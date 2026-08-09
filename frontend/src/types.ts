export interface Video {
  id: number;
  filename: string;
  duration: number;
  width: number;
  height: number;
  fps: number;
  status: "uploaded" | "queued" | "processing" | "completed" | "failed";
  progress: number;
  current_stage: string;
  fps_processed: number;
  error: string | null;
  created_at: string;
}

export interface UploadResponse {
  id: number;
  filename: string;
  status: string;
}

export interface StatusResponse {
  id: number;
  filename: string;
  status: string;
  progress: number;
  current_stage: string;
  fps_processed: number;
  error: string | null;
  queued_position: number | null;
}

export interface Person {
  id: number;
  video_id: number | null;
  first_seen: number;
  last_seen: number;
  thumbnail_url: string | null;
  event_count: number;
  last_event_type: string | null;
}

export interface CctvEvent {
  id: number;
  video_id: number;
  person_id: number | null;
  timestamp: number;
  event_type: string;
  description: string;
  confidence: number;
  image_url: string | null;
  thumbnail_url: string | null;
  objects: string[];
  activity: string | null;
  created_at: string;
}

export interface SearchResultItem {
  event: CctvEvent;
  score: number;
}

export interface SearchResponse {
  query: string;
  method: "ollama_embedding" | "keyword";
  results: SearchResultItem[];
}

export interface ModelHealth {
  name: string;
  available: boolean;
  detail: string;
}

export interface Health {
  app: string;
  version: string;
  cuda_available: boolean;
  gpu_name: string | null;
  device: string;
  torch_version: string | null;
  yolo: ModelHealth;
  reid: ModelHealth;
  ollama: ModelHealth;
  ollama_models: string[];
  storage_dir: string;
  storage_used_mb: number;
  videos: number;
}

export interface VideoStats {
  events: number;
  persons: number;
  event_types: Record<string, number>;
}

export interface WsMessage {
  type: "progress" | "event" | "status";
  video_id: number;
  payload: unknown;
}

export interface ProgressPayload {
  progress: number;
  current_stage: string;
  fps_processed: number;
}
