"""Video reading with an FFmpeg fallback.

OpenCV wheels bundle a minimal FFmpeg that cannot decode proprietary DVR
codecs (H.264/MPEG-4/MJPEG from NVRs). When OpenCV fails to open a file we
fall back to a real ffmpeg binary (bundled with imageio-ffmpeg) streaming
raw BGR frames over a pipe, so the rest of the pipeline stays unchanged.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
from typing import Iterator

import numpy as np

logger = logging.getLogger(__name__)

# Some DVR/NVR recorders tag HEVC/H.264 streams with nonstandard fourccs
# (e.g. "x265", "h265") inside AVI. FFmpeg's AVI demuxer does not map these
# to a codec, so decoding fails. We patch the tag bytes in a temporary copy.
_FOURCC_PATCHES = {
    b"x265": b"HEVC",
    b"h265": b"HEVC",
    b"X265": b"HEVC",
    b"x264": b"H264",
    b"X264": b"H264",
}
_PATCHABLE_CODEC_RE = re.compile(r"\b(none|unknown)\b")


def _patch_fourcc_file(path: str) -> str | None:
    """Return a temp path where nonstandard codec tags were rewritten, or None."""
    try:
        with open(path, "rb") as fh:
            data = bytearray(fh.read())
    except OSError as exc:
        logger.warning("VideoReader: cannot read %s for tag patch: %s", path, exc)
        return None
    patched = False
    for src, dst in _FOURCC_PATCHES.items():
        idx = 0
        while True:
            idx = data.find(src, idx)
            if idx < 0:
                break
            data[idx : idx + 4] = dst
            idx += 4
            patched = True
    if not patched:
        return None
    fd, tmp = tempfile.mkstemp(suffix=os.path.splitext(path)[1] or ".avi")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(bytes(data))
    except OSError:
        return None
    logger.info("VideoReader: patched fourcc tags of %s -> %s", path, tmp)
    return tmp


class VideoReader:
    """Unified frame source: OpenCV first, ffmpeg pipe as fallback."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.fps = 25.0
        self.width = 0
        self.height = 0
        self.frame_count: int | None = None
        self.duration: float | None = None
        self.backend: str | None = None
        self._cap = None
        self._proc: subprocess.Popen | None = None
        self._frame_size = 0
        self._fallback_error: str | None = None
        self._patched_path: str | None = None

    # ------------------------------------------------------------------
    def open(self) -> bool:
        import cv2

        cap = cv2.VideoCapture(self.path)
        if cap.isOpened():
            self._cap = cap
            self.fps = float(cap.get(cv2.CAP_PROP_FPS)) or 25.0
            self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 0
            self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 0
            fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.frame_count = fc if fc > 0 else None
            if self.duration is None and self.frame_count:
                self.duration = self.frame_count / self.fps
            self.backend = "opencv"
            logger.info("VideoReader: opencv backend for %s", self.path)
            return True
        cap.release()
        return self._open_ffmpeg()

    def _open_ffmpeg(self) -> bool:
        try:
            import imageio_ffmpeg

            exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as exc:  # package not installed
            self._fallback_error = f"imageio-ffmpeg unavailable: {exc}"
            logger.warning("VideoReader: %s", self._fallback_error)
            return False

        try:
            probe = subprocess.run(
                [exe, "-hide_banner", "-i", self.path],
                capture_output=True, text=True, timeout=60,
            )
            err = probe.stderr
            m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", err)
            if not m:
                self._fallback_error = "ffmpeg could not parse video stream"
                return False
            stream_line = m.group(0)
            if _PATCHABLE_CODEC_RE.search(stream_line):
                patched = _patch_fourcc_file(self.path)
                if patched is not None:
                    probe = subprocess.run(
                        [exe, "-hide_banner", "-i", patched],
                        capture_output=True, text=True, timeout=60,
                    )
                    err = probe.stderr
                    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", err)
                    if m is None:
                        self._cleanup_patched()
                        self._fallback_error = "ffmpeg could not parse patched stream"
                        return False
                    self._patched_path = patched
                    stream_line = m.group(0)
            self.width, self.height = int(m.group(1)), int(m.group(2))
            mf = re.search(r"(\d+(?:\.\d+)?) fps", err)
            self.fps = float(mf.group(1)) if mf else 25.0
            md = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", err)
            if md:
                self.duration = (int(md.group(1)) * 3600 + int(md.group(2)) * 60
                                 + float(md.group(3)))
        except Exception as exc:
            self._fallback_error = f"ffmpeg probe failed: {exc}"
            logger.warning("VideoReader: %s", self._fallback_error)
            return False

        if self.duration is not None:
            self.frame_count = int(round(self.duration * self.fps))

        self._frame_size = self.width * self.height * 3
        cmd = [
            exe, "-hide_banner", "-loglevel", "error",
            "-i", self._patched_path or self.path, "-an",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "-fps_mode", "passthrough", "-",
        ]
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, bufsize=10 * 1024 * 1024
            )
        except Exception as exc:
            self._fallback_error = f"ffmpeg spawn failed: {exc}"
            logger.warning("VideoReader: %s", self._fallback_error)
            return False
        self.backend = "ffmpeg"
        logger.info("VideoDecoder: ffmpeg backend for %s (%sx%s @ %.1f fps)",
                    self.path, self.width, self.height, self.fps)
        return True

    # ------------------------------------------------------------------
    def read(self) -> tuple[bool, np.ndarray | None]:
        if self._cap is not None:
            ret, frame = self._cap.read()
            if not ret or frame is None:
                return False, None
            # Some CCTV/DVR streams hand back ret=True frames with zero-sized
            # buffers (OpenCV logs them as 0x0). Passing those to cv2.resize
            # crashes with "!ssize.empty()". Treat them as failed reads.
            if frame.ndim != 3 or frame.shape[0] < 1 or frame.shape[1] < 1:
                return False, None
            return ret, frame

        data = self._proc.stdout.read(self._frame_size)  # type: ignore[union-attr]
        if not data or len(data) < self._frame_size:
            return False, None
        frame = np.frombuffer(data, dtype=np.uint8)
        return True, frame.reshape(self.height, self.width, 3)

    def is_open(self) -> bool:
        return self._cap is not None or (
            self._proc is not None and self._proc.poll() is None
        )

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        if self._proc is not None:
            try:
                if self._proc.stdout is not None:
                    self._proc.stdout.close()
            except Exception:
                pass
            if self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=5)
                except Exception:
                    self._proc.kill()
            self._proc = None
        self._cleanup_patched()

    def _cleanup_patched(self) -> None:
        if self._patched_path is not None:
            try:
                os.remove(self._patched_path)
            except OSError:
                pass
            self._patched_path = None

    def __iter__(self) -> Iterator[tuple[bool, np.ndarray | None]]:
        while True:
            ok, frame = self.read()
            if not ok:
                return
            yield ok, frame