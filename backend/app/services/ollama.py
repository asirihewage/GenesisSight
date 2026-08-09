"""Ollama integration service.

- `analyze_event(images, context)` — sends keyframe images to a vision model
  (default qwen2.5vl:7b) and parses the JSON response:
  `{description, objects, activity, confidence}`.
- `embed(texts)` — embeddings API used by natural-language search.

All calls are serialized (single Ollama process; avoids VRAM contention with
the detector) and never raise: failures are logged and return None so the
pipeline degrades gracefully to rule-based descriptions.

The core is synchronous (`*_sync`) so it can be driven from the analysis
worker thread; async wrappers offload via `asyncio.to_thread`.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import threading
from typing import Any

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, base_url: str | None = None,
                 vlm_model: str | None = None,
                 embed_model: str | None = None) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.vlm_model = vlm_model or settings.ollama_vlm_model
        self.embed_model = embed_model or settings.ollama_embed_model
        self._lock = threading.Lock()
        self._available: bool | None = None

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------
    def is_available_sync(self) -> bool:
        if self._available is not None:
            return self._available
        import httpx

        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=settings.ollama_connect_timeout_s)
            self._available = resp.status_code == 200
        except Exception:
            self._available = False
        if not self._available:
            logger.warning(
                "Ollama not reachable at %s — VLM enrichment and semantic search disabled",
                self.base_url,
            )
        return self._available

    async def is_available(self) -> bool:
        return await asyncio.to_thread(self.is_available_sync)

    def list_models_sync(self) -> list[str]:
        import httpx

        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=settings.ollama_connect_timeout_s)
            if resp.status_code == 200:
                return [m.get("name", "") for m in resp.json().get("models", [])]
        except Exception:
            pass
        return []

    async def list_models(self) -> list[str]:
        return await asyncio.to_thread(self.list_models_sync)

    def ensure_model_sync(self, model: str) -> bool:
        """Best-effort `ollama pull` for a missing model (blocks)."""
        import httpx

        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=10)
            names = [m.get("name", "") for m in resp.json().get("models", [])]
            if any(n == model or n.startswith(model + ":") for n in names):
                return True
            logger.info("Pulling Ollama model %s (this can take a while)…", model)
            resp = httpx.post(f"{self.base_url}/api/pull", json={"model": model, "stream": False},
                              timeout=None)
            return resp.status_code == 200
        except Exception as exc:
            logger.warning("Failed to pull model %s: %s", model, exc)
            return False

    # ------------------------------------------------------------------
    # VLM event analysis (sync core)
    # ------------------------------------------------------------------
    def analyze_event_sync(self, images: list[bytes], context: dict[str, Any]) -> dict[str, Any] | None:
        if not self.is_available_sync() or not images:
            return None

        with self._lock:
            import httpx

            messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
            user_content: list[dict[str, Any]] = [
                {"type": "image", "image": base64.b64encode(img).decode("ascii")}
                for img in images[:3]
            ]
            user_content.append({"type": "text", "text": self._user_prompt(context)})
            messages.append({"role": "user", "content": user_content})

            for attempt in range(2):
                try:
                    resp = httpx.post(
                        f"{self.base_url}/api/chat",
                        json={"model": self.vlm_model, "messages": messages,
                              "stream": False, "format": "json",
                              "options": {"temperature": 0.2, "num_predict": 512}},
                        timeout=settings.ollama_timeout_s,
                    )
                    if resp.status_code != 200:
                        logger.warning("Ollama chat HTTP %s: %s", resp.status_code, resp.text[:200])
                        return None
                    content = resp.json()["message"]["content"]
                    return _parse_json_response(content)
                except Exception as exc:
                    logger.warning("Ollama VLM attempt %d failed: %s", attempt + 1, exc)
                    time_sleep(2.0 * (attempt + 1))
        return None

    async def analyze_event(self, images: list[bytes], context: dict[str, Any]) -> dict[str, Any] | None:
        return await asyncio.to_thread(self.analyze_event_sync, images, context)

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------
    def embed_sync(self, texts: list[str]) -> np.ndarray | None:
        if not self.is_available_sync() or not texts:
            return None
        import httpx

        try:
            resp = httpx.post(
                f"{self.base_url}/api/embed",
                json={"model": self.embed_model, "input": texts},
                timeout=60,
            )
            if resp.status_code != 200:
                logger.warning("Ollama embed HTTP %s", resp.status_code)
                return None
            data = resp.json().get("embeddings") or []
            if not data:
                return None
            return np.asarray(data, dtype=np.float32)
        except Exception as exc:
            logger.warning("Ollama embed failed: %s", exc)
            return None

    async def embed(self, texts: list[str]) -> np.ndarray | None:
        return await asyncio.to_thread(self.embed_sync, texts)

    # ------------------------------------------------------------------
    @staticmethod
    def _user_prompt(context: dict[str, Any]) -> str:
        return (
            "These are keyframes from a CCTV security camera recording "
            f"({context.get('video', 'unknown')}).\n"
            f"A rule engine detected: {context.get('event_type', 'unknown')} "
            f"at {context.get('ts_display', '')}.\n"
            f"Rule description: {context.get('rule_desc', '')}\n"
            f"Detected objects: {context.get('objects', [])}\n\n"
            "Describe what is happening in 1-2 sentences for a security log. "
            "Return JSON only."
        )


def time_sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)


def _parse_json_response(content: str) -> dict[str, Any] | None:
    """Robust JSON extraction from an LLM response (strip fences etc.)."""
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    desc = str(data.get("description", "")).strip()
    if not desc:
        return None
    objects = data.get("objects", [])
    if not isinstance(objects, list):
        objects = [objects] if objects else []
    return {
        "description": desc,
        "objects": [str(o) for o in objects if str(o)][:10],
        "activity": str(data.get("activity", "")).strip() or None,
        "confidence": float(data.get("confidence", 0.5)),
    }


_SYSTEM_PROMPT = (
    "You are a CCTV security video analyst. You receive keyframe images from a "
    "camera recording. Describe the situation concisely and factually for a "
    "security event log. Reply ONLY with a JSON object of the form "
    '{"description": "<1-2 sentence description>", "objects": ["person", "backpack"], '
    '"activity": "<verb phrase>", "confidence": 0.0-1.0}. '
    "Do not invent details that are not visible in the image."
)


ollama_client = OllamaClient()
