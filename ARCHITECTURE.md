# Local AI CCTV Analyzer — Architecture

A fully local CCTV video analysis application: upload `.avi`/`.mp4`, detect motion, detect and
track people, re-identify the same person across the video, generate an AI-described event
timeline, and search it with natural language. One command starts everything and opens the
browser.

---

## 1. System overview

```
┌────────────────────────────────────────────────────────────────────────┐
│  Browser  ── http://localhost:3000                                      │
│    React + Vite + TypeScript + Tailwind + shadcn-style UI               │
│    React Query (REST)  +  WebSocket (live progress / events)            │
└───────────────┬────────────────────────────────────────────────────────┘
                │  /api/* (REST)        │  /ws (WebSocket)
                ▼                       ▼
┌────────────────────────────────────────────────────────────────────────┐
│  FastAPI backend  (uvicorn, port 8000 dev / 3000 prod)                  │
│    - REST routers: videos, persons, search, health                      │
│    - WebSocket manager (progress + event broadcasts)                    │
│    - SQLAlchemy ORM  →  SQLite (PostgreSQL-compatible schema)           │
│    - Static media mount: /media (frames, crops, event images)           │
│    - Analysis worker: single GPU pipeline consuming an async queue      │
└───────────────┬────────────────────────────────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────────────────────────────────┐
│  AI pipeline (PyTorch on RTX 5080 CUDA)                                 │
│  Frame extraction → Motion gate → YOLO11x batch detection → ByteTrack   │
│  → ReID (OSNet / ResNet fallback) → Person ID assignment → Event rules │
│  → Keyframe saving → Ollama Qwen2.5-VL VLM enrichment → embeddings      │
└───────────────┬────────────────────────────────────────────────────────┘
                │  http://localhost:11434
                ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Ollama (local LLM runtime) — qwen2.5vl:7b (vision) + embed model       │
└────────────────────────────────────────────────────────────────────────┘
```

**Hardware target:** MSI Vector 16 HX AI, RTX 5080 Laptop (16 GB VRAM), Windows 11, CUDA.

---

## 2. AI processing pipeline (stage-by-stage)

```
CCTV Video
   │  cv2.VideoCapture, target 3–4 FPS sampling
   ▼
Frame extraction
   │  skip strategy: process `fps / TARGET_FPS` stride
   ▼
Motion detection
   │  downscaled frame-difference + threshold ratio; skips static frames
   │  → this is the GPU-cost gate: YOLO never runs on static frames
   ▼
YOLO object detection
   │  ultralytics YOLO11x, batched (≤8 motion frames / inference call)
   │  classes: person + bags/cars/animals for context
   ▼
Person detection         (filter class_id == 0)
   ▼
ByteTrack tracking       (supervision ByteTrack, per-frame, lost-track buffer)
   ▼
Person ID assignment     (ReID embedding → cosine match → stable Person #N)
   ▼
Person ReID embedding    (OSNet x1_0 via torchreid; ResNet50 fallback;
                          per-track embedding cache, centroid per person)
   ▼
Event generation         (rule engine: entered / exited / appeared /
                          disappeared / moved / carrying / loitering / running)
   ▼
Important frames         (event frames + person crops saved as JPEG)
   ▼
Qwen2.5-VL analysis      (Ollama, batched keyframes only — never every frame)
   ▼
Human readable event     (rule description + VLM description + confidence)
```

### Smart cost control (Performance requirements)

- **Motion gate** — YOLO runs only on frames where the motion detector fires.
- **Batch inference** — multiple motion frames sent to YOLO in one forward pass.
- **VLM sparingly** — only event keyframes (≤ 40 per video), serialized, with retries.
- **Embedding cache** — one embedding per track computed on first sighting, refreshed
  every 25 frames; person centroids updated incrementally.
- **Single GPU queue** — one video processed at a time (asyncio queue); avoids OOM and
  keeps progress linear and predictable. Redis/Celery can replace the in-process queue
  (see `docker-compose.yml`) without touching the pipeline.

### Event rule engine

Track state (position history, velocity, carry state, loiter timer) drives rule events:

| event_type          | trigger                                                              |
|---------------------|----------------------------------------------------------------------|
| `person_entered`    | new track starting at/near frame edge                                |
| `person_exited`     | track ending at/near frame edge                                      |
| `person_appeared`   | new track appearing mid-frame                                        |
| `person_disappeared`| track lost mid-frame                                                 |
| `person_moved`      | displacement over a window > threshold (cooldown 8 s)                |
| `person_carrying`   | person bbox overlapping backpack/handbag/suitcase detection          |
| `person_loitering`  | stationary > 15 s                                                    |
| `person_running`    | normalized speed above threshold                                     |

Each event stores its frame → keyframe saved → description drafted by rules → enriched by VLM.

---

## 3. Backend API design

| Method | Route                            | Purpose                                   |
|--------|----------------------------------|-------------------------------------------|
| POST   | `/api/videos/upload`             | multipart upload → `{id, filename, status}`|
| POST   | `/api/videos/{id}/analyze`       | enqueue analysis                          |
| GET    | `/api/videos/{id}/status`        | `{progress, current_stage, fps_processed, status}` |
| GET    | `/api/videos`                    | list                                      |
| GET    | `/api/videos/{id}`               | detail                                    |
| GET    | `/api/videos/{id}/events`        | timeline events (filters: person, type)   |
| DELETE | `/api/videos/{id}`               | remove video + artifacts                  |
| GET    | `/api/persons?video_id=`         | detected people with thumbnails           |
| GET    | `/api/search?q=...`              | natural-language event search             |
| GET    | `/api/health`                    | CUDA / Ollama / model status              |
| WS     | `/ws`                            | `{type: progress|event|status}` broadcasts|

### WebSocket payloads

```jsonc
// progress
{ "type": "progress", "video_id": 1, "progress": 72.0,
  "current_stage": "Analyzing person identity", "fps_processed": 14.2 }
// event (new timeline item)
{ "type": "event", "video_id": 1, "event": { ...EventOut } }
// status change
{ "type": "status", "video_id": 1, "status": "completed" }
```

---

## 4. Database design (SQLAlchemy, SQLite → PostgreSQL compatible)

Uses portable column types (`JSON`, `Float`, `Integer`, `DateTime` with explicit indexes).
`DATABASE_URL` accepts any SQLAlchemy URL (e.g. `postgresql+psycopg://...`).

- **videos** — id, filename, filepath, duration, width, height, fps, status
  (`uploaded|queued|processing|completed|failed`), progress, current_stage,
  fps_processed, error, created_at.
- **persons** — id, video_id (nullable → future cross-video matching), track_id,
  embedding (JSON float list), first_seen, last_seen, thumbnail_path, created_at.
- **events** — id, video_id, person_id, timestamp (seconds), event_type, description,
  image_path, thumbnail_path, confidence, objects (JSON), activity, metadata (JSON:
  bbox, frame_idx), embedding (JSON, for search), created_at.

---

## 5. Frontend design

Single-page dashboard, dark theme, shadcn/ui-style components (hand-rolled `components/ui`
following shadcn conventions: `cn()`, `cva`, CSS-variable tokens — no CLI dependency).

- **Dashboard** — stats, video cards (status/progress), recent events.
- **Upload** — drag & drop `.avi`/`.mp4`, auto-start analysis toggle.
- **Video Analysis** — live status (WS), filterable event timeline grouped by person,
  thumbnails, person list with same-person tracking.
- **Search** — natural language query → ranked events with scores.
- **Settings** — health panel: CUDA/GPU name, Ollama status + models, storage usage.

`vite.config.ts` proxies `/api`, `/ws`, `/media` to the backend, so dev and prod behave
identically. In prod mode (`start.py --prod`) FastAPI serves the built frontend on :3000.

---

## 6. Search (natural language)

1. Query embedded via Ollama embeddings API (default `nomic-embed-text`).
2. Event descriptions embedded lazily on first search (cached in `events.embedding`).
3. Cosine similarity ranking → top results with scores.
4. If Ollama is down: char n-gram TF cosine fallback (pure numpy, fully local).

---

## 7. Deployment / startup

- `python start.py` — validates env, starts backend (uvicorn) + frontend (Vite dev on
  :3000, auto `npm install`), waits for health, opens browser.
- `python start.py --prod` — builds frontend, FastAPI serves it on :3000.
- `CCTV Analyzer.exe` — PyInstaller launcher (`build_exe.py`).
- `docker-compose.yml` — optional Redis for the queue (profile `redis`).

## 8. Configuration (`.env`)

`API_HOST`, `API_PORT`, `FRONTEND_PORT`, `STORAGE_DIR`, `DATABASE_URL`, `MODEL_DIR`,
`YOLO_MODEL` (`yolo11x.pt`), `REID_ENGINE` (`osnet|resnet|disabled`), `OLLAMA_BASE_URL`,
`OLLAMA_VLM_MODEL` (`qwen2.5vl:7b`), `OLLAMA_EMBED_MODEL`, `TARGET_FPS`, `DETECT_BATCH_SIZE`,
`REID_MATCH_THRESHOLD`, `VLM_MAX_EVENTS`, `LOG_LEVEL`.

## 9. Failure strategy (no fake AI)

Every AI component is a clean adapter with a real, working fallback:

- YOLO missing weights → auto-downloaded by ultralytics into `models/`.
- OSNet unavailable → honest fallback to ResNet50 embeddings (still real person matching).
- Ollama not running → pipeline continues; events keep rule-based descriptions; Settings
  shows the problem. No silent placeholders.
