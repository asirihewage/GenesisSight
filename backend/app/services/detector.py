"""Object detection adapter: YOLO11x via ultralytics.

Detects people plus context objects (bags, vehicles, animals) used by the event
engine and the VLM description. Detection runs on *batches* of motion frames to
saturate the GPU. Weights auto-download into `models/` on first use.

`get_detector()` returns a process-wide singleton so weights load exactly once.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

# COCO-80 classes we care about
CLASS_NAMES: dict[int, str] = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
    14: "bird",
    15: "cat",
    16: "dog",
    24: "backpack",
    25: "umbrella",
    26: "handbag",
    28: "suitcase",
    29: "frisbee",
    30: "skis",
    31: "snowboard",
    33: "kite",
    37: "surfboard",
    39: "bottle",
    41: "cup",
    43: "knife",
    45: "bowl",
    46: "banana",
    48: "sandwich",
    53: "pizza",
    54: "donut",
    55: "cake",
    56: "chair",
    57: "couch",
    62: "tv",
    63: "laptop",
    64: "mouse",
    65: "remote",
    66: "keyboard",
    67: "cell phone",
    73: "book",
    74: "clock",
    76: "scissors",
    79: "toothbrush",
}

BAG_CLASSES = {24, 25, 26, 28}  # backpack, umbrella, handbag, suitcase


@dataclass
class Detection:
    xyxy: np.ndarray  # (4,) float
    confidence: float
    class_id: int

    @property
    def class_name(self) -> str:
        return CLASS_NAMES.get(int(self.class_id), f"class_{int(self.class_id)}")


class YOLODetector:
    def __init__(self, weights: str | Path, device: str = "auto") -> None:
        from ultralytics import YOLO

        self.model = YOLO(str(weights))
        self.device = self._resolve_device(device)
        logger.info("YOLO model %s loaded on device %s", weights, self.device)

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device != "auto":
            return device
        try:
            import torch

            if torch.cuda.is_available():
                return "0"
        except Exception:
            pass
        return "cpu"

    def warmup(self) -> None:
        dummy = np.zeros((64, 64, 3), dtype=np.uint8)
        self.detect_batch([dummy], verbose=False)

    def detect_batch(
        self,
        frames: Sequence[np.ndarray],
        conf: float | None = None,
        iou: float | None = None,
        verbose: bool = False,
    ) -> list[list[Detection]]:
        """Run YOLO over a batch of frames. Returns per-frame detection lists."""
        if not frames:
            return []
        results = self.model.predict(
            source=list(frames),
            conf=conf or settings.yolo_conf,
            iou=iou or settings.yolo_iou,
            imgsz=settings.yolo_img_size,
            device=self.device,
            verbose=verbose,
            stream=False,
        )
        out: list[list[Detection]] = []
        for r in results:
            dets: list[Detection] = []
            if r.boxes is not None and len(r.boxes) > 0:
                xyxy = r.boxes.xyxy.cpu().numpy()
                confs = r.boxes.conf.cpu().numpy()
                cls = r.boxes.cls.cpu().numpy().astype(int)
                for b, c, k in zip(xyxy, confs, cls):
                    dets.append(Detection(xyxy=b.astype(np.float32), confidence=float(c), class_id=int(k)))
            out.append(dets)
        return out


_detector: YOLODetector | None = None


def get_detector() -> YOLODetector:
    global _detector
    if _detector is None:
        models_dir = Path(settings.model_dir)
        models_dir.mkdir(parents=True, exist_ok=True)
        weights = models_dir / settings.yolo_model
        _detector = YOLODetector(weights, settings.device)
    return _detector
