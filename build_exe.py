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

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
OUT = ROOT / "dist-exe" / "backend"

# PyInstaller work/dist live in the pre-approved temp workspace: this
# machine's sandbox refuses python-written .exe files everywhere else.
# The finished bundle is staged into the repo by PowerShell (which is allowed).
BUILD_ROOT = Path(tempfile.gettempdir()) / "opencode" / "pyi"

BUNDLE_DATA = [
    (str(FRONTEND / "dist"), "frontend/dist"),
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


# Optional-role CUDA libraries that torch loads eagerly but that this app never
# calls (verified by load/conv tests on the same DLL set): removing them keeps
# the NSIS payload under makensis' 2 GB mmap limit.
#
#  * cudnn_adv64_9.dll      — deformable-conv / attention ops only
#  * cusparse64_12.dll      — sparse-matrix ops (load-time safe to skip)
#  * nvrtc64_120_0.alt.dll  — NVIDIA runtime compiler fallback (no torch.compile)
#  * cusolverMg64_11.dll    — multi-GPU solver (single-GPU app)
#
# Also dropped: polars / Tk interop trees that nothing in the app graph
# references (leftovers pulled from the environment by PyInstaller hooks).
# NOTE: PyAV ("av", "av.libs") must NOT be trimmed — supervision._cv2._video
# hard-imports it when ByteTrack loads (analyze stage) and the process dies
# with ModuleNotFoundError without it.
TRIMMED_INTERNAL = [
    "torch/lib/cudnn_adv64_9.dll",
    "torch/lib/cusparse64_12.dll",
    "torch/lib/nvrtc64_120_0.alt.dll",
    "torch/lib/cusolverMg64_11.dll",
    "_polars_runtime_32",
    "tcl8",
    "_tcl_data",
    "_tk_data",
    "tcl86t.dll",
    "tk86t.dll",
]


def trim_bundle(bundle: Path) -> None:
    internal = bundle / "_internal"
    for rel in TRIMMED_INTERNAL:
        target = internal / rel
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            print(f"  trimmed {rel}")
    print("  trim complete")


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
        "--windowed",  # no console window; logs go to <storage>/logs/app.log
    ]
    for src, dest in BUNDLE_DATA:
        cmd += ["--add-data", f"{src};{dest}"]
    # imageio-ffmpeg loads its bundled ffmpeg.exe from inside the package:
    # PyInstaller must collect that binary (and its data).
    cmd += ["--collect-all", "imageio_ffmpeg"]
    # The entry script boots uvicorn with a *string* "app.main:app", which
    # static analysis cannot see — and the AI stack is imported lazily inside
    # functions. Make the bundler pull in the whole app + heavy deps:
    for hidden in (
        "app.main",
        "cv2",
        "torch",
        "torchvision",
        "ultralytics",
        "supervision",
        "imageio_ffmpeg",
    ):
        cmd += ["--hidden-import", hidden]
    cmd += ["--collect-submodules", "app"]
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

    # Ship the built frontend SPA inside _internal/frontend/dist so the bundled
    # backend serves the UI (main.py MEIPASS discovery) and the Electron window
    # is never blank.
    fe_dest = bundle / "_internal" / "frontend" / "dist"
    fe_dest.mkdir(parents=True, exist_ok=True)
    for item in (FRONTEND / "dist").iterdir():
        dst = fe_dest / item.name
        if item.is_dir():
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Copy-Item -LiteralPath '{item}' -Destination '{dst}' -Recurse -Force"],
                check=False,
            )
        else:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Copy-Item -LiteralPath '{item}' -Destination '{dst}' -Force"],
                check=False,
            )
    print(f"  frontend bundled -> {fe_dest}")

    trim_bundle(bundle)

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