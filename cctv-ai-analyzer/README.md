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

---

## Requirements

| Component | Requirement |
|---|---|
| OS | Windows 11 |
| GPU | NVIDIA RTX 5080 (16 GB VRAM) — any CUDA GPU works |
| Python | **3.11 – 3.13** recommended (3.14 may lack prebuilt wheels) |
| Node.js | 18+ (frontend tooling) |
| CUDA | Driver already on your system (610+) |

---

## 1. Install

```powershell
# (recommended) create a venv — avoids touching your system Python
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 1) PyTorch FIRST with CUDA 12.8 support (required for RTX 50-series / Blackwell)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

# 2) Everything else
pip install -r requirements.txt

# 3) Ollama (vision model + embeddings)
#    install from https://ollama.com, then:
ollama pull qwen2.5vl:7b
ollama pull nomic-embed-text
```

Optional — higher-quality person identity matching with OSNet weights:

```powershell
pip install torchreid
# download OSNet re-id weights (osnet_x1_0_imagenet.pth) from the torchreid
# GitHub release into models/, or set REID_WEIGHTS in .env.
# Without weights the app automatically uses ResNet50 embeddings (still real
# person matching).
```

First analysis auto-downloads `yolo11x.pt` (≈ 250 MB) into `models/`.

## 2. Run

```powershell
python start.py
```

That starts the FastAPI backend (:8000), the React UI (:3000), waits for health
checks and opens your browser automatically. `Ctrl+C` shuts everything down.

| Option | Effect |
|---|---|
| `python start.py --prod` | builds the frontend and serves it from the backend on one port (:3000) |
| `python start.py --no-browser` | don't open the browser |
| `python start.py --port 3100` | override the UI port (prod) |

### Standalone exe (optional)

```powershell
cd frontend && npm install && npm run build
pip install pyinstaller
python ..\build_exe.py      # -> dist-exe/CCTV Analyzer/CCTV Analyzer.exe
```

Double-click the exe; it launches the API, serves the built UI and opens the browser on :3000.

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
| SQLite "database is locked" | One video processes at a time by design; the queue serializes work |
| Ports in use | Change `API_PORT` / `FRONTEND_PORT` in `.env` |
| Exe / bundle quirks | Storage and models live next to the exe (`storage/`, `models/`) |

## Project layout

```
cctv-ai-analyzer/
├── start.py               one-command launcher (backend + frontend + browser)
├── build_exe.py           PyInstaller launcher build
├── docker-compose.yml     optional Redis/GPU deployment
├── ARCHITECTURE.md        full design document
├── backend/               FastAPI + AI pipeline
│   └── app/
│       ├── api/           videos, persons, search, health, WebSocket
│       ├── core/          ws manager, analysis worker (queue)
│       └── services/      motion, detector (YOLO), tracker (ByteTrack),
│                          reid (OSNet/ResNet50), events (rules),
│                          ollama (Qwen2.5-VL), pipeline (orchestrator)
├── frontend/              React + Vite + TS + Tailwind + shadcn-style UI
├── models/                weights (auto-downloaded)
└── storage/               uploads / frames / images / database
```

## Performance notes (RTX 5080)

- Motion gate skips static frames → YOLO runs only where it matters.
- Up to 8 motion frames per YOLO forward pass (batched inference).
- One video at a time on the GPU (asyncio queue) — predictable, no VRAM thrash.
- Embeddings cached per track; VLM calls capped and serialized.
