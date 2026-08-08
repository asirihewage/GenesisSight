"""Generate a synthetic CCTV-style test video using real person photos.

Composites two real photos (from ultralytics' public sample images) onto a
static background to exercise the full pipeline:
  - one person photo walks across the frame (enter -> move -> exit -> re-enter)
  - a second photo (multiple people) stays static in the corner (loitering)

Usage: python scripts/make_test_video.py output.avi
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

ASSETS = Path(__file__).resolve().parent / "assets"


def paste(img: np.ndarray, base: np.ndarray, x: int, y: int, h_frac: float) -> None:
    """Paste `img` (photo) onto `base` scaled to h_frac of base height."""
    target_h = int(base.shape[0] * h_frac)
    scale = target_h / img.shape[0]
    target_w = int(img.shape[1] * scale)
    if target_w <= 0 or target_h <= 0:
        return
    small = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_AREA)
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(base.shape[1], x + target_w)
    y2 = min(base.shape[0], y + target_h)
    if x2 <= x1 or y2 <= y1:
        return
    region = base[y1:y2, x1:x2]
    patch = small[: y2 - y1, : x2 - x1]
    # slight soft blend on the edges so the composite reads as "video noise"
    region[:] = cv2.addWeighted(region, 0.15, patch, 0.85, 0)


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "test_cctv.avi")
    zidane = cv2.imread(str(ASSETS / "zidane.jpg"))
    bus = cv2.imread(str(ASSETS / "bus.jpg"))
    if zidane is None or bus is None:
        print(f"missing assets in {ASSETS} — download zidane.jpg + bus.jpg first")
        return 1

    fps, duration, w, h = 15, 24, 960, 540
    writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"MJPG"), fps, (w, h))

    # static background + static bus photo (people in corner)
    bg = np.full((h, w, 3), 118, dtype=np.uint8)
    bus_bg = bg.copy()
    paste(bus, bus_bg, w - 420, h - 260, 0.34)

    for f in range(fps * duration):
        t = f / fps
        frame = bus_bg.copy()
        if t < 7.5:
            # walk across left->right
            x = int(30 + t / 7.5 * (w - 260))
            paste(zidane, frame, x, 90, 0.55)
        elif 7.5 <= t < 10.5:
            # gone (off-camera)
            pass
        else:
            # re-enter from the right, walk left
            x = int(w - 60 - (t - 10.5) / 6.0 * (w - 200))
            paste(zidane, frame, x, 90, 0.55)
        writer.write(frame)
    writer.release()
    print(f"wrote {out} ({duration}s, {w}x{h}@{fps}fps)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
