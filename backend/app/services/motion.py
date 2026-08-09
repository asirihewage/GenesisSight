"""Motion detection gate.

Cheap frame-difference motion detector. Runs on every sampled frame and acts as
the GPU gate: YOLO inference is skipped on static frames, which is the biggest
saving for long CCTV recordings. Also detects scene cuts so a hard cut never
spawns a flood of bogus events.
"""

from __future__ import annotations

import cv2
import numpy as np


class MotionDetector:
    def __init__(self, threshold_ratio: float = 0.0025, scale: float = 0.25) -> None:
        self.threshold_ratio = threshold_ratio
        self.scale = scale
        self._prev_gray: np.ndarray | None = None

    @staticmethod
    def _resize_gray(frame: np.ndarray, scale: float) -> np.ndarray:
        if scale != 1.0:
            frame = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    def analyze(self, frame: np.ndarray) -> tuple[bool, bool]:
        """Return (has_motion, is_scene_change). Updates internal state."""
        gray = self._resize_gray(frame, self.scale)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        if self._prev_gray is None:
            self._prev_gray = gray
            return False, False

        diff = cv2.absdiff(self._prev_gray, gray)
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        changed = float(np.count_nonzero(thresh))
        total = float(thresh.size)
        ratio = changed / total if total > 0 else 0.0

        scene_change = ratio > 0.35
        has_motion = (not scene_change) and ratio > self.threshold_ratio

        self._prev_gray = gray
        return has_motion, scene_change

    def reset(self) -> None:
        self._prev_gray = None
