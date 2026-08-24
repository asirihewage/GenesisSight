"""License Plate Recognition (LPR) service.

Detects license plates in vehicle crops and runs OCR to extract plate text.
Uses a dedicated YOLO model for plate detection + EasyOCR for text recognition.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PlateResult:
    """Result of license plate detection and OCR."""
    plate_text: str
    confidence: float
    bbox: np.ndarray  # xyxy in crop coordinates
    detection_confidence: float


class LPRDetector:
    """License plate detector with OCR."""

    def __init__(self, weights: str | Path, device: str = "auto", ocr_langs: list[str] | None = None) -> None:
        self.weights = str(weights)
        self.device = self._resolve_device(device)
        self.ocr_langs = ocr_langs or ["en"]
        self._model = None
        self._ocr_reader = None
        self._load_model()
        self._load_ocr()

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

    def _load_model(self) -> None:
        """Load the license plate detection YOLO model."""
        try:
            from ultralytics import YOLO
            self._model = YOLO(self.weights)
            self._model.to(self.device)
            logger.info("LPR model %s loaded on device %s", self.weights, self.device)
        except Exception as e:
            logger.warning("Failed to load LPR model %s: %s. Will try to download.", self.weights, e)
            self._model = None

    def _load_ocr(self) -> None:
        """Load EasyOCR reader."""
        try:
            import easyocr
            self._ocr_reader = easyocr.Reader(self.ocr_langs, gpu=self.device != "cpu")
            logger.info("EasyOCR loaded for languages: %s", self.ocr_langs)
        except Exception as e:
            logger.warning("Failed to load EasyOCR: %s. OCR will be unavailable.", e)
            self._ocr_reader = None

    def detect_plates(self, frame: np.ndarray, conf: float | None = None) -> list[PlateResult]:
        """Detect license plates in a frame and run OCR on each."""
        if self._model is None:
            return []

        results = self._model.predict(
            source=frame,
            conf=conf or settings.lpr_conf,
            imgsz=640,
            device=self.device,
            verbose=False,
            stream=False,
        )

        plates: list[PlateResult] = []
        for r in results:
            if r.boxes is None or len(r.boxes) == 0:
                continue
            xyxy = r.boxes.xyxy.cpu().numpy()
            confs = r.boxes.conf.cpu().numpy()
            for bbox, det_conf in zip(xyxy, confs):
                # Crop the plate region
                x1, y1, x2, y2 = [int(v) for v in bbox]
                h, w = frame.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                if x2 <= x1 or y2 <= y1:
                    continue
                plate_crop = frame[y1:y2, x1:x2]
                if plate_crop.size == 0:
                    continue

                # Run OCR on plate crop
                plate_text, ocr_conf = self._ocr_plate(plate_crop)
                if plate_text and ocr_conf >= settings.lpr_min_confidence:
                    plates.append(PlateResult(
                        plate_text=plate_text.upper().replace(" ", ""),
                        confidence=ocr_conf,
                        bbox=bbox.astype(np.float32),
                        detection_confidence=float(det_conf),
                    ))
        return plates

    def _ocr_plate(self, crop: np.ndarray) -> tuple[str, float]:
        """Run OCR on a plate crop. Returns (text, confidence)."""
        if self._ocr_reader is None:
            return "", 0.0
        try:
            # EasyOCR returns list of (bbox, text, confidence)
            results = self._ocr_reader.readtext(crop)
            if not results:
                return "", 0.0
            # Take the highest confidence result
            best = max(results, key=lambda x: x[2])
            text = best[1].strip()
            confidence = float(best[2])
            # Basic cleanup: keep only alphanumeric
            text = "".join(c for c in text if c.isalnum())
            return text, confidence
        except Exception as e:
            logger.debug("OCR failed on plate crop: %s", e)
            return "", 0.0

    def warmup(self) -> None:
        """Warm up the model and OCR."""
        dummy = np.zeros((320, 320, 3), dtype=np.uint8)
        self.detect_plates(dummy)


_lpr_detector: Optional[LPRDetector] = None


def get_lpr_detector() -> Optional[LPRDetector]:
    """Get or create the global LPR detector singleton."""
    global _lpr_detector
    if not settings.lpr_enabled:
        return None
    if _lpr_detector is None:
        models_dir = Path(settings.model_dir)
        models_dir.mkdir(parents=True, exist_ok=True)
        weights = models_dir / settings.lpr_model
        # Check if model exists, if not it will auto-download via ultralytics
        _lpr_detector = LPRDetector(weights, settings.device, settings.lpr_ocr_lang)
    return _lpr_detector