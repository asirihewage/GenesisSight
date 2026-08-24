"""Event rule engine.

Maintains per-track state (position history, velocity, carrying, loitering) and
emits typed events with rule-based descriptions. Keyframes are flagged for the
VLM enrichment stage.

Deduplication is *person-level*, not track-level: ByteTrack may break a single
person's track into several track ids (occlusion, low frame rate), and cooldowns
keyed by person id keep the timeline clean while still capturing every real
event (re-entry, exit, carrying, loitering).

Event types: person_entered, person_exited, person_appeared, person_disappeared,
person_moved, person_carrying, person_loitering, person_running,
vehicle_entered, vehicle_exited, vehicle_appeared, vehicle_disappeared.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from app.services.detector import BAG_CLASSES
from app.services.tracker import TrackedDetection

logger = logging.getLogger(__name__)

_EDGE_MARGIN_RATIO = 0.06

# per-person cooldowns (seconds) — track churn must not duplicate events
_PERSON_COOLDOWNS = {
    "person_entered": 8.0,
    "person_exited": 8.0,
    "person_appeared": 8.0,
    "person_disappeared": 8.0,
    "person_moved": 10.0,
    "person_loitering": 25.0,
    "person_running": 15.0,
    "person_carrying": 30.0,
}

# per-vehicle cooldowns
_VEHICLE_COOLDOWNS = {
    "vehicle_entered": 8.0,
    "vehicle_exited": 8.0,
    "vehicle_appeared": 8.0,
    "vehicle_disappeared": 8.0,
}
_MOVE_DIST_RATIO = 0.25    # bbox width fraction to call it "moved"
_LOITER_SECONDS = 12.0
_RUN_SPEED_RATIO = 0.6     # bbox heights per second to call it "running"
_KEYFRAME_PRIORITY = ("person_entered", "person_exited", "person_carrying", "person_running",
                      "vehicle_entered", "vehicle_exited")


@dataclass
class TrackState:
    track_id: int
    person_id: int | None = None
    vehicle_id: int | None = None
    first_seen: float = 0.0
    last_seen: float = 0.0
    seen_frames: int = 0
    positions: deque = field(default_factory=lambda: deque(maxlen=60))
    center: tuple[float, float] | None = None
    prev_center: tuple[float, float] | None = None
    stationary_since: float | None = None
    carrying: set[int] = field(default_factory=set)
    carrying_event_fired: bool = False
    exited_fired: bool = False
    keyframes: list[int] = field(default_factory=list)  # frame indices for VLM
    avg_score: float = 0.0


@dataclass
class VehicleTrackState:
    track_id: int
    vehicle_id: int | None = None
    first_seen: float = 0.0
    last_seen: float = 0.0
    seen_frames: int = 0
    positions: deque = field(default_factory=lambda: deque(maxlen=60))
    center: tuple[float, float] | None = None
    prev_center: tuple[float, float] | None = None
    exited_fired: bool = False
    keyframes: list[int] = field(default_factory=list)
    avg_score: float = 0.0
    vehicle_type: str | None = None
    color: str | None = None


class EventGenerator:
    def __init__(self, video_id: int, frame_h: int, frame_w: int,
                 emit: Callable[[dict], None], target_fps: float) -> None:
        self.video_id = video_id
        self.frame_h = frame_h
        self.frame_w = frame_w
        self.emit = emit
        self.target_fps = target_fps
        self.tracks: dict[int, TrackState] = {}
        self.vehicle_tracks: dict[int, VehicleTrackState] = {}
        # person_id -> {event_type -> last ts}
        self._person_last: dict[int, dict[str, float]] = {}
        self._person_carrying: dict[int, bool] = {}
        # vehicle_id -> {event_type -> last ts}
        self._vehicle_last: dict[int, dict[str, float]] = {}

    # ------------------------------------------------------------------
    def register_track(self, track_id: int, person_id: int, ts: float) -> None:
        """Attach a ReID-assigned person id (DB Person.id) to a track."""
        state = self.tracks.setdefault(
            track_id, TrackState(track_id=track_id, first_seen=ts, last_seen=ts)
        )
        state.person_id = person_id

    def register_vehicle_track(self, track_id: int, vehicle_id: int, ts: float, vehicle_type: str | None = None) -> None:
        """Attach a vehicle id (DB Vehicle.id) to a track."""
        state = self.vehicle_tracks.setdefault(
            track_id, VehicleTrackState(track_id=track_id, first_seen=ts, last_seen=ts, vehicle_type=vehicle_type)
        )
        state.vehicle_id = vehicle_id

    def process(self, tracks: list[TrackedDetection], frame_idx: int, ts: float) -> None:
        seen = set()
        vehicle_seen = set()
        for t in tracks:
            if t.person():
                seen.add(t.track_id)
                state = self.tracks.setdefault(
                    t.track_id, TrackState(track_id=t.track_id, first_seen=ts, last_seen=ts)
                )
                state.last_seen = ts
                state.seen_frames += 1
                state.avg_score = (state.avg_score * (state.seen_frames - 1) + float(t.confidence)) / state.seen_frames
                center = ((t.xyxy[0] + t.xyxy[2]) / 2.0, (t.xyxy[1] + t.xyxy[3]) / 2.0)
                state.prev_center = state.center
                state.center = center
                state.positions.append((ts, center))

                self._maybe_keyframe(state, frame_idx)
                self._check_carrying(state, t, tracks, ts, frame_idx)

                if state.seen_frames == 1:
                    self._handle_appear(state, ts, t, frame_idx)
                else:
                    self._check_motion(state, ts, frame_idx, t)
            elif t.vehicle():
                vehicle_seen.add(t.track_id)
                state = self.vehicle_tracks.setdefault(
                    t.track_id, VehicleTrackState(track_id=t.track_id, first_seen=ts, last_seen=ts, vehicle_type=t.class_name)
                )
                state.last_seen = ts
                state.seen_frames += 1
                state.avg_score = (state.avg_score * (state.seen_frames - 1) + float(t.confidence)) / state.seen_frames
                center = ((t.xyxy[0] + t.xyxy[2]) / 2.0, (t.xyxy[1] + t.xyxy[3]) / 2.0)
                state.prev_center = state.center
                state.center = center
                state.positions.append((ts, center))

                if state.seen_frames == 1:
                    self._handle_vehicle_appear(state, ts, t, frame_idx)

        self._handle_missing(seen, ts, frame_idx)
        self._handle_vehicle_missing(vehicle_seen, ts, frame_idx)

    # ------------------------------------------------------------------
    def _handle_appear(self, state: TrackState, ts: float, t: TrackedDetection, frame_idx: int) -> None:
        x1, y1, x2, y2 = t.xyxy
        near_edge = (
            x1 < self.frame_w * _EDGE_MARGIN_RATIO
            or x2 > self.frame_w * (1 - _EDGE_MARGIN_RATIO)
            or y1 < self.frame_h * _EDGE_MARGIN_RATIO
            or y2 > self.frame_h * (1 - _EDGE_MARGIN_RATIO)
        )
        if near_edge:
            if self._can_fire_person(state.person_id, "person_entered", ts):
                self._emit(
                    state, "person_entered", ts, frame_idx, t,
                    "Person entered the frame area",
                    confidence=float(t.confidence),
                )
        else:
            if self._can_fire_person(state.person_id, "person_appeared", ts):
                self._emit(
                    state, "person_appeared", ts, frame_idx, t,
                    "Person appeared inside the frame area",
                    confidence=float(t.confidence),
                )

    def _handle_vehicle_appear(self, state: VehicleTrackState, ts: float, t: TrackedDetection, frame_idx: int) -> None:
        x1, y1, x2, y2 = t.xyxy
        near_edge = (
            x1 < self.frame_w * _EDGE_MARGIN_RATIO
            or x2 > self.frame_w * (1 - _EDGE_MARGIN_RATIO)
            or y1 < self.frame_h * _EDGE_MARGIN_RATIO
            or y2 > self.frame_h * (1 - _EDGE_MARGIN_RATIO)
        )
        vehicle_type = state.vehicle_type or t.class_name
        if near_edge:
            if self._can_fire_vehicle(state.vehicle_id, "vehicle_entered", ts):
                self._emit_vehicle(
                    state, "vehicle_entered", ts, frame_idx, t,
                    f"{vehicle_type.capitalize()} entered the frame area",
                    confidence=float(t.confidence),
                    vehicle_type=vehicle_type,
                )
        else:
            if self._can_fire_vehicle(state.vehicle_id, "vehicle_appeared", ts):
                self._emit_vehicle(
                    state, "vehicle_appeared", ts, frame_idx, t,
                    f"{vehicle_type.capitalize()} appeared inside the frame area",
                    confidence=float(t.confidence),
                    vehicle_type=vehicle_type,
                )

    def _check_motion(self, state: TrackState, ts: float, frame_idx: int, t: TrackedDetection) -> None:
        if state.center is None or state.prev_center is None:
            return
        dx = state.center[0] - state.prev_center[0]
        dy = state.center[1] - state.prev_center[1]
        dist = float(np.hypot(dx, dy))
        bw = float(t.xyxy[2] - t.xyxy[0])
        bh = float(t.xyxy[3] - t.xyxy[1])

        # loitering
        if dist < max(2.0, bw * 0.02):
            if state.stationary_since is None:
                state.stationary_since = ts
            elif ts - state.stationary_since >= _LOITER_SECONDS and self._can_fire_person(state.person_id, "person_loitering", ts):
                self._emit(
                    state, "person_loitering", ts, frame_idx, t,
                    "Person was stationary for an extended period",
                    confidence=float(t.confidence),
                )
        else:
            state.stationary_since = None

        # running
        if bh > 0:
            speed = dist * self.target_fps / bh  # bbox heights per second
            if speed > _RUN_SPEED_RATIO and self._can_fire_person(state.person_id, "person_running", ts):
                self._emit(
                    state, "person_running", ts, frame_idx, t,
                    "Person was moving quickly",
                    confidence=float(t.confidence),
                )

        # moved (window displacement)
        if state.positions:
            first_pos = state.positions[0][1]
            total = float(np.hypot(state.center[0] - first_pos[0], state.center[1] - first_pos[1]))
            if total > bw * _MOVE_DIST_RATIO and self._can_fire_person(state.person_id, "person_moved", ts):
                direction = self._direction(first_pos, state.center)
                self._emit(
                    state, "person_moved", ts, frame_idx, t,
                    f"Person moved {direction}",
                    confidence=float(t.confidence),
                )
                state.positions.clear()

    def _check_carrying(
        self, state: TrackState, t: TrackedDetection, all_tracks: list[TrackedDetection],
        ts: float, frame_idx: int,
    ) -> None:
        carrying_now = set()
        px1, py1, px2, py2 = [float(v) for v in t.xyxy]
        pbox_w, pbox_h = px2 - px1, py2 - py1
        for other in all_tracks:
            if int(other.class_id) not in BAG_CLASSES:
                continue
            bx1, by1, bx2, by2 = [float(v) for v in other.xyxy]
            ox1, oy1 = max(px1, bx1), max(py1, by1)
            ox2, oy2 = min(px2, bx2), min(py2, by2)
            if ox2 > ox1 and oy2 > oy1 and (ox2 - ox1) * (oy2 - oy1) > 0.25 * pbox_w * pbox_h:
                carrying_now.add(int(other.class_id))
        state.carrying = carrying_now

        was_carrying = self._person_carrying.get(state.person_id, False)
        if carrying_now and not was_carrying and self._can_fire_person(state.person_id, "person_carrying", ts):
            names = sorted(_BAG_NAME.get(c, str(c)) for c in carrying_now)
            self._emit(
                state, "person_carrying", ts, frame_idx, t,
                f"Person was carrying a {', '.join(names)}",
                confidence=float(t.confidence),
                objects=names,
            )
            self._person_carrying[state.person_id] = True
        elif not carrying_now:
            self._person_carrying[state.person_id] = False

    def _handle_missing(self, seen: set[int], ts: float, frame_idx: int) -> None:
        grace = 90 / self.target_fps  # allow brief tracking gaps
        for tid, state in list(self.tracks.items()):
            if tid in seen or state.exited_fired:
                continue
            if ts - state.last_seen > grace:
                if self._last_was_near_edge(state):
                    if self._can_fire_person(state.person_id, "person_exited", ts):
                        self._emit(
                            state, "person_exited", ts, frame_idx, None,
                            "Person exited the frame area",
                            confidence=state.avg_score or 0.6,
                        )
                else:
                    if self._can_fire_person(state.person_id, "person_disappeared", ts):
                        self._emit(
                            state, "person_disappeared", ts, frame_idx, None,
                            "Person disappeared from the frame",
                            confidence=state.avg_score or 0.6,
                        )
                state.exited_fired = True
                state.positions.clear()

    def _handle_vehicle_missing(self, seen: set[int], ts: float, frame_idx: int) -> None:
        grace = 90 / self.target_fps
        for tid, state in list(self.vehicle_tracks.items()):
            if tid in seen or state.exited_fired:
                continue
            if ts - state.last_seen > grace:
                vehicle_type = state.vehicle_type or "vehicle"
                if self._last_was_near_edge(state):
                    if self._can_fire_vehicle(state.vehicle_id, "vehicle_exited", ts):
                        self._emit_vehicle(
                            state, "vehicle_exited", ts, frame_idx, None,
                            f"{vehicle_type.capitalize()} exited the frame area",
                            confidence=state.avg_score or 0.6,
                            vehicle_type=vehicle_type,
                        )
                else:
                    if self._can_fire_vehicle(state.vehicle_id, "vehicle_disappeared", ts):
                        self._emit_vehicle(
                            state, "vehicle_disappeared", ts, frame_idx, None,
                            f"{vehicle_type.capitalize()} disappeared from the frame",
                            confidence=state.avg_score or 0.6,
                            vehicle_type=vehicle_type,
                        )
                state.exited_fired = True
                state.positions.clear()

    def _last_was_near_edge(self, state: TrackState | VehicleTrackState) -> bool:
        if not state.positions:
            return False
        _, (cx, cy) = state.positions[-1]
        return (
            cx < self.frame_w * _EDGE_MARGIN_RATIO
            or cx > self.frame_w * (1 - _EDGE_MARGIN_RATIO)
            or cy < self.frame_h * _EDGE_MARGIN_RATIO
            or cy > self.frame_h * (1 - _EDGE_MARGIN_RATIO)
        )

    # ------------------------------------------------------------------
    def _can_fire_person(self, person_id: int | None, event_type: str, ts: float) -> bool:
        window = _PERSON_COOLDOWNS[event_type]
        last = self._person_last.get(person_id, {}).get(event_type, -1e9)
        if ts - last < window:
            return False
        self._person_last.setdefault(person_id, {})[event_type] = ts
        return True

    def _can_fire_vehicle(self, vehicle_id: int | None, event_type: str, ts: float) -> bool:
        window = _VEHICLE_COOLDOWNS[event_type]
        last = self._vehicle_last.get(vehicle_id, {}).get(event_type, -1e9)
        if ts - last < window:
            return False
        self._vehicle_last.setdefault(vehicle_id, {})[event_type] = ts
        return True

    def _maybe_keyframe(self, state: TrackState, frame_idx: int) -> None:
        if state.seen_frames == 1:
            state.keyframes.append(frame_idx)
        elif state.seen_frames % 60 == 0:  # every ~20s at 3fps
            state.keyframes.append(frame_idx)

    def _emit(self, state: TrackState, event_type: str, ts: float, frame_idx: int,
              track: TrackedDetection | None, description: str,
              confidence: float, objects: list[str] | None = None) -> None:
        if event_type in _KEYFRAME_PRIORITY:
            state.keyframes.append(frame_idx)
        self.emit(
            {
                "video_id": self.video_id,
                "person_id": state.person_id,
                "vehicle_id": None,
                "track_id": state.track_id,
                "timestamp": ts,
                "event_type": event_type,
                "description": description,
                "confidence": confidence,
                "objects": objects or [],
                "activity": None,
                "metadata": {
                    "frame_idx": frame_idx,
                    "bbox": None if track is None else track.xyxy.tolist(),
                    "rule_based": True,
                },
            }
        )

    def _emit_vehicle(self, state: VehicleTrackState, event_type: str, ts: float, frame_idx: int,
              track: TrackedDetection | None, description: str,
              confidence: float, vehicle_type: str | None = None) -> None:
        if event_type in _KEYFRAME_PRIORITY:
            state.keyframes.append(frame_idx)
        self.emit(
            {
                "video_id": self.video_id,
                "person_id": None,
                "vehicle_id": state.vehicle_id,
                "track_id": state.track_id,
                "timestamp": ts,
                "event_type": event_type,
                "description": description,
                "confidence": confidence,
                "objects": [vehicle_type] if vehicle_type else [],
                "activity": None,
                "metadata": {
                    "frame_idx": frame_idx,
                    "bbox": None if track is None else track.xyxy.tolist(),
                    "rule_based": True,
                    "vehicle_type": vehicle_type,
                },
            }
        )

    @staticmethod
    def _direction(a: tuple[float, float], b: tuple[float, float]) -> str:
        dx, dy = b[0] - a[0], b[1] - a[1]
        if abs(dx) > abs(dy) * 1.4:
            return "right" if dx > 0 else "left"
        if abs(dy) > abs(dx) * 1.4:
            return "down" if dy > 0 else "up"
        return ""


_BAG_NAME = {24: "backpack", 25: "umbrella", 26: "handbag", 28: "suitcase"}
