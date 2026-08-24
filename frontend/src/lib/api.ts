import type { Health, Person, SimilarPerson, CctvEvent, SearchResponse, SetupStatus, StatusResponse, UploadResponse, Video, VideoStats, Vehicle } from "@/types";

const BASE = ""; // same origin (vite proxy / fastapi static)

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export const api = {
  // videos
  listVideos: (limit = 20, offset = 0) => {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    return request<Video[]>(`/api/videos?${params.toString()}`);
  },
  getVideo: (id: number) => request<Video>(`/api/videos/${id}`),
  getStatus: (id: number) => request<StatusResponse>(`/api/videos/${id}/status`),
  getEvents: (id: number, personId?: number, eventType?: string) => {
    const params = new URLSearchParams();
    if (personId) params.set("person_id", String(personId));
    if (eventType) params.set("event_type", eventType);
    const qs = params.toString();
    return request<CctvEvent[]>(`/api/videos/${id}/events${qs ? `?${qs}` : ""}`);
  },
  getVideoStats: (id: number) => request<VideoStats>(`/api/videos/${id}/stats`),
  analyze: (id: number) => request<StatusResponse>(`/api/videos/${id}/analyze`, { method: "POST" }),
  deleteVideo: (id: number) => request<{ ok: boolean }>(`/api/videos/${id}`, { method: "DELETE" }),

  // directory watching
  getWatchDir: () => request<{ default_watch_dir: string; auto_scan_new_videos: boolean }>("/api/videos/watch-dir"),
  setWatchDir: (dir: string) => request<{ default_watch_dir: string; auto_scan_new_videos: boolean; message: string }>("/api/videos/watch-dir", { method: "POST" }),
  scanWatchDir: () => request<{ found: number; added: number; message: string }>("/api/videos/watch-dir/scan", { method: "POST" }),
  setAutoScanToggle: (enabled: boolean) =>
    request<{ auto_scan_new_videos: boolean; message: string }>("/api/videos/watch-dir/autoscan", { method: "POST", body: JSON.stringify({ auto_scan_new_videos: enabled }) }),

  // upload with progress
  uploadVideo: (file: File, onProgress?: (pct: number) => void) =>
    new Promise<UploadResponse>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${BASE}/api/videos/upload`);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
      };
      xhr.onload = () => {
        try {
          const body = JSON.parse(xhr.responseText);
          if (xhr.status >= 200 && xhr.status < 300) resolve(body);
          else reject(new Error(body?.detail ?? `Upload failed (${xhr.status})`));
        } catch {
          reject(new Error("Invalid server response"));
        }
      };
      xhr.onerror = () => reject(new Error("Network error during upload"));
      const form = new FormData();
      form.append("file", file);
      xhr.send(form);
    }),

  // persons
  listPersons: (videoId?: number) => {
    const qs = videoId ? `?video_id=${videoId}` : "";
    return request<Person[]>(`/api/persons${qs}`);
  },
  renamePerson: (id: number, name: string) =>
    request<Person>(`/api/persons/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  personSimilar: (id: number) => request<SimilarPerson[]>(`/api/persons/${id}/similar`),

  // vehicles
  listVehicles: (page = 1, limit = 20) => {
    const params = new URLSearchParams();
    params.set("page", String(page));
    params.set("limit", String(limit));
    return request<{ items: Vehicle[]; total_pages: number }>(`/api/vehicles?${params.toString()}`);
  },
  getVehicle: (id: number) => request<Vehicle>(`/api/vehicles/${id}`),
  getVehicleEvents: (vehicleId: number) => request<CctvEvent[]>(`/api/vehicles/${vehicleId}/events`),

  // event annotations (tags / notes are fed back into semantic search)
  patchEvent: (videoId: number, eventId: number, patch: { tags?: string[]; tag?: string; note?: string }) =>
    request<CctvEvent>(`/api/videos/${videoId}/events/${eventId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }),

  // search
  search: (q: string, videoId?: number) => {
    const params = new URLSearchParams({ q });
    if (videoId) params.set("video_id", String(videoId));
    return request<SearchResponse>(`/api/search?${params.toString()}`);
  },

  // health
  health: () => request<Health>("/api/health"),

  // first-run setup wizard
  setupStatus: () => request<SetupStatus>("/api/setup/status"),
  setupDownloadYolo: () => request<{ ok: boolean; started: boolean }>("/api/setup/yolo/download", { method: "POST" }),
  setupPullOllama: () => request<{ ok: boolean; started: boolean }>("/api/setup/ollama/pull", { method: "POST" }),
  setupInstallOllama: () => request<{ ok: boolean; started: boolean }>("/api/setup/ollama/install", { method: "POST" }),
  setupComplete: (ollamaSkipped: boolean) =>
    request<{ ok: boolean }>("/api/setup/complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ollama_skipped: ollamaSkipped }),
    }),
};

export function wsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws`;
}
