import type { Health, Person, CctvEvent, SearchResponse, StatusResponse, UploadResponse, Video, VideoStats } from "@/types";

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
  listVideos: () => request<Video[]>("/api/videos"),
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

  // search
  search: (q: string, videoId?: number) => {
    const params = new URLSearchParams({ q });
    if (videoId) params.set("video_id", String(videoId));
    return request<SearchResponse>(`/api/search?${params.toString()}`);
  },

  // health
  health: () => request<Health>("/api/health"),
};

export function wsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws`;
}
