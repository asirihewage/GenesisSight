"""Local AI CCTV Analyzer — one-command launcher.

Usage:
    python start.py              # dev mode: backend :8000 + Vite dev server :3000
    python start.py --prod       # prod mode: builds frontend, backend serves it on :3000
    python start.py --no-browser # don't open the browser
    python start.py --port 3000  # prod mode custom port

The script:
  1. loads .env
  2. verifies the Python environment (torch + CUDA)
  3. checks Ollama (VLM/embeddings) and warns if missing
  4. installs frontend deps if needed (dev mode)
  5. starts backend + frontend
  6. waits for health checks and opens the browser
  7. shuts everything down cleanly on Ctrl+C
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"

BANNER = r"""
  ┌─────────────────────────────────────────────────────────┐
  │           Local AI CCTV Analyzer                        │
  │   YOLO11x · ByteTrack · Re-ID · Qwen2.5-VL · 100% local │
  └─────────────────────────────────────────────────────────┘
"""


# ---------------------------------------------------------------------------
# .env loading (stdlib only — keep the launcher dependency-free)
# ---------------------------------------------------------------------------
def load_env() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------
def check_python_env() -> None:
    import importlib.util

    missing = [pkg for pkg in ("fastapi", "sqlalchemy", "cv2", "torch", "numpy") if importlib.util.find_spec(pkg) is None]
    if missing:
        print(f"[setup] Missing Python packages: {', '.join(missing)}")
        print("        Run:  pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128")
        print("        Then: pip install -r requirements.txt")
        sys.exit(1)

    try:
        import torch

        if torch.cuda.is_available():
            print(f"[setup] CUDA OK — GPU: {torch.cuda.get_device_name(0)} (PyTorch {torch.__version__})")
        else:
            print("[setup] WARNING: CUDA is not available to PyTorch. Analysis will run on CPU (slow).")
            print("        Install the CUDA build: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128")
    except Exception as exc:
        print(f"[setup] WARNING: torch check failed: {exc}")


def check_ollama() -> None:
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_VLM_MODEL", "qwen2.5vl:7b")
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=2) as resp:
            data = resp.read().decode()
        if resp.status == 200:
            print(f"[setup] Ollama OK ({base})")
            if model not in data:
                print(f"        HINT: model '{model}' not found. Pull it with:  ollama pull {model}")
            embed = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
            if embed not in data:
                print(f"        HINT: embedding model '{embed}' not found. Pull it with:  ollama pull {embed}")
    except Exception:
        print(f"[setup] WARNING: Ollama not reachable at {base}.")
        print("        Install: https://ollama.com  →  ollama pull qwen2.5vl:7b  →  ollama pull nomic-embed-text")
        print("        Analysis still works; events keep rule-based descriptions (no VLM enrichment).")


# ---------------------------------------------------------------------------
# Process management
# ---------------------------------------------------------------------------
def start_backend(port: int, prod_mode: bool) -> subprocess.Popen:
    env = dict(os.environ)
    env["API_PORT"] = str(port)
    env["PROD_MODE"] = "1" if prod_mode else "0"
    cmd = [
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", os.environ.get("API_HOST", "127.0.0.1"),
        "--port", str(port),
    ]
    print(f"[backend] starting API on http://localhost:{port}")
    proc = subprocess.Popen(cmd, cwd=str(BACKEND_DIR), env=env)
    return proc


def ensure_frontend_deps() -> bool:
    if (FRONTEND_DIR / "node_modules").exists():
        return True
    print("[frontend] installing npm dependencies…")
    proc = subprocess.run(
        ["npm", "install", "--no-audit", "--no-fund"],
        cwd=str(FRONTEND_DIR),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(f"[frontend] npm install failed:\n{proc.stdout}\n{proc.stderr}")
        return False
    return True


def start_frontend(port: int) -> subprocess.Popen:
    env = dict(os.environ)
    env["PORT"] = str(port)
    npm = shutil.which("npm")
    print(f"[frontend] starting UI on http://localhost:{port}")
    if sys.platform == "win32":
        return subprocess.Popen(["npm.cmd", "run", "dev", "--", "--port", str(port), "--strictPort"],
                                cwd=str(FRONTEND_DIR), env=env,
                                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    return subprocess.Popen([npm or "npm", "run", "dev", "--", "--port", str(port), "--strictPort"],
                            cwd=str(FRONTEND_DIR), env=env)


def build_frontend() -> bool:
    if (FRONTEND_DIR / "dist" / "index.html").exists():
        return True
    if not ensure_frontend_deps():
        return False
    print("[frontend] building production bundle…")
    proc = subprocess.run(["npm", "run", "build"], cwd=str(FRONTEND_DIR), capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[frontend] build failed:\n{proc.stdout}\n{proc.stderr}")
        return False
    return True


def wait_for(url: str, timeout: float, label: str) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    print(f"[start] timed out waiting for {label} at {url}")
    return False


def terminate(proc: subprocess.Popen, name: str) -> None:
    if proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, timeout=10)
        else:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    except Exception:
        pass
    print(f"[start] stopped {name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="Local AI CCTV Analyzer")
    parser.add_argument("--prod", action="store_true", help="build + serve frontend from the backend (single port)")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    parser.add_argument("--port", type=int, default=None, help="port override (prod mode / frontend)")
    args = parser.parse_args()

    load_env()
    print(BANNER)

    api_port = env_int("API_PORT", 8000)
    frontend_port = args.port or env_int("FRONTEND_PORT", 3000)

    if not (ROOT / "backend" / "app").exists():
        print("[start] backend/app not found — run this from the project root")
        return 1

    check_python_env()
    check_ollama()

    procs: list[subprocess.Popen] = []
    browser_url = f"http://localhost:{frontend_port}"

    try:
        if args.prod:
            if not build_frontend():
                return 1
            procs.append(start_backend(frontend_port, prod_mode=True))
            backend_url = f"http://localhost:{frontend_port}/api/health"
        else:
            if not ensure_frontend_deps():
                return 1
            procs.append(start_backend(api_port, prod_mode=False))
            procs.append(start_frontend(frontend_port))
            backend_url = f"http://localhost:{api_port}/api/health"

        if not wait_for(backend_url, timeout=120, label="backend API"):
            print("[start] backend failed to start. Check the logs above.")
            return 1
        print("[start] backend is healthy")

        if args.prod:
            print(f"\n  UI ready: {browser_url}\n")
            if not args.no_browser:
                webbrowser.open(browser_url)
            print("Press Ctrl+C to stop.\n")
            while True:
                time.sleep(1)
        else:
            if not wait_for(browser_url, timeout=90, label="frontend UI"):
                print("[start] frontend did not come up; opening API docs instead.")
                webbrowser.open(f"http://localhost:{api_port}/docs")
                while True:
                    time.sleep(1)
            print(f"\n  UI ready: {browser_url}   (API: http://localhost:{api_port}/docs)\n")
            if not args.no_browser:
                webbrowser.open(browser_url)
            print("Press Ctrl+C to stop.\n")
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n[start] shutting down…")
    finally:
        for proc, name in reversed(list(zip(procs, ["backend", "frontend"]))):
            terminate(proc, name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
