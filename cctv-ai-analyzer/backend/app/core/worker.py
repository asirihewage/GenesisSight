"""Analysis worker.

A single async worker consumes a queue of video ids. Only one video is analyzed
at a time: the GPU pipeline (YOLO + ReID) is a single heavy consumer and the
queue guarantees predictable progress without VRAM contention. This is a clean
stand-in for Redis + Celery — swap `AnalysisWorker.enqueue` for a Celery task
without touching the pipeline itself.
"""

from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.core.ws_manager import manager
from app.database import SessionLocal
from app.models import Video

logger = logging.getLogger(__name__)


class AnalysisWorker:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[int] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._running_ids: set[int] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._loop = asyncio.get_running_loop()
            self._task = asyncio.create_task(self._run(), name="analysis-worker")
            logger.info("Analysis worker started")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def enqueue(self, video_id: int) -> None:
        self._queue.put_nowait(video_id)

    def is_queued(self, video_id: int) -> bool:
        return video_id in self._running_ids

    def queued_position(self, video_id: int) -> int | None:
        items = list(self._queue._queue)  # noqa: SLF001  (asyncio.Queue has no peek API)
        try:
            return items.index(video_id) + 1
        except ValueError:
            return None

    async def _run(self) -> None:
        while True:
            video_id = await self._queue.get()
            self._running_ids.add(video_id)
            try:
                await asyncio.to_thread(self._process_sync, video_id)
            except Exception:
                logger.exception("Analysis failed for video %s", video_id)
                self._mark_failed(video_id)
            finally:
                self._running_ids.discard(video_id)
                self._queue.task_done()

    def _process_sync(self, video_id: int) -> None:
        from app.services.pipeline import AnalysisPipeline  # lazy: heavy imports

        pipeline = AnalysisPipeline(
            video_id=video_id,
            on_progress=self._emit_progress,
            on_event=self._emit_event,
            on_status=self._emit_status,
        )
        pipeline.run()

    # -- callbacks (called from worker thread; schedules broadcasts on the loop)
    def _loop_runner(self) -> asyncio.AbstractEventLoop | None:
        if self._loop is None or self._loop.is_closed():
            return None
        return self._loop

    def _emit_progress(self, video_id: int, payload: dict) -> None:
        logger.debug("progress video=%s %s", video_id, payload)
        if not settings.ws_broadcast_enabled:
            return
        loop = self._loop_runner()
        if loop is not None:
            try:
                loop.call_soon_threadsafe(
                    asyncio.ensure_future,
                    manager.broadcast("progress", video_id, payload),
                )
            except RuntimeError:
                pass  # no running loop (shutdown) — ignore

    def _emit_event(self, video_id: int, event_id: int) -> None:
        def _do() -> None:
            db = SessionLocal()
            try:
                from app.schemas import EventOut

                from app.api.utils import serialize_event

                event = serialize_event(db, event_id)
                if event is not None:
                    asyncio.create_task(manager.broadcast("event", video_id, event))
            finally:
                db.close()

        loop = self._loop_runner()
        if loop is not None:
            try:
                loop.call_soon_threadsafe(_do)
            except RuntimeError:
                pass

    def _emit_status(self, video_id: int, status: str) -> None:
        loop = self._loop_runner()
        if loop is not None:
            try:
                loop.call_soon_threadsafe(
                    asyncio.ensure_future,
                    manager.broadcast("status", video_id, status),
                )
            except RuntimeError:
                pass

    def _mark_failed(self, video_id: int) -> None:
        db = SessionLocal()
        try:
            video = db.get(Video, video_id)
            if video is not None:
                video.status = "failed"
                db.commit()
        finally:
            db.close()


worker = AnalysisWorker()
