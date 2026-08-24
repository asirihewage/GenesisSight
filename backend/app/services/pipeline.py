"""The AI analysis pipeline (orchestrator).

Runs entirely in a worker thread (via the AnalysisWorker). Pipeline:

    open video -> sample frames -> motion gate -> YOLO batch detection
    -> ByteTrack -> ReID person matching -> rule events + keyframes
    -> VLM enrichment (Ollama) -> persist + broadcast

Design notes:
- YOLO never runs on static frames (motion gate).
- Detection is batched (multiple motion frames per forward pass).
- ReID embeddings are cached per track and refreshed every N frames.
- The VLM only sees event keyframes, capped per video.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from typing import Any, Callable

import numpy as np

from app.config import settings
from app.database import SessionLocal
from app.models import Event, Person, Vehicle, Video
from app.services.detector import get_detector
from app.services.events import EventGenerator
from app.services.lpr import get_lpr_detector
from app.services.motion import MotionDetector
from app.services.ollama import ollama_client
from app.services.reid import ReIDEngine, get_reid_engine
from app.services.tracker import ByteTrackTracker, TrackedDetection
from app.services.visualizer import crop_person, crop_vehicle, draw_tracks, save_image

logger = logging.getLogger(__name__)

VLM_PRIORITY_TYPES = ("person_entered", "person_exited", "person_carrying", "person_running",
                      "vehicle_entered", "vehicle_exited")

STAGES = {
    "open": "Opening video",
    "detect": "Detecting motion and people",
    "track": "Tracking and identifying people",
    "vlm": "Analyzing events with AI vision model",
    "finalize": "Finalizing timeline",
}


class PersonMatcher:
    """In-memory person identity map: ReID embedding centroid per person id."""

    def __init__(self, reid: ReIDEngine, threshold: float) -> None:
        self.reid = reid
        self.threshold = threshold
        self.centroids: dict[int, np.ndarray] = {}
        self.counts: dict[int, int] = {}
        self._next_id = 1

    def match(self, embedding: np.ndarray | None) -> int | None:
        if embedding is None or not self.reid.enabled():
            pid = self._new_id()
            if embedding is not None:
                self._store(pid, embedding)
            return pid
        best_id, best_score = None, -1.0
        for pid, centroid in self.centroids.items():
            denom = float(np.linalg.norm(centroid) * np.linalg.norm(embedding))
            score = float(centroid @ embedding) / denom if denom > 0 else 0.0
            if score > best_score:
                best_id, best_score = pid, score
        if best_id is not None and best_score >= self.threshold:
            self._store(best_id, embedding)
            return best_id
        pid = self._new_id()
        self._store(pid, embedding)
        return pid

    def _store(self, pid: int, embedding: np.ndarray) -> None:
        count = self.counts.get(pid, 0)
        n = count + 1
        if count == 0:
            self.centroids[pid] = embedding.copy()
        else:
            self.centroids[pid] = (self.centroids[pid] * count + embedding) / n
        self.counts[pid] = n

    def _new_id(self) -> int:
        pid = self._next_id
        self._next_id += 1
        return pid


class AnalysisPipeline:
    def __init__(self, video_id: int,
                 on_progress: Callable[[int, dict], None],
                 on_event: Callable[[int, int], None],
                 on_status: Callable[[int, str], None]) -> None:
        self.video_id = video_id
        self.on_progress = on_progress
        self.on_event = on_event
        self.on_status = on_status

        # current-frame context for the event emit callback
        self._frame: np.ndarray | None = None
        self._tracks: list[TrackedDetection] = []
        self._labels: dict[int, int] = {}
        self._vlm_event_ids: list[int] = []
        self._person_rows: dict[int, int] = {}  # matcher pid -> Person.id
        self._vehicle_rows: dict[int, int] = {}  # matcher vid -> Vehicle.id
        self._db = None

    # ------------------------------------------------------------------
    def run(self) -> None:
        db = SessionLocal()
        self._db = db
        try:
            video = db.get(Video, self.video_id)
            if video is None:
                raise ValueError(f"Video {self.video_id} not found")
            video.status = "processing"
            video.error = None
            video.progress = 0.0
            db.commit()
            self._emit_status("processing")
            self._run_inner(db, video)
        except Exception as exc:
            logger.exception("Pipeline failed for video %s", self.video_id)
            try:
                video = db.get(Video, self.video_id)
                if video is not None:
                    video.status = "failed"
                    video.error = str(exc)[:2000]
                    db.commit()
            except Exception:
                db.rollback()
            self._emit_status("failed")
            raise
        finally:
            db.close()

    # ------------------------------------------------------------------
    def _run_inner(self, db, video) -> None:
        from app.services.video_io import VideoReader

        self._set_stage(db, video, "open", 0.0)

        reader = VideoReader(video.filepath)
        if not reader.open():
            raise RuntimeError(
                f"Could not open video file: {video.filepath} "
                f"({reader._fallback_error or 'unknown decoder'})"
            )
        try:
            fps = reader.fps or 25.0
            total = reader.frame_count or 0
            width = reader.width or 0
            height = reader.height or 0
            duration = reader.duration if reader.duration is not None else (
                total / fps if total > 0 else 0.0
            )
            video.fps, video.width, video.height, video.duration = fps, width, height, duration
            db.commit()

            step = max(1, int(round(fps / settings.target_fps)))
            n_sampled = total // step if total > 0 else None
            self._set_stage(db, video, "detect", 0.0)

            motion = MotionDetector(threshold_ratio=settings.motion_threshold)
            tracker = ByteTrackTracker()
            tracker.reset()
            reid = get_reid_engine()
            matcher = PersonMatcher(reid, settings.reid_match_threshold)
            track_person: dict[int, int] = {}
            generator = EventGenerator(
                video_id=self.video_id, frame_h=height, frame_w=width,
                emit=self._emit_event_dict, target_fps=settings.target_fps,
            )

            frame_idx = -1
            processed = 0
            batch: list[tuple[int, float, np.ndarray]] = []
            wall_start = time.perf_counter()
            last_report = 0.0

            def report() -> None:
                nonlocal last_report
                now = time.perf_counter()
                if now - last_report < 0.5:
                    return
                last_report = now
                elapsed = max(now - wall_start, 1e-6)
                fps_proc = processed / elapsed
                pct = self._progress_pct(processed, n_sampled, frame_idx, fps, duration)
                video.progress = pct
                video.fps_processed = fps_proc
                db.commit()
                self.on_progress(
                    self.video_id,
                    {"progress": round(pct, 1), "current_stage": video.current_stage,
                     "fps_processed": round(fps_proc, 1)},
                )

            while True:
                ok = False
                for _ in range(step):
                    ret, frame = reader.read()
                    frame_idx += 1
                    if ret:
                        ok = True
                if not ok:
                    break
                processed += 1
                ts = frame_idx / fps

                has_motion, _ = motion.analyze(frame)
                if has_motion:
                    batch.append((frame_idx, ts, frame))
                    if len(batch) >= settings.detect_batch_size:
                        self._flush(db, video, batch, tracker, reid, matcher,
                                    track_person, generator, wall_start, report)
                        batch = []
                report()

            if batch:
                self._flush(db, video, batch, tracker, reid, matcher,
                            track_person, generator, wall_start, report)

            # final flush: emit exits for any remaining tracks
            final_ts = (frame_idx + step) / fps if frame_idx >= 0 else 0.0
            self._set_stage(db, video, "track", video.progress)
            self._frame, self._tracks, self._labels = None, [], {}
            generator.process([], max(frame_idx, 0), final_ts)
            db.commit()

            # ---------------- VLM enrichment ----------------
            if settings.vlm_enabled:
                self._set_stage(db, video, "vlm", min(video.progress, 92.0))
                self._vlm_enrich(db, video, reid)

            # ---------------- finalize ----------------
            self._set_stage(db, video, "finalize", 99.0)
            self._finalize_persons(db, video)
            video.status = "completed"
            video.progress = 100.0
            video.current_stage = "Completed"
            db.commit()
            logger.info("Video %s analysis completed", self.video_id)
            self.on_progress(self.video_id, {"progress": 100.0, "current_stage": "Completed",
                                             "fps_processed": round(video.fps_processed, 1)})
            self._emit_status("completed")
        finally:
            reader.release()

    # ------------------------------------------------------------------
    def _flush(self, db, video, batch, tracker, reid, matcher, track_person,
               generator, wall_start, report) -> None:
        from app.services.detector import get_detector

        frames = [b[2] for b in batch]
        detections = get_detector().detect_batch(frames)

        for (frame_idx, ts, frame), dets in zip(batch, detections):
            tracks = tracker.update(dets)
            self._frame, self._tracks = frame, tracks

            # person identity assignment
            for t in tracks:
                if not t.person():
                    continue
                tid = t.track_id
                if tid not in track_person:
                    crop = crop_person(frame, t.xyxy)
                    if crop.size > 0:
                        emb = reid.embed_crops([crop])[0]
                    else:
                        emb = None
                    pid = matcher.match(emb)
                    track_person[tid] = pid
                    if pid not in self._person_rows:
                        # first time this identity is seen -> create a Person row
                        person = Person(
                            video_id=self.video_id, track_id=tid,
                            embedding=None if emb is None else [float(v) for v in emb],
                            first_seen=ts, last_seen=ts,
                        )
                        db.add(person)
                        db.flush()
                        if crop.size > 0:
                            person.thumbnail_path = save_image(
                                self.video_id, f"person_{person.id}.jpg", crop
                            )
                        self._person_rows[pid] = person.id
                    else:
                        # existing identity: keep track pointing at the same person
                        person = db.get(Person, self._person_rows[pid])
                        if person is not None:
                            person.last_seen = ts
                    generator.register_track(tid, self._person_rows[pid], ts)
                self._labels[tid] = self._person_rows[track_person[tid]]

            # vehicle tracking
            track_vehicle: dict[int, int] = {}
            lpr = get_lpr_detector()
            for t in tracks:
                if not t.vehicle():
                    continue
                tid = t.track_id
                if tid not in track_vehicle:
                    crop = crop_vehicle(frame, t.xyxy)
                    # Create vehicle record on first sighting
                    vehicle = Vehicle(
                        video_id=self.video_id, track_id=tid,
                        vehicle_type=t.class_name,
                        first_seen=ts, last_seen=ts,
                    )
                    db.add(vehicle)
                    db.flush()
                    if crop.size > 0:
                        vehicle.thumbnail_path = save_image(
                            self.video_id, f"vehicle_{vehicle.id}.jpg", crop
                        )
                        # Run LPR on vehicle crop
                        if lpr is not None:
                            plates = lpr.detect_plates(crop)
                            if plates:
                                best_plate = max(plates, key=lambda p: p.confidence)
                                vehicle.license_plate = best_plate.plate_text
                                logger.info("LPR detected plate '%s' (conf=%.2f) for vehicle %d",
                                           best_plate.plate_text, best_plate.confidence, vehicle.id)
                    track_vehicle[tid] = vehicle.id
                    self._vehicle_rows[vehicle.id] = vehicle.id
                    generator.register_vehicle_track(tid, vehicle.id, ts, t.class_name)
                else:
                    vehicle = db.get(Vehicle, track_vehicle[tid])
                    if vehicle is not None:
                        vehicle.last_seen = ts
                    generator.register_vehicle_track(tid, track_vehicle[tid], ts)

            generator.process(tracks, frame_idx, ts)
            db.commit()
            report()

        self._frame, self._tracks, self._labels = None, [], {}

    # ------------------------------------------------------------------
    def _emit_event_dict(self, event: dict[str, Any]) -> None:
        """Called synchronously by the EventGenerator with the current frame set."""
        frame = self._frame
        tracks = self._tracks
        metadata = event.get("metadata") or {}
        bbox = metadata.get("bbox")

        image_rel: str | None = None
        thumb_rel: str | None = None
        if frame is not None:
            vis = draw_tracks(frame, tracks, self._labels)
            suffix = uuid.uuid4().hex[:8]
            image_rel = save_image(self.video_id, f"event_{suffix}.jpg", vis)
            if bbox:
                crop = crop_person(frame, np.asarray(bbox, dtype=np.float32))
                if crop.size > 0:
                    thumb_rel = save_image(self.video_id, f"thumb_{suffix}.jpg", crop)

        is_vlm = event["event_type"] in VLM_PRIORITY_TYPES
        if is_vlm and len(self._vlm_event_ids) >= settings.vlm_max_events:
            is_vlm = False

        row = Event(
            video_id=self.video_id,
            person_id=event["person_id"],
            vehicle_id=event.get("vehicle_id"),
            timestamp=event["timestamp"],
            event_type=event["event_type"],
            description=event["description"],
            confidence=event["confidence"],
            image_path=image_rel,
            thumbnail_path=thumb_rel,
            objects=event.get("objects") or [],
            activity=event.get("activity"),
            details={**(metadata or {}), "vlm": is_vlm},
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        if is_vlm:
            self._vlm_event_ids.append(row.id)
        self.on_event(self.video_id, row.id)

    # ------------------------------------------------------------------
    def _vlm_enrich(self, db, video, reid) -> None:
        if not self._vlm_event_ids:
            return
        if not ollama_client.is_available_sync():
            logger.info("Skipping VLM enrichment (Ollama unavailable)")
            return
        done = 0
        total = len(self._vlm_event_ids)
        for event_id in self._vlm_event_ids:
            row = db.get(Event, event_id)
            if row is None:
                continue
            images: list[bytes] = []
            if row.image_path:
                from pathlib import Path

                p = Path(settings.storage_dir) / row.image_path
                if p.exists():
                    images.append(p.read_bytes())
            if not images:
                continue
            context = {
                "video": video.filename,
                "event_type": row.event_type,
                "ts_display": self._format_ts(row.timestamp),
                "rule_desc": row.description,
                "objects": row.objects or [],
            }
            result = ollama_client.analyze_event_sync(images, context)
            if result and result["confidence"] >= settings.vlm_confidence_min:
                row.description = result["description"]
                row.objects = result["objects"]
                row.activity = result["activity"]
                row.confidence = result["confidence"]
                db.commit()
            done += 1
            video.progress = min(92.0, 60.0 + (done / total) * 30.0)
            db.commit()
            self.on_progress(self.video_id, {"progress": round(video.progress, 1),
                                             "current_stage": video.current_stage,
                                             "fps_processed": round(video.fps_processed, 1)})

    # ------------------------------------------------------------------
    def _finalize_persons(self, db, video) -> None:
        from sqlalchemy import func

        max_ts_per_person = db.execute(
            db.query(Event.person_id, func.max(Event.timestamp))
            .filter(Event.video_id == self.video_id, Event.person_id.isnot(None))
            .group_by(Event.person_id)
        ).all()
        for person_id, max_ts in max_ts_per_person:
            person = db.get(Person, person_id)
            if person is not None and max_ts is not None:
                person.last_seen = max_ts
        db.commit()

    # ------------------------------------------------------------------
    @staticmethod
    def _progress_pct(processed: int, n_sampled: int | None, frame_idx: int,
                      fps: float, duration: float) -> float:
        if n_sampled:
            return min(95.0, processed / n_sampled * 100.0)
        if duration > 0 and frame_idx >= 0:
            return min(95.0, (frame_idx / fps) / duration * 100.0)
        return 0.0

    def _set_stage(self, db, video, key: str, progress: float | None = None) -> None:
        video.current_stage = STAGES[key]
        if progress is not None:
            video.progress = progress
        db.commit()
        self.on_progress(self.video_id, {"progress": round(video.progress, 1),
                                         "current_stage": video.current_stage,
                                         "fps_processed": round(video.fps_processed, 1)})

    @staticmethod
    def _format_ts(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _emit_status(self, status: str) -> None:
        self.on_status(self.video_id, status)
