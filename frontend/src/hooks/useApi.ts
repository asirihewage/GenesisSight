import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export const queryKeys = {
  videos: ["videos"] as const,
  video: (id: number) => ["video", id] as const,
  status: (id: number) => ["status", id] as const,
  events: (id: number, filters: string) => ["events", id, filters] as const,
  persons: (videoId?: number) => ["persons", videoId ?? "all"] as const,
  stats: (id: number) => ["stats", id] as const,
  search: (q: string, videoId?: number) => ["search", q, videoId ?? "all"] as const,
  health: ["health"] as const,
};

export function useVideos() {
  return useQuery({ queryKey: queryKeys.videos, queryFn: () => api.listVideos() });
}

export function useVideo(id: number) {
  return useQuery({ queryKey: queryKeys.video(id), queryFn: () => api.getVideo(id) });
}

export function useStatus(id: number, refetchIntervalMs = 2000) {
  return useQuery({
    queryKey: queryKeys.status(id),
    queryFn: () => api.getStatus(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "processing" || status === "queued" ? refetchIntervalMs : false;
    },
  });
}

export function useEvents(id: number, personId?: number, eventType?: string) {
  const filters = `${personId ?? "all"}:${eventType ?? "all"}`;
  return useQuery({
    queryKey: queryKeys.events(id, filters),
    queryFn: () => api.getEvents(id, personId, eventType),
  });
}

export function usePersons(videoId?: number) {
  return useQuery({ queryKey: queryKeys.persons(videoId), queryFn: () => api.listPersons(videoId) });
}

export function useStats(id: number) {
  return useQuery({ queryKey: queryKeys.stats(id), queryFn: () => api.getVideoStats(id) });
}

export function useHealth() {
  return useQuery({ queryKey: queryKeys.health, queryFn: () => api.health(), refetchInterval: 15000 });
}
