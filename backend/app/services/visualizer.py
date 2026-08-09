"""Frame / crop visualization and persistence.

Saves event frames (with detection boxes drawn) and person crops to
`storage/frames/<video_id>/` and `storage/images/<video_id>/`. Paths stored in
the DB are relative to the storage dir and exposed via the `/media` mount.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

import cv2
import numpy as np

from app.config import IMAGES_DIR, FRAMES_DIR, settings

logger = logging.getLogger(__name__)

_STORAGE = Path(settings.storage_dir)


def _rel_to_storage(path: Path) -> str:
    return str(path.relative_to(_STORAGE)).replace("\\", "/")


def save_frame(video_id: int, name: str, frame: np.ndarray, quality: int = 92) -> str:
    path = FRAMES_DIR / str(video_id) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("JPEG encode failed")
    path.write_bytes(buf.tobytes())
    return _rel_to_storage(path)


def save_image(video_id: int, name: str, image: np.ndarray, quality: int = 92) -> str:
    path = IMAGES_DIR / str(video_id) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("JPEG encode failed")
    path.write_bytes(buf.tobytes())
    return _rel_to_storage(path)


def draw_tracks(frame: np.ndarray, tracks: list, person_labels: dict[int, str]) -> np.ndarray:
    """Draw bounding boxes + person ids on a copy of the frame."""
    vis = frame.copy()
    for t in tracks:
        x1, y1, x2, y2 = (int(v) for v in t.xyxy)
        color = (59, 130, 246) if t.person() else (250, 204, 21)  # BGR
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
        label = person_labels.get(t.track_id)
        if label:
            label = f"#{label}"
        else:
            label = CLASS_LABEL_FALLBACK(t)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(vis, (x1, y1 - th - 8), (x1 + tw + 6, y1), color, -1)
        cv2.putText(vis, label, (x1 + 3, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (10, 10, 10), 1)
    return vis


def CLASS_LABEL_FALLBACK(track: object) -> str:  # pragma: no cover - trivial
    from app.services.detector import CLASS_NAMES

    return CLASS_NAMES.get(int(track.class_id), str(track.class_id))


def crop_person(frame: np.ndarray, xyxy: np.ndarray, pad_ratio: float = 0.12) -> np.ndarray:
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = [float(v) for v in xyxy]
    pad_x, pad_y = (x2 - x1) * pad_ratio, (y2 - y1) * pad_ratio
    x1, y1 = max(0, int(x1 - pad_x)), max(0, int(y1 - pad_y))
    x2, y2 = min(w, int(x2 + pad_x)), min(h, int(y2 + pad_y))
    if x2 - x1 < 8 or y2 - y1 < 8:
        x1, y1, x2, y2 = int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])
    return frame[y1:y2, x1:x2]


def unique_name(prefix: str, ext: str = "jpg") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}.{ext}"
