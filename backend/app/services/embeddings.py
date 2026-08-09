"""Semantic search over events.

Strategy:
1. Embed the query with Ollama embeddings (`nomic-embed-text` by default).
2. Lazily embed event descriptions that lack an embedding (cached in DB).
3. Rank by cosine similarity.
4. If Ollama is unavailable, fall back to a pure-numpy char n-gram TF cosine
   score — keyword search that still works fully offline.
"""

from __future__ import annotations

import logging
import re
from collections import Counter

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event
from app.schemas import EventOut
from app.services.ollama import ollama_client

logger = logging.getLogger(__name__)


class SearchService:
    async def search(self, db: Session, query: str,
                     video_id: int | None = None, limit: int = 25) -> tuple[list[tuple[EventOut, float]], str]:
        """Returns (results, method_used)."""
        query = (query or "").strip()
        if not query:
            return [], "keyword"

        events = self._load_events(db, video_id, limit=1000)
        if not events:
            return [], "keyword"

        query_emb = await ollama_client.embed([query])
        if query_emb is not None:
            method = "ollama_embedding"
            await self._ensure_event_embeddings(db, events)
            scores = self._score_cosine(events, query_emb[0])
        else:
            method = "keyword"
            scores = self._score_keyword(events, query)

        ranked = sorted(zip(events, scores), key=lambda pair: pair[1], reverse=True)
        results = [(self._to_out(e), float(s)) for e, s in ranked[:limit] if s > 0.0]
        return results, method

    # ------------------------------------------------------------------
    @staticmethod
    def _load_events(db: Session, video_id: int | None, limit: int) -> list[Event]:
        stmt = select(Event)
        if video_id is not None:
            stmt = stmt.where(Event.video_id == video_id)
        stmt = stmt.order_by(Event.timestamp.asc()).limit(limit)
        return list(db.scalars(stmt))

    async def _ensure_event_embeddings(self, db: Session, events: list[Event]) -> None:
        missing = [e for e in events if not e.embedding and (e.description or "")]
        if not missing:
            return
        texts = [e.description[:512] for e in missing]
        embs = await ollama_client.embed(texts)
        if embs is None:
            return
        for e, emb in zip(missing, embs):
            e.embedding = [float(v) for v in emb]
        try:
            db.commit()
        except Exception:
            db.rollback()

    @staticmethod
    def _score_cosine(events: list[Event], query_emb: np.ndarray) -> list[float]:
        q_norm = float(np.linalg.norm(query_emb)) or 1.0
        scores: list[float] = []
        for e in events:
            if not e.embedding:
                scores.append(0.0)
                continue
            vec = np.asarray(e.embedding, dtype=np.float32)
            denom = float(np.linalg.norm(vec)) * q_norm
            scores.append(float(vec @ query_emb) / denom if denom > 0 else 0.0)
        return scores

    @staticmethod
    def _score_keyword(events: list[Event], query: str) -> list[float]:
        q_grams = _char_ngrams(_norm(query), n=3)
        if not q_grams:
            return [0.0] * len(events)
        q_vec = _tf(q_grams)
        q_len = _norm_len(q_vec)
        out: list[float] = []
        for e in events:
            text = f"{e.description or ''} {e.event_type or ''} {e.objects or ''}"
            d_vec = _tf(_char_ngrams(_norm(text), n=3))
            denom = _norm_len(d_vec) * q_len
            out.append(_dot(d_vec, q_vec) / denom if denom > 0 else 0.0)
        return out

    @staticmethod
    def _to_out(e: Event) -> EventOut:
        return EventOut(
            id=e.id,
            video_id=e.video_id,
            person_id=e.person_id,
            timestamp=e.timestamp,
            event_type=e.event_type,
            description=e.description,
            confidence=e.confidence,
            image_url=_media_url(e.image_path),
            thumbnail_url=_media_url(e.thumbnail_path),
            objects=(e.objects or []) if isinstance(e.objects, list) else [],
            activity=e.activity,
            created_at=e.created_at,
        )


def _media_url(rel_path: str | None) -> str | None:
    if not rel_path:
        return None
    return f"/media/{rel_path}"


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", "", text.lower())


def _char_ngrams(text: str, n: int = 3) -> list[str]:
    text = "".join(text.split())
    if len(text) < n:
        return list(text)
    return [text[i:i + n] for i in range(len(text) - n + 1)]


def _tf(grams: list[str]) -> dict[str, float]:
    counts = Counter(grams)
    total = sum(counts.values()) or 1.0
    return {g: c / total for g, c in counts.items()}


def _dot(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(a.get(k, 0.0) * v for k, v in b.items())


def _norm_len(a: dict[str, float]) -> float:
    return float(np.sqrt(sum(v * v for v in a.values())))


search_service = SearchService()
