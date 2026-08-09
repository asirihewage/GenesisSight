# Local AI CCTV Analyzer

Fully-local CCTV video analysis: upload `.avi`/`.mp4`, detect motion, detect and track people,
**identify the same person across the video**, generate an AI-described searchable event
timeline — all on your own GPU. No cloud, no uploads.

```
09:12:22 ────────────────  Person #12 entered        [camera frame]
09:15:44 ────────────────  Person #12 moved right    [camera frame]
09:30:10 ────────────────  Person #12 exited         [camera frame]
```

## Pipeline

```
Frame extraction → Motion gate → YOLO11x (batched) → ByteTrack → Re-ID (OSNet/ResNet50)
→ Person ID assignment → Rule events + keyframes → Qwen2.5-VL description → Searchable timeline
```

The vision model (Qwen2.5-VL via Ollama) only receives **important event keyframes**
(enter/exit/carrying/running + periodic), capped at 40 per video — it never sees every frame.

Real DVR/NVR recordings are handled out of the box: if OpenCV can't decode a clip
(HEVC/H.264/MJPEG with non-standard codec tags), the app falls back to FFmpeg and,
if necessary, rewrites the broken codec tag in a temporary copy before decoding.

---

## Requirements

| Component | Requirement |
|---|---|
| OS | Windows 11 |
| GPU | NVIDIA RTX 5080 (16 GB VRAM) — any CUDA GPU works |
| Python | 3.11 – 3.14 (verified on 3.14.2 with cu128 wheels) |
| Node.js | 18+ (only needed to build the UI / installer) |
| CUDA | Driver already on your system (610+) |

---

## 1. Install — the app

The simplest way is the **installer**: it bundles the backend (Python + AI stack),
the UI and Electron into one setup file with an installation wizard.

1. Get `CCTV Analyzer Setup <version>.exe` (built in `release/`, see *Build the installer* below).
2. Run it — the NSIS wizard walks you through install location and shortcuts.
3. Launch **CCTV Analyzer** from the Start menu or desktop.

First run: the app starts its private backend on a free port, seeds the YOLO weights
into your user profile (one-time) and opens the UI window. User data lives in
`%APPDATA%\CCTV Analyzer\` (storage, models, logs) — uninstalling leaves it intact.
First launch loads torch + CUDA: allow ~20–60 s before the window appears.

### Build the installer from source

```powershell
# 1) backend deps (venv recommended)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
pip install pyinstaller

# 2) one-command build:  frontend → backend bundle → NSIS installer
python build_app.py

# 3) optional extras
ollama pull qwen2.5vl:7b            # vision descriptions (default VLM)
ollama pull nomic-embed-text        # semantic search embeddings
```

Output: `release/CCTV Analyzer Setup 1.0.0.exe` (double-click to install).

### Build steps individually

| Step | Command | Output |
|---|---|---|
| Frontend | `cd frontend && npm install && npm run build` | `frontend/dist/` |
| Backend bundle | `python build_exe.py` | `dist-exe/backend/` (PyInstaller onedir) |
| Installer | `cd electron && npm install && npm run dist` | `release/CCTV Analyzer Setup *.exe` |

`build_app.py` runs all three (`--skip-frontend`, `--skip-backend`, `--installer-only` for reuse).

---

## 2. Run without installing (developers)

```powershell
python start.py
```

That starts the FastAPI backend (:8000), the React UI (:3000), waits for health
checks and opens your browser automatically. `Ctrl+C` shuts everything down.

| Option | Effect |
|---|---|
| `python start.py --prod` | builds the frontend and serves it from the backend on one port |
| `python start.py --no-browser` | don't open the browser |
| `python start.py --port 3100` | override the UI port (prod) |

Electron in dev mode (uses a backend you started yourself):

```powershell
cd electron && npm install && npm start -- --dev        # backend on :8000
```

> Sandboxed machines may refuse python-written `.exe` files inside the repo
> (Path permission quirks). `build_exe.py` builds PyInstaller artifacts in the
> temp dir and stages the finished bundle into `dist-exe/` — keep that in mind
> if the build fails with `Access denied`.

---

## 3. Use it

1. **Upload** — drag a `.avi`/`.mp4` onto the Upload page (analysis auto-starts).
2. **Watch** — the analysis page shows live progress, current AI stage and fps via WebSocket.
3. **Timeline** — events grouped by time with frame thumbnails, person numbers, confidence.
   Filter by person or event type; the person chips show every identity found (Re-ID keeps
   the same number for the same person throughout the video).
4. **Search** — ask in plain English: *"find person carrying a backpack"*. Uses local
   Ollama embeddings (keyword fallback if Ollama is off).

## API

Interactive docs at `http://localhost:8000/docs`:

```
POST /api/videos/upload          upload CCTV file -> {id, filename, status}
POST /api/videos/{id}/analyze    start analysis
GET  /api/videos/{id}/status     {progress, current_stage, fps_processed}
GET  /api/videos/{id}/events     timeline events
GET  /api/videos                 list
GET  /api/persons                detected people
GET  /api/search?q=…             natural language event search
GET  /api/health                 CUDA / Ollama / models status
WS   /ws                         live progress + events
```

---

## Configuration (`.env`)

Copy `.env.example` to `.env` to customize: ports, `DATABASE_URL` (SQLite by default,
PostgreSQL-compatible schema), YOLO model, ReID engine (`osnet | resnet | disabled`),
sampling rate (`TARGET_FPS`), VLM limits, Ollama model names.

## Troubleshooting

| Problem | Fix |
|---|---|
| `CUDA not available` | Install the cu128 torch build (step 1). Verify: `python -c "import torch; print(torch.cuda.is_available())"` |
| No VLM descriptions | Ollama not running / model not pulled — see Settings → AI models |
| Slow analysis | Reduce `TARGET_FPS` (e.g. 1.0); long static recordings are skipped by the motion gate anyway |
| DVR clip doesn't decode | The ffmpeg fallback covers HEVC/MJPEG/MPEG4; a failed video row shows why. Check `%APPDATA%\CCTV Analyzer\logs\backend.log` in the installed app |
| SQLite "database is locked" | One video processes at a time by design; the queue serializes work |
| Installer blocked by SmartScreen | Run the installer and choose "More info → Run anyway" (unsigned build) |
| Backend fails to start in the app | See `%APPDATA%\CCTV Analyzer\logs\backend.log` |

## Project layout

```
├── start.py               one-command dev launcher (backend + frontend + browser)
├── build_app.py           full installer build (frontend → backend exe → NSIS)
├── build_exe.py           PyInstaller backend bundle (dist-exe/backend)
├── electron/              Electron shell + electron-builder (NSIS wizard installer)
│   ├── main.cjs           spawns the bundled backend, health-gates, opens the window
│   ├── preload.cjs        minimal contextBridge API
│   └── build/             app icons
├── docker-compose.yml     optional Redis/GPU deployment
├── ARCHITECTURE.md        full design document
├── backend/               FastAPI + AI pipeline
│   └── app/
│       ├── api/           videos, persons, search, health, WebSocket
│       ├── core/          ws manager, analysis worker (queue)
│       └── services/      motion, detector (YOLO), tracker (ByteTrack),
│                          reid (OSNet/ResNet50), video_io (ffmpeg fallback),
│                          events (rules), ollama (Qwen2.5-VL), pipeline (orchestrator)
├── frontend/              React + Vite + TS + Tailwind + shadcn-style UI
├── models/                weights (auto-downloaded)
└── storage/               uploads / frames / images / database
```

## Performance notes (RTX 5080)

- Motion gate skips static frames → YOLO runs only where it matters.
- Up to 8 motion frames per YOLO forward pass (batched inference).
- One video at a time on the GPU (asyncio queue) — predictable, no VRAM thrash.
- Embeddings cached per track; VLM calls capped and serialized.
- Large DVR frames (e.g. 1920×3240 HEVC) decode ~50 fps even on the ffmpeg fallback.