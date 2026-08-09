import { Link } from "react-router-dom";
import { UserRound } from "lucide-react";
import { cn, EVENT_TYPE_COLORS, EVENT_TYPE_LABELS, formatTimestamp } from "@/lib/utils";
import type { CctvEvent } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

interface EventItemProps {
  event: CctvEvent;
  showVideoLink?: boolean;
  score?: number;
}

export function EventItem({ event, showVideoLink, score }: EventItemProps) {
  const typeLabel = EVENT_TYPE_LABELS[event.event_type] ?? event.event_type.replace("person_", "");
  return (
    <Card className="overflow-hidden transition-colors hover:border-primary/40">
      <div className="flex gap-4 p-4">
        {/* thumbnail */}
        <div className="flex h-20 w-32 shrink-0 items-center justify-center overflow-hidden rounded-md bg-slate-900">
          {event.thumbnail_url ? (
            <img
              src={event.thumbnail_url}
              alt={event.description}
              className="h-full w-full object-cover"
              loading="lazy"
            />
          ) : (
            <UserRound className="h-8 w-8 text-muted-foreground/40" />
          )}
        </div>

        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm font-semibold text-primary">
              {formatTimestamp(event.timestamp)}
            </span>
            <Badge variant="outline" className={cn(EVENT_TYPE_COLORS[event.event_type])}>
              {typeLabel}
            </Badge>
            {event.person_id !== null && (
              <Badge variant="secondary">Person #{event.person_id}</Badge>
            )}
            {score !== undefined && (
              <Badge variant="outline" className="border-primary/40 text-primary">
                {(score * 100).toFixed(0)}% match
              </Badge>
            )}
          </div>
          <p className="text-sm text-foreground">{event.description}</p>
          <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            {event.objects.length > 0 && (
              <span>Objects: {event.objects.join(", ")}</span>
            )}
            {event.activity && <span>Activity: {event.activity}</span>}
            <span>Confidence: {(event.confidence * 100).toFixed(0)}%</span>
            {showVideoLink && (
              <Link to={`/videos/${event.video_id}`} className="text-primary hover:underline">
                Open video →
              </Link>
            )}
          </div>
        </div>

        {/* full frame */}
        {event.image_url && (
          <div className="hidden h-20 w-32 shrink-0 items-center justify-center overflow-hidden rounded-md bg-slate-900 md:flex">
            <img
              src={event.image_url}
              alt={event.description}
              className="h-full w-full object-cover"
              loading="lazy"
            />
          </div>
        )}
      </div>
    </Card>
  );
}
