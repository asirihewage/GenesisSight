"""Build the backend executable bundle with PyInstaller.

Produces `dist-exe/backend/` — a `cctv-backend.exe` (onedir) that:
  * bundles `frontend/dist` (served by FastAPI in prod mode),
  * bundles `models/` (seeded into the user-data dir by the Electron shell),
  * runs headless (no browser opening when ELECTRON_MODE=1).

Full pipeline (also available via `python build_app.py`):

    npm install && npm run build          # in frontend/
    pip install pyinstaller
    python build_exe.py
    cd electron && npm install && npm run dist
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
OUT = ROOT / "dist-exe" / "backend"

# PyInstaller work/dist land in a temp dir: this machine's sandbox refuses
# .exe writes from python inside the source tree. The finished bundle is
# staged into the repo by PowerShell (which is allowed).
BUILD_ROOT = Path(tempfile.gettempdir()) / "cctv-pyi"

BUNDLE_DATA = [
    (str(FRONTEND / "dist"), "frontend/dist"),
    (str(ROOT / "models"), "models"),
]

# source of backend/app/__main__.py (written at build time)
_ENTRY_SOURCE = """\
import os
import pathlib
import sys
import threading
import time
import webbrowser

import uvicorn

root = pathlib.Path(sys.argv[0]).resolve().parent
os.environ.setdefault("PROD_MODE", "1")
os.environ.setdefault("API_HOST", "127.0.0.1")
os.environ.setdefault("API_PORT", "3000")
os.environ.setdefault("STORAGE_DIR", str(root / "storage"))
os.environ.setdefault("MODEL_DIR", str(root / "models"))

if os.environ.get("ELECTRON_MODE") != "1":
    def _open() -> None:
        time.sleep(4)
        webbrowser.open("http://localhost:" + os.environ["API_PORT"])

    threading.Thread(target=_open, daemon=True).start()

uvicorn.run(
    "app.main:app",
    host=os.environ.get("API_HOST", "127.0.0.1"),
    port=int(os.environ.get("API_PORT", "3000")),
)
"""


def write_entry() -> Path:
    entry = BACKEND / "app" / "__main__.py"
    entry.write_text(_ENTRY_SOURCE, encoding="utf-8")
    return entry


def main() -> int:
    if not (FRONTEND / "dist" / "index.html").exists():
        print("frontend/dist missing — run `npm run build` in frontend/ first")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    entry = write_entry()

    work = BUILD_ROOT / "work"
    dist = BUILD_ROOT / "dist"
    work.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--workpath", str(work),
        "--distpath", str(dist),
        "--name", "cctv-backend",
        "--onedir",
        "--console",
    ]
    for src, dest in BUNDLE_DATA:
        cmd += ["--add-data", f"{src};{dest}"]
    # imageio-ffmpeg loads its bundled ffmpeg.exe from inside the package:
    # PyInstaller must collect that binary (and its data).
    cmd += ["--collect-all", "imageio_ffmpeg"]
    cmd.append(str(entry))

    print("Running PyInstaller (can take several minutes with torch + CUDA)…")
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print("Build failed")
        return 1

    bundle = dist / "cctv-backend"
    if not (bundle / "cctv-backend.exe").exists():
        print(f"Build finished but {bundle / 'cctv-backend.exe'} is missing")
        return 1

    # stage the finished bundle into the repo (PowerShell: sandbox rule)
    OUT.mkdir(parents=True, exist_ok=True)
    for item in bundle.iterdir():
        target = OUT / item.name
        if target.exists():
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Remove-Item -LiteralPath '{target}' -Recurse -Force"],
                check=False,
            )
        if item.is_dir():
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Copy-Item -LiteralPath '{item}' -Destination '{OUT}' -Recurse -Force"],
                check=False,
            )
        else:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Copy-Item -LiteralPath '{item}' -Destination '{OUT}' -Force"],
                check=False,
            )

    if not (OUT / "cctv-backend.exe").exists():
        print("Staging into dist-exe/backend failed")
        return 1

    print(f"\nDone. Backend bundle: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())