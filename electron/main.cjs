/**
 * CCTV Analyzer — Electron main process.
 *
 * Responsibilities:
 *   1. lock onto a single instance,
 *   2. spawn the bundled Python backend (PyInstaller onedir) on a free port,
 *   3. wait for the health endpoint, then open the UI window,
 *   4. cleanly kill the backend on quit.
 *
 * Dev mode (`electron . --dev`): does not spawn anything — it connects to a
 * backend you started yourself (default http://127.0.0.1:8000,
 * override with the CCTV_BACKEND_URL env var).
 */

"use strict";

const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const net = require("node:net");
const http = require("node:http");

const APP_NAME = "CCTV Analyzer";
const DEV = process.argv.includes("--dev");
const DEFAULT_DEV_URL = "http://127.0.0.1:8000";

let backendUrl = null;
let backendProc = null;
let mainWindow = null;
let quitting = false;

// ---------------------------------------------------------------------------
// Paths + one-time seeding
// ---------------------------------------------------------------------------

function userDataDir() {
  return path.join(app.getPath("appData"), APP_NAME);
}

function backendExePath() {
  // extraResources maps dist-exe/backend -> resources/backend
  return path.join(process.resourcesPath, "backend", "cctv-backend.exe");
}

function bundledModelsDir() {
  const backend = path.join(process.resourcesPath, "backend");
  const candidates = [
    path.join(backend, "_internal", "models"),
    path.join(backend, "models"),
  ];
  return candidates.find((dir) => fs.existsSync(dir)) || null;
}

/** Copy bundled model weights (e.g. yolo11x.pt) into the user data dir once. */
function seedModels() {
  const src = bundledModelsDir();
  if (!src) return;
  const dst = path.join(userDataDir(), "models");
  try {
    fs.mkdirSync(dst, { recursive: true });
  } catch (err) {
    console.error("seed: cannot create models dir:", err);
    return;
  }
  for (const entry of fs.readdirSync(src)) {
    const from = path.join(src, entry);
    const to = path.join(dst, entry);
    if (fs.statSync(from).isFile() && !fs.existsSync(to)) {
      try {
        fs.copyFileSync(from, to);
        console.log("Seeded model:", entry);
      } catch (err) {
        console.error("seed:", entry, err);
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Port + health helpers
// ---------------------------------------------------------------------------

function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
    server.on("error", reject);
  });
}

function waitForHealth(url, timeoutMs) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const tryOnce = () => {
      const req = http.get(`${url}/api/health`, (res) => {
        res.resume();
        if (res.statusCode === 200) resolve();
        else retry();
      });
      req.on("error", retry);
      req.setTimeout(1500, () => {
        req.destroy();
        retry();
      });
    };
    const retry = () => {
      if (Date.now() - started > timeoutMs) {
        reject(new Error(`Backend not healthy within ${timeoutMs} ms`));
        return;
      }
      setTimeout(tryOnce, 500);
    };
    tryOnce();
  });
}

// ---------------------------------------------------------------------------
// Backend lifecycle
// ---------------------------------------------------------------------------

function logFileStream() {
  const logsDir = path.join(userDataDir(), "logs");
  fs.mkdirSync(logsDir, { recursive: true });
  return fs.createWriteStream(path.join(logsDir, "backend.log"), { flags: "a" });
}

async function startBackend() {
  const exe = backendExePath();
  if (!fs.existsSync(exe)) {
    return { ok: false, error: `Backend executable missing: ${exe}` };
  }
  const port = await findFreePort();
  const env = {
    ...process.env,
    PROD_MODE: "1",
    API_PORT: String(port),
    STORAGE_DIR: path.join(userDataDir(), "storage"),
    MODEL_DIR: path.join(userDataDir(), "models"),
    ELECTRON_MODE: "1",
  };
  const log = logFileStream();
  backendProc = spawn(exe, [], { env, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
  backendProc.stdout.pipe(log);
  backendProc.stderr.pipe(log);
  backendProc.on("error", (err) => {
    console.error("backend spawn error:", err);
  });
  backendProc.on("exit", (code, signal) => {
    console.log("backend exited:", code, signal);
    if (!quitting && mainWindow && !mainWindow.isDestroyed()) {
      dialog.showErrorBox(
        "CCTV Analyzer backend stopped",
        `The analysis service exited unexpectedly (code ${code}).\n` +
          `See ${path.join(userDataDir(), "logs", "backend.log")} for details.`
      );
    }
    backendProc = null;
  });

  backendUrl = `http://127.0.0.1:${port}`;
  return { ok: true, url: backendUrl };
}

function killBackend() {
  if (!backendProc) return;
  const proc = backendProc;
  backendProc = null;
  try {
    const taskkill = spawn(
      "taskkill",
      ["/PID", String(proc.pid), "/T", "/F"],
      { windowsHide: true, stdio: "ignore" }
    );
    taskkill.on("exit", () => {});
  } catch (err) {
    try {
      proc.kill("SIGKILL");
    } catch (_) {
      /* already dead */
    }
  }
}

// ---------------------------------------------------------------------------
// Window
// ---------------------------------------------------------------------------

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 640,
    title: APP_NAME,
    backgroundColor: "#0a0f1e",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow.loadURL(backendUrl);
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// ---------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(async () => {
    let ready = false;
    if (DEV) {
      backendUrl = process.env.CCTV_BACKEND_URL || DEFAULT_DEV_URL;
      console.log(`dev mode -> ${backendUrl}`);
      try {
        await waitForHealth(backendUrl, 10000);
        ready = true;
      } catch {
        ready = false;
      }
      if (!ready) {
        dialog.showErrorBox(
          "Backend not running",
          `Did not find the API at ${backendUrl}.\n` +
            "Start it with `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` (in backend/)."
        );
        app.quit();
        return;
      }
    } else {
      seedModels();
      const result = await startBackend();
      if (!result.ok) {
        dialog.showErrorBox("Startup failed", result.error);
        app.quit();
        return;
      }
      try {
        // first backend start may import torch + CUDA libs: allow generous time
        await waitForHealth(result.url, 180000);
      } catch (err) {
        dialog.showErrorBox(
          "Startup failed",
          `${err.message}\nSee ${path.join(userDataDir(), "logs", "backend.log")} for details.`
        );
        killBackend();
        app.quit();
        return;
      }
    }

    createWindow();

    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });

  app.on("window-all-closed", () => {
    app.quit();
  });

  app.on("before-quit", () => {
    quitting = true;
    killBackend();
  });
}