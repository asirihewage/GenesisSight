"""First-run setup wizard API.

Drives the fresh-install flow:
  1. system check (GPU, writable storage, backend up),
  2. detection model download (YOLO weights),
  3. Ollama + VLM model install / pull (skippable),
  4. completion marker so the app opens the wizard only once.

All downloads run in background threads; progress is polled via
`GET /api/setup/status` (and shown in the UI).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/setup", tags=["setup"])

YOLO_URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11x.pt"
OLLAMA_EXE_URL = "https://ollama.com/download/OllamaSetup.exe"
OLLAMA_INSTALL_HINT = r"%LocalAppData%\Programs\Ollama\ollama.exe"


# ---------------------------------------------------------------------------
# Background-task state (module-level; one-shot per app run is fine)
# ---------------------------------------------------------------------------

_state_lock = threading.Lock()
_state = {
    "yolo": {"state": "idle", "done": 0, "total": 0, "error": None},  # idle|downloading|done|failed
    "ollama_pull": {"state": "idle", "error": None, "log": ""},      # idle|running|done|failed
    "ollama_install": {"state": "idle", "error": None},              # idle|downloading|launched|failed
}


def _marker() -> Path:
    return Path(settings.storage_dir) / "setup_complete.json"


def _cache_dir() -> Path:
    d = Path(settings.storage_dir) / "downloads"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ollama_binary() -> str | None:
    exe = shutil.which("ollama")
    if exe:
        return exe
    local = Path(os.path.expandvars(OLLAMA_INSTALL_HINT))
    return str(local) if local.exists() else None


def _models_list() -> list[str]:
    from app.services.ollama import OllamaClient

    client = OllamaClient()
    try:
        return client.list_models_sync()
    except Exception:
        return []


def _yolo_path() -> Path:
    return Path(settings.model_dir) / settings.yolo_model


def _yolo_ready() -> bool:
    p = _yolo_path()
    # yolo11x.pt is ~112 MB; anything close to that counts as a real weight file
    return p.exists() and p.stat().st_size > 90 * 1024 * 1024


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@router.get("/status")
def setup_status() -> dict:
    ollama_bin = _ollama_binary()
    try:
        models = _models_list()
    except Exception:
        models = []
    vlm_ready = settings.ollama_vlm_model in models
    marker = _marker()
    complete = marker.exists()
    skip_ollama = bool(marker.exists() and marker.read_text().find("ollama_skipped") >= 0)

    with _state_lock:
        yolo = dict(_state["yolo"])
        pull = dict(_state["ollama_pull"])
        inst = dict(_state["ollama_install"])
    if yolo["state"] in ("idle", "done") and not _yolo_ready():
        yolo["state"] = "idle"
        yolo["error"] = None
    if yolo["state"] == "downloading" and (_yolo_ready() or yolo["error"]):
        yolo["state"] = "done" if _yolo_ready() else "failed"

    return {
        "complete": complete,
        "ollama_skipped": skip_ollama,
        "system": {
            "backend_ok": True,
            "cuda": settings.cuda_available,
            "storage_writable": os.access(settings.storage_dir, os.W_OK),
            "model_dir": str(Path(settings.model_dir)),
            "storage_dir": str(Path(settings.storage_dir)),
        },
        "yolo": {
            "ready": _yolo_ready(),
            "path": str(_yolo_path()),
            "download": yolo,
        },
        "ollama": {
            "installed": ollama_bin is not None,
            "install_path": ollama_bin or str(os.path.expandvars(OLLAMA_INSTALL_HINT)),
            "reachable": vlm_ready or bool(_models_list()),
            "vlm_model": settings.ollama_vlm_model,
            "embed_model": settings.ollama_embed_model,
            "vlm_ready": vlm_ready,
            "installed_models": models,
            "pull": pull,
            "install": inst,
        },
    }


# ---------------------------------------------------------------------------
# YOLO weights download
# ---------------------------------------------------------------------------

@router.post("/yolo/download")
def download_yolo() -> dict:
    with _state_lock:
        if _state["yolo"]["state"] == "downloading":
            return {"ok": True, "started": False, "detail": "download already running"}
    if _yolo_ready():
        with _state_lock:
            _state["yolo"] = {"state": "done", "done": 0, "total": 0, "error": None}
        return {"ok": True, "started": False, "detail": "weights already present"}

    target = _yolo_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    def run() -> None:
        def progress(url: str, dest: Path) -> None:
            with httpx.stream("GET", url, follow_redirects=True, timeout=60) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                done = 0
                with _state_lock:
                    _state["yolo"]["total"] = total
                tmp = dest.with_suffix(dest.suffix + ".part")
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_bytes(1024 * 256):
                        fh.write(chunk)
                        done += len(chunk)
                        with _state_lock:
                            _state["yolo"]["done"] = done
                tmp.replace(dest)

        try:
            progress(YOLO_URL, target)
            with _state_lock:
                _state["yolo"]["state"] = "done"
        except Exception as exc:
            logger.exception("YOLO download failed")
            with _state_lock:
                _state["yolo"]["state"] = "failed"
                _state["yolo"]["error"] = str(exc)

    with _state_lock:
        _state["yolo"] = {"state": "downloading", "done": 0, "total": 0, "error": None}
    threading.Thread(target=run, name="yolo-download", daemon=True).start()
    return {"ok": True, "started": True}


# ---------------------------------------------------------------------------
# Ollama: pull VLM model
# ---------------------------------------------------------------------------

@router.post("/ollama/pull")
def ollama_pull() -> dict:
    ollama_bin = _ollama_binary()
    if not ollama_bin:
        return {"ok": False, "detail": "Ollama executable not found — install Ollama first"}
    with _state_lock:
        if _state["ollama_pull"]["state"] == "running":
            return {"ok": True, "started": False, "detail": "pull already running"}
        _state["ollama_pull"] = {"state": "running", "error": None, "log": ""}

    model = settings.ollama_vlm_model

    def run() -> None:
        try:
            proc = subprocess.Popen(
                [ollama_bin, "pull", model],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            lines: list[str] = []
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.strip()
                if line:
                    lines.append(line)
                    lines = lines[-40:]
                    with _state_lock:
                        _state["ollama_pull"]["log"] = "\n".join(lines)
            code = proc.wait()
            with _state_lock:
                _state["ollama_pull"]["state"] = "done" if code == 0 else "failed"
                if code != 0:
                    _state["ollama_pull"]["error"] = f"ollama pull exited with code {code}"
        except Exception as exc:
            logger.exception("ollama pull failed")
            with _state_lock:
                _state["ollama_pull"]["state"] = "failed"
                _state["ollama_pull"]["error"] = str(exc)

    threading.Thread(target=run, name="ollama-pull", daemon=True).start()
    return {"ok": True, "started": True}


# ---------------------------------------------------------------------------
# Ollama: download + launch installer
# ---------------------------------------------------------------------------

@router.post("/ollama/install")
def ollama_install() -> dict:
    if os.name != "nt":
        return {
            "ok": False,
            "detail": "Auto-install is Windows-only. Install Ollama from https://ollama.com/download",
        }
    with _state_lock:
        if _state["ollama_install"]["state"] == "downloading":
            return {"ok": True, "started": False, "detail": "installer download already running"}
        _state["ollama_install"] = {"state": "downloading", "error": None}

    dst = _cache_dir() / "OllamaSetup.exe"

    def run() -> None:
        try:
            with httpx.stream("GET", OLLAMA_EXE_URL, follow_redirects=True, timeout=60) as r:
                r.raise_for_status()
                tmp = dst.with_suffix(dst.suffix + ".part")
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_bytes(1024 * 256):
                        fh.write(chunk)
                tmp.replace(dst)
            os.startfile(str(dst))  # type: ignore[attr-defined]  # Windows only
            with _state_lock:
                _state["ollama_install"]["state"] = "launched"
        except Exception as exc:
            logger.exception("Ollama installer download failed")
            with _state_lock:
                _state["ollama_install"]["state"] = "failed"
                _state["ollama_install"]["error"] = str(exc)

    threading.Thread(target=run, name="ollama-install", daemon=True).start()
    return {"ok": True, "started": True}


# ---------------------------------------------------------------------------
# Completion / skip
# ---------------------------------------------------------------------------

@router.post("/complete")
def complete_setup(payload: dict | None = None) -> dict:
    body = payload or {}
    marker = _marker()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        '{\n  "completed": true,\n  "completed_at": "%s",\n  '
        % datetime.now(timezone.utc).isoformat()
        + '"ollama_skipped": %s\n}\n' % ("true" if body.get("ollama_skipped") else "false"),
        encoding="utf-8",
    )
    return {"ok": True}


@router.post("/reset")
def reset_setup() -> dict:
    marker = _marker()
    if marker.exists():
        marker.unlink()
    return {"ok": True}