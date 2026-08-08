import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Activity, Film, Users, Video as VideoIcon, UploadCloud, PlayCircle } from "lucide-react";
import { useEvents, usePersons, useVideos } from "@/hooks/useApi";
import { queryKeys } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { VideoCard } from "@/components/VideoCard";
import { EventItem } from "@/components/EventItem";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function Dashboard() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: videos, isLoading: videosLoading } = useVideos();
  const { data: persons } = usePersons();

  // Most recent completed video -> its events feed the "recent events" panel
  const latestCompleted = (videos ?? []).find((v) => v.status === "completed");
  const { data: events, isLoading: eventsLoading } = useEvents(latestCompleted?.id ?? -1);

  const deleteMutation = useMutation({
    mutationFn: api.deleteVideo,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.videos }),
  });

  const processingCount = (videos ?? []).filter(
    (v) => v.status === "processing" || v.status === "queued",
  ).length;
  const completedCount = (videos ?? []).filter((v) => v.status === "completed").length;
  const recentEvents = (events ?? []).slice(-10).reverse();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">Upload CCTV footage and analyze it with local AI.</p>
        </div>
        <Button onClick={() => navigate("/upload")}>
          <UploadCloud className="mr-2" /> Upload Video
        </Button>
      </div>

      {/* stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Film} label="Videos" value={videos?.length ?? 0} />
        <StatCard icon={PlayCircle} label="Processing" value={processingCount} />
        <StatCard icon={Users} label="Identified people" value={persons?.length ?? 0} />
        <StatCard icon={Activity} label="Completed analyses" value={completedCount} />
      </div>

      {/* videos */}
      <div>
        <h2 className="mb-3 text-lg font-semibold">Videos</h2>
        {videosLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((i) => <Skeleton key={i} className="h-56 rounded-lg" />)}
          </div>
        ) : (videos ?? []).length === 0 ? (
          <Card className="flex flex-col items-center gap-3 border-dashed py-16">
            <VideoIcon className="h-12 w-12 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">No videos yet</p>
            <Button variant="outline" onClick={() => navigate("/upload")}>
              Upload your first CCTV recording
            </Button>
          </Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {(videos ?? []).map((v) => (
              <VideoCard key={v.id} video={v} onDelete={(id) => deleteMutation.mutate(id)} />
            ))}
          </div>
        )}
      </div>

      {/* recent events */}
      <div>
        <h2 className="mb-3 text-lg font-semibold">
          Recent events{latestCompleted ? ` — ${latestCompleted.filename}` : ""}
        </h2>
        {!latestCompleted ? (
          <Card className="py-10 text-center text-sm text-muted-foreground">
            No events yet — upload a video and click Analyze.
          </Card>
        ) : eventsLoading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => <Skeleton key={i} className="h-24 rounded-lg" />)}
          </div>
        ) : recentEvents.length === 0 ? (
          <Card className="py-10 text-center text-sm text-muted-foreground">
            This video produced no events.
          </Card>
        ) : (
          <div className="space-y-3">
            {recentEvents.slice(0, 8).map((e) => (
              <EventItem key={e.id} event={e} showVideoLink />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value }: { icon: typeof Film; label: string; value: number }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary/15 text-primary">
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <div className="text-2xl font-bold">{value}</div>
          <div className="text-xs text-muted-foreground">{label}</div>
        </div>
      </CardContent>
    </Card>
  );
}
