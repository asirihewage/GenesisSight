import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatTimestamp(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
}

export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export const EVENT_TYPE_LABELS: Record<string, string> = {
  person_entered: "Entered",
  person_exited: "Exited",
  person_appeared: "Appeared",
  person_disappeared: "Disappeared",
  person_moved: "Moved",
  person_carrying: "Carrying",
  person_loitering: "Loitering",
  person_running: "Running",
};

export const EVENT_TYPE_COLORS: Record<string, string> = {
  person_entered: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  person_exited: "bg-rose-500/15 text-rose-400 border-rose-500/30",
  person_appeared: "bg-sky-500/15 text-sky-400 border-sky-500/30",
  person_disappeared: "bg-orange-500/15 text-orange-400 border-orange-500/30",
  person_moved: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  person_carrying: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  person_loitering: "bg-violet-500/15 text-violet-400 border-violet-500/30",
  person_running: "bg-red-500/15 text-red-400 border-red-500/30",
};

export const EVENT_TYPE_SOLID: Record<string, string> = {
  person_entered: "bg-emerald-500",
  person_exited: "bg-rose-500",
  person_appeared: "bg-sky-500",
  person_disappeared: "bg-orange-500",
  person_moved: "bg-blue-500",
  person_carrying: "bg-amber-500",
  person_loitering: "bg-violet-500",
  person_running: "bg-red-500",
};
