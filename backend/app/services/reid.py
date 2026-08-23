"""Person Re-Identification engine.

Preferred backend: OSNet (x1_0) via `torchreid` with pre-trained reid weights.
Fallback: ResNet50 (ImageNet) embedding — still a real, functional embedding
model. `disabled` makes matching fall back to track-id only (no cross-track
identity merging), so the app never fakes identity.

Because weights live in `models/`, resolution is:

1. OSNet + weights file            -> best quality (needs `pip install torchreid`)
2. OSNet without weights           -> falls back to ResNet50
3. torchreid not importable        -> falls back to ResNet50
4. REID_ENGINE=disabled            -> identity = track id
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class ReIDEngine:
    def __init__(self, engine: str = "auto") -> None:
        self.backend: str = "disabled"
        self._model = None
        self._device = "cpu"
        self.dim = 0
        self._in_w, self._in_h = 224, 224

        if engine == "disabled":
            logger.warning("ReID disabled by config: identity = ByteTrack id")
            return

        import torch

        self._device = "cuda" if torch.cuda.is_available() and settings.torch_device == "cuda" else "cpu"

        weights = settings.reid_weights
        weights_path = Path(weights) if weights else None

        # 1) OSNet via torchreid
        if engine == "osnet":
            try:
                import torchreid  # type: ignore[import-untyped]

                torchreid.utils.set_logger.severity = "error"  # quiet
                model = torchreid.models.build_model(
                    name="osnet_x1_0", num_classes=1000, pretrained=False
                )
                if weights_path is not None and weights_path.exists():
                    torchreid.utils.load_pretrained_weights(model, str(weights_path))
                    logger.info("OSNet weights loaded from %s", weights_path)
                else:
                    logger.warning(
                        "OSNet requested but weights file not found (%s). "
                        "See README for download instructions; falling back to ResNet50.",
                        weights_path,
                    )
                    raise RuntimeError("osnet weights missing")
                model = model.eval().to(self._device)
                self._model = model
                self.backend = "osnet"
                self.dim = 512
                self._in_w, self._in_h = 128, 256
                logger.info("ReID backend: OSNet x1_0 on %s", self._device)
                return
            except ImportError:
                logger.warning("torchreid not installed — falling back to ResNet50 embeddings")
            except Exception as exc:  # build/load failure
                logger.warning("OSNet init failed (%s) — falling back to ResNet50", exc)

        # 2) ResNet50 fallback
        if engine in ("osnet", "resnet"):
            try:
                import torch
                import torch.nn as nn
                import torchvision.models as tv_models

                model = tv_models.resnet50(weights=tv_models.ResNet50_Weights.IMAGENET1K_V1)
                model.fc = nn.Identity()
                model = model.eval().to(self._device)
                self._model = model
                self.backend = "resnet"
                self.dim = 2048
                logger.info("ReID backend: ResNet50 (ImageNet) on %s", self._device)
                return
            except Exception as exc:
                logger.error("ResNet50 fallback failed: %s", exc)

        logger.warning("ReID disabled (no usable backend): identity = track id")

    def enabled(self) -> bool:
        return self.backend != "disabled"

    def embed_crops(self, crops: list[np.ndarray]) -> np.ndarray:
        """Embed person crops -> (N, dim) L2-normalized matrix."""
        if not self.enabled() or not crops:
            return np.zeros((len(crops), self.dim), dtype=np.float32)
        images = []
        for c in crops:
            if c is None or c.ndim != 3 or c.shape[0] < 1 or c.shape[1] < 1:
                images.append(np.zeros((self._in_h, self._in_w, 3), dtype=np.uint8))
            else:
                images.append(self._preprocess(c))
        import torch
        import torch.nn.functional as F

        tensor = torch.from_numpy(np.stack(images)).to(self._device)
        with torch.no_grad():
            feats = self._model(tensor)
        feats = F.normalize(feats, p=2, dim=1).cpu().numpy()
        return feats.astype(np.float32)

    def _preprocess(self, crop: np.ndarray) -> np.ndarray:
        """Crop (H,W,3) -> (3,224,224) ImageNet-normalized float32."""
        import cv2

        if self.backend == "osnet":
            w, h = 128, 256  # OSNet convention (W=128, H=256)
        else:
            w, h = 224, 224
        img = cv2.resize(crop, (w, h), interpolation=cv2.INTER_LINEAR)
        img = img.astype(np.float32) / 255.0
        img = (img - _IMAGENET_MEAN) / _IMAGENET_STD
        return np.transpose(img, (2, 0, 1))

    # ------------------------------------------------------------------
    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Row-wise cosine similarity between (M,d) and (d,) -> (M,)."""
        if a.size == 0:
            return np.zeros((0,), dtype=np.float32)
        denom = np.linalg.norm(a, axis=1) * np.linalg.norm(b)
        if denom == 0:
            return np.zeros((a.shape[0],), dtype=np.float32)
        return (a @ b) / denom


_reid: ReIDEngine | None = None


def get_reid_engine() -> ReIDEngine:
    global _reid
    if _reid is None:
        _reid = ReIDEngine(settings.reid_engine)
    return _reid
