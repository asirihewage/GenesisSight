import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle, ArrowLeft, Cpu, Film, Gauge, Loader2, Play, Trash2, Users,
} from "lucide-react";
import { useEvents, usePersons, useStats, useStatus, useVideo } from "@/hooks/useApi";
import { queryKeys } from "@/hooks/useApi";
import { useSocket } from "@/hooks/useSocket";
import { api } from "@/lib/api";
import { EVENT_TYPE_LABELS, formatDuration, formatTimestamp } from "@/lib/utils";
import type { ProgressPayload } from "@/types";
import { StatusBadge, VideoCard } from "@/components/VideoCard";
import { EventItem } from "@/components/EventItem";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

export function VideoAnalysis() {
  const { id } = useParams<{ id: string }>();
  const videoId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: video } = useVideo(videoId);
  const { data: status } = useStatus(videoId);
  const { data: events, isLoading: eventsLoading } = useEvents(videoId);
  const { data: persons } = usePersons(videoId);
  const { data: stats } = useStats(videoId);
  const { message: wsMessage } = useSocket();

  const [liveProgress, setLiveProgress] = useState<ProgressPayload | null>(null);
  const [personFilter, setPersonFilter] = useState<number | "all">("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");

  // live updates from the WebSocket
  useEffect(() => {
    if (!wsMessage || wsMessage.video_id !== videoId) return;
    if (wsMessage.type === "progress") {
      setLiveProgress(wsMessage.payload as ProgressPayload);
    }
    if (wsMessage.type === "event") {
      queryClient.invalidateQueries({ queryKey: queryKeys.events(videoId, "*") });
      queryClient.invalidateQueries({ queryKey: queryKeys.stats(videoId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.persons(videoId) });
    }
    if (wsMessage.type === "status") {
      queryClient.invalidateQueries({ queryKey: queryKeys.video(videoId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.status(videoId) });
      setLiveProgress(null);
    }
  }, [wsMessage, videoId, queryClient]);

  const analyzeMutation = useMutation({
    mutationFn: api.analyze,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.status(videoId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.video(videoId) });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: api.deleteVideo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.videos });
      navigate("/");
    },
  });

  const processing = status?.status === "processing" || status?.status === "queued";
  const displayProgress = processing && liveProgress ? liveProgress.progress : status?.progress ?? 0;
  const displayStage = processing && liveProgress ? liveProgress.current_stage : status?.current_stage ?? "";

  const filteredEvents = useMemo(() => {
    let list = events ?? [];
    if (personFilter !== "all") list = list.filter((e) => e.person_id === personFilter);
    if (typeFilter !== "all") list = list.filter((e) => e.event_type === typeFilter);
    return list;
  }, [events, personFilter, typeFilter]);

  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const e of events ?? []) counts[e.event_type] = (counts[e.event_type] ?? 0) + 1;
    return counts;
  }, [events]);

  if (!video) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 w-full rounded-lg" />
        <Skeleton className="h-96 w-full rounded-lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/")}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight">{video.filename}</h1>
              <StatusBadge status={status?.status ?? video.status} />
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {formatDuration(video.duration)} · {video.width}×{video.height} · {video.fps.toFixed(1)} fps
              {stats && stats.persons > 0 && <> · {stats.persons} people · {stats.events} events</>}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          {status?.status === "failed" && (
            <Button variant="outline" onClick={() => analyzeMutation.mutate(videoId)}>
              <Play className="mr-2" /> Retry
            </Button>
          )}
          {status?.status === "uploaded" && !processing && (
            <Button onClick={() => analyzeMutation.mutate(videoId)} disabled={analyzeMutation.isPending}>
              <Play className="mr-2" />
              {analyzeMutation.isPending ? "Starting…" : "Analyze"}
            </Button>
          )}
          {status?.status === "completed" && (
            <Button variant="outline" onClick={() => analyzeMutation.mutate(videoId)}>
              <Play className="mr-2" /> Re-analyze
            </Button>
          )}
          {!processing && (
            <Button variant="ghost" className="text-destructive hover:text-destructive" onClick={() => deleteMutation.mutate(videoId)}>
              <Trash2 className="mr-2" /> Delete
            </Button>
          )}
        </div>
      </div>

      {video.status === "failed" && video.error && (
        <div className="flex items-start gap-3 rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{video.error}</span>
        </div>
      )}

      {/* live processing status */}
      {(processing || status?.status === "uploaded") && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Cpu className="h-4 w-4 text-primary" />
              Processing status
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Progress value={displayProgress} />
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <div className="flex items-center gap-2">
                {processing && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
                <span className="font-medium">{displayStage || "Queued…"}</span>
                {status?.queued_position && <span className="text-muted-foreground">(position {status.queued_position} in queue)</span>}
              </div>
              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <span className="flex items-center gap-1"><Gauge className="h-3.5 w-3.5" /> {status?.fps_processed?.toFixed(1) ?? "0.0"} fps processed</span>
                <span className="font-mono text-sm text-foreground">{displayProgress.toFixed(1)}%</span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* persons */}
      {persons && persons.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Users className="h-4 w-4 text-primary" />
              Identified people ({persons.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {persons.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setPersonFilter(personFilter === p.id ? "all" : p.id)}
                  className={personFilter === p.id ? "ring-2 ring-primary" : ""}
                >
                  <Badge
                    variant="outline"
                    className={personFilter === p.id
                      ? "border-primary bg-primary/15 text-primary"
                      : "hover:border-primary/50"}
                  >
                    <span className="mr-1.5 inline-block h-4 w-4 overflow-hidden rounded-sm bg-slate-800 align-middle">
                      {p.thumbnail_url ? (
                        <img src={p.thumbnail_url} alt={`Person ${p.id}`} className="h-full w-full object-cover" />
                      ) : null}
                    </span>
                    #{p.id} · {p.event_count} events
                  </Badge>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* filters + timeline */}
      <div>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Event timeline</h2>
          <div className="flex gap-2">
            <Select value={personFilter === "all" ? "all" : String(personFilter)} onChange={(e) => setPersonFilter(e.target.value === "all" ? "all" : Number(e.target.value))}>
              <option value="all">All people</option>
              {(persons ?? []).map((p) => (
                <option key={p.id} value={p.id}>Person #{p.id}</option>
              ))}
            </Select>
            <Select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="all">All event types</option>
              {Object.entries(EVENT_TYPE_LABELS).map(([key, label]) => (
                <option key={key} value={key}>
                  {label} ({typeCounts[key] ?? 0})
                </option>
              ))}
            </Select>
          </div>
        </div>

        {eventsLoading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => <Skeleton key={i} className="h-24 rounded-lg" />)}
          </div>
        ) : (events ?? []).length === 0 ? (
          <Card className="flex flex-col items-center gap-3 py-16 text-center">
            <Film className="h-10 w-10 text-muted-foreground/40" />
            <div>
              <p className="text-sm font-medium">No events yet</p>
              <p className="text-xs text-muted-foreground">
                {status?.status === "completed"
                  ? "This video produced no timeline events."
                  : "Click Analyze to start the AI pipeline."}
              </p>
            </div>
          </Card>
        ) : filteredEvents.length === 0 ? (
          <Card className="py-10 text-center text-sm text-muted-foreground">
            No events match the selected filters.
          </Card>
        ) : (
          <div className="space-y-3">
            {filteredEvents.map((e) => (
              <EventItem key={e.id} event={e} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
