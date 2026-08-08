"""One-command builder for the installer-ready desktop app.

Steps:
  1. build the frontend (npm run build in frontend/),
  2. bundle the Python backend with PyInstaller (dist-exe/backend),
  3. invoke electron-builder (NSIS) — produces the setup wizard installer.

Requires the frontend deps (`npm install` in frontend/), PyInstaller and the
electron deps (`npm install` in electron/). Flags:

    python build_app.py                 # everything
    python build_app.py --no-frontend   # reuse existing frontend/dist
    python build_app.py --no-backend    # reuse existing dist-exe/backend
    python build_app.py --installer-only   # only run electron-builder
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
ELECTRON = ROOT / "electron"


def run(cmd: list[str], cwd: Path, label: str) -> bool:
    print(f"\n=== {label} ===")
    result = subprocess.run(cmd, cwd=str(cwd))
    if result.returncode != 0:
        print(f"[FAIL] {label} (exit {result.returncode})")
        return False
    print(f"[ok] {label}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the CCTV Analyzer installer")
    parser.add_argument("--frontend", action="store_true", help="force frontend build")
    parser.add_argument("--skip-frontend", action="store_true", help="keep existing frontend/dist")
    parser.add_argument("--skip-backend", action="store_true", help="keep existing dist-exe/backend")
    parser.add_argument("--installer-only", action="store_true", help="only run electron-builder")
    args = parser.parse_args()

    if not args.installer_only:
        if not args.skip_frontend:
            if not (FRONTEND / "dist" / "index.html").exists() or args.frontend:
                deps_ok = (FRONTEND / "node_modules").exists() or run(
                    ["npm", "install", "--no-audit", "--no-fund"], FRONTEND, "frontend npm install"
                )
                if not deps_ok or not run(["npm", "run", "build"], FRONTEND, "frontend build"):
                    return 1
            else:
                print("[skip] frontend/dist already exists")
        if not args.skip_backend:
            if not (ROOT / "dist-exe" / "backend" / "cctv-backend.exe").exists():
                if not run([sys.executable, str(ROOT / "build_exe.py")], ROOT, "backend PyInstaller bundle"):
                    return 1
            else:
                print("[skip] dist-exe/backend already exists")

    if not (ELECTRON / "node_modules" / "electron" / "dist" / "electron.exe").exists():
        if not (ELECTRON / "node_modules").exists():
            if not run(["npm", "install", "--no-audit", "--no-fund"], ELECTRON, "electron deps"):
                return 1
        else:
            print("[note] electron deps present but binary missing; running npm install")
            if not run(["npm", "install", "--no-audit", "--no-fund"], ELECTRON, "electron deps"):
                return 1

    if not (ROOT / "dist-exe" / "backend" / "cctv-backend.exe").exists():
        print("[FAIL] dist-exe/backend/cctv-backend.exe missing — run python build_exe.py")
        return 1

    if not run(["npm", "run", "dist"], ELECTRON, "electron-builder (NSIS installer)"):
        return 1

    setup = ROOT / "release"
    print(f"\nDone. Installer: {setup / 'CCTV Analyzer Setup *.exe'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())