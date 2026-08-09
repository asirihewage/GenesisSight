"""ByteTrack multi-object tracker (via supervision).

Turns per-frame detections into stable track ids. `reset()` must be called at
the start of each video.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from app.config import settings
from app.services.detector import Detection

logger = logging.getLogger(__name__)


@dataclass
class TrackedDetection:
    xyxy: np.ndarray
    track_id: int
    confidence: float
    class_id: int

    @property
    def class_name(self) -> str:
        return self._class_name

    @property
    def _class_name(self) -> str:  # pragma: no cover - trivial
        from app.services.detector import CLASS_NAMES

        return CLASS_NAMES.get(int(self.class_id), f"class_{int(self.class_id)}")

    def person(self) -> bool:
        return int(self.class_id) == 0


class ByteTrackTracker:
    def __init__(self) -> None:
        self._tracker: object | None = None

    def _ensure(self) -> None:
        if self._tracker is None:
            import warnings

            warnings.filterwarnings("ignore", category=FutureWarning, module="supervision")
            from supervision import ByteTrack

            # Parameters tuned for CCTV: keep tracks alive across occlusions.
            # minimum_matching_threshold is low because sampling runs at ~3 fps,
            # so inter-frame boxes move far and IoU is small.
            self._tracker = ByteTrack(
                track_activation_threshold=0.25,
                minimum_matching_threshold=0.30,
                frame_rate=max(1, int(settings.target_fps)),
            )
            logger.info("ByteTrack initialized")

    def reset(self) -> None:
        self._ensure()
        self._tracker.reset()  # type: ignore[attr-defined]

    def update(self, detections: list[Detection]) -> list[TrackedDetection]:
        self._ensure()
        from supervision import Detections

        if not detections:
            return []
        xyxy = np.stack([d.xyxy for d in detections]).astype(np.float32)
        conf = np.array([d.confidence for d in detections], dtype=np.float32)
        cls = np.array([d.class_id for d in detections], dtype=int)
        det = Detections(xyxy=xyxy, confidence=conf, class_id=cls)

        tracked = self._tracker.update_with_detections(det)  # type: ignore[attr-defined]
        if tracked is None or len(tracked) == 0:
            return []

        out: list[TrackedDetection] = []
        for i in range(len(tracked)):
            tid = int(tracked.tracker_id[i])
            out.append(
                TrackedDetection(
                    xyxy=tracked.xyxy[i].astype(np.float32),
                    track_id=tid,
                    confidence=float(tracked.confidence[i]),
                    class_id=int(tracked.class_id[i]),
                )
            )
        return out
