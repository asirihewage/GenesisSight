import { Link } from "react-router-dom";
import { Film, Trash2 } from "lucide-react";
import { cn, formatDuration } from "@/lib/utils";
import type { Video } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

const STATUS_STYLES: Record<string, string> = {
  uploaded: "border-muted-foreground/40 text-muted-foreground",
  queued: "border-amber-500/40 text-amber-400",
  processing: "border-blue-500/40 text-blue-400",
  completed: "border-emerald-500/40 text-emerald-400",
  failed: "border-rose-500/40 text-rose-400",
};

export function StatusBadge({ status }: { status: string }) {
  return <Badge variant="outline" className={cn(STATUS_STYLES[status] ?? "")}>{status}</Badge>;
}

interface VideoCardProps {
  video: Video;
  onDelete?: (id: number) => void;
}

export function VideoCard({ video, onDelete }: VideoCardProps) {
  const processing = video.status === "processing" || video.status === "queued";
  const hasThumbnail = video.thumbnail_url && video.status === "completed";
  return (
    <Card className="group relative overflow-hidden transition-colors hover:border-primary/40">
      <Link to={`/videos/${video.id}`} className="block">
        <div className="flex aspect-video w-full items-center justify-center bg-gradient-to-br from-slate-900 to-slate-950">
          {hasThumbnail ? (
            <img
              src={video.thumbnail_url!}
              alt={video.filename}
              className="object-cover w-full h-full"
            />
          ) : (
            <Film className="h-10 w-10 text-muted-foreground/40" />
          )}
        </div>
        <div className="space-y-2 p-4">
          <div className="flex items-start justify-between gap-2">
            <div className="truncate text-sm font-medium" title={video.filename}>
              {video.filename}
            </div>
            <StatusBadge status={video.status} />
          </div>
          <div className="text-xs text-muted-foreground">
            {video.duration > 0 ? formatDuration(video.duration) : "—"}
            {video.width > 0 && ` · ${video.width}×${video.height}`}
            {video.status === "completed" && video.fps_processed > 0 && (
              <> · {video.fps_processed.toFixed(1)} fps</>
            )}
          </div>
          {processing && (
            <div className="space-y-1">
              <Progress value={video.progress} />
              <div className="flex justify-between text-[11px] text-muted-foreground">
                <span className="truncate pr-2">{video.current_stage || "Waiting…"}</span>
                <span>{video.progress.toFixed(0)}%</span>
              </div>
            </div>
          )}
          {video.status === "failed" && video.error && (
            <div className="truncate text-[11px] text-rose-400" title={video.error}>
              {video.error}
            </div>
          )}
        </div>
      </Link>
      {onDelete && (
        <Button
          variant="ghost"
          size="icon"
          className="absolute right-2 top-2 h-7 w-7 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 hover:text-rose-400"
          onClick={() => onDelete(video.id)}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      )}
    </Card>
  );
}
