/**
 * CCTV Analyzer — splash window preload.
 *
 * Exposes a single read-only channel: the main process streams the tail of
 * the backend log file so the loader can show a live, auto-scrolling status
 * log while the analysis engine boots.
 */

"use strict";

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("cctvSplash", {
  onLog: (callback) => {
    ipcRenderer.on("splash-log", (_event, text) => callback(text));
  },
});