/**
 * CCTV Analyzer — preload script.
 *
 * Exposes a minimal, read-only API to the renderer over contextBridge.
 * The renderer talks to the backend over HTTP/WebSocket (same origin), so
 * all it needs from here is static information for the UI / support.
 */

"use strict";

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("cctv", {
  appName: "CCTV Analyzer",
  platform: process.platform,
  isPackaged: !process.argv.includes("--dev"),
  versions: {
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    node: process.versions.node,
  },
  appVersion: () => ipcRenderer.invoke("app:version"),
});

ipcRenderer.on("backend:stopped", () => {
  document.dispatchEvent(new CustomEvent("cctv-backend-stopped"));
});