import { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, PlayCircle, Tag, UserRound } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cn, EVENT_TYPE_COLORS, EVENT_TYPE_LABELS, formatTimestamp } from "@/lib/utils";
import { api } from "@/lib/api";
import { queryKeys } from "@/hooks/useApi";
import type { CctvEvent } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Lightbox } from "@/components/Lightbox";

interface EventItemProps {
  event: CctvEvent;
  showVideoLink?: boolean;
  score?: number;
  /** when provided, clicking the row / "Jump to" seeks the video player */
  onSeek?: (timestamp: number) => void;
  /** enables the tag/note annotation editor (video page only) */
  allowAnnotate?: boolean;
}

export function EventItem({ event, showVideoLink, score, onSeek, allowAnnotate }: EventItemProps) {
  const typeLabel = EVENT_TYPE_LABELS[event.event_type] ?? event.event_type.replace("person_", "");
  const [lightboxSrc, setLightboxSrc] = useState<string | null>(null);
  const [annotating, setAnnotating] = useState(false);
  const [tagsText, setTagsText] = useState((event.tags ?? []).join(", "));
  const [note, setNote] = useState(event.note ?? "");
  const queryClient = useQueryClient();

  const patchMutation = useMutation({
    mutationFn: (body: { tags?: string[]; tag?: string; note?: string }) =>
      api.patchEvent(event.video_id, event.id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.events(event.video_id, "*") });
      setAnnotating(false);
    },
  });

  const saveAnnotate = () => {
    const tags = tagsText
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    const body: { tags?: string[]; note?: string } = { note: note.trim() };
    if (allowAnnotate) body.tags = tags;
    patchMutation.mutate(body);
  };

  return (
    <Card
      className={cn(
        "overflow-hidden transition-colors",
        onSeek ? "cursor-pointer hover:border-primary/40" : "hover:border-primary/40",
      )}
      onClick={onSeek ? () => onSeek(event.timestamp) : undefined}
    >
      <div className="flex gap-4 p-4">
        {/* thumbnail */}
        <div
          className="flex h-20 w-32 shrink-0 cursor-zoom-in items-center justify-center overflow-hidden rounded-md bg-slate-900"
          onClick={(e) => {
            if (onSeek) e.stopPropagation();
            if (event.image_url) setLightboxSrc(event.image_url);
          }}
        >
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
            {onSeek && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-xs"
                onClick={(e) => {
                  e.stopPropagation();
                  onSeek(event.timestamp);
                }}
              >
                <PlayCircle className="mr-1 h-3.5 w-3.5" /> Jump to
              </Button>
            )}
          </div>
          <p className="text-sm text-foreground">{event.description}</p>
          <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            {event.objects.length > 0 && <span>Objects: {event.objects.join(", ")}</span>}
            {event.activity && <span>Activity: {event.activity}</span>}
            <span>Confidence: {(event.confidence * 100).toFixed(0)}%</span>
            {showVideoLink && (
              <Link
                to={`/videos/${event.video_id}`}
                className="text-primary hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                Open video →
              </Link>
            )}
          </div>

          {/* user annotations */}
          {event.tags.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              {event.tags.map((t) => (
                <Badge key={t} variant="outline" className="border-amber-500/30 text-amber-400">
                  {t}
                </Badge>
              ))}
            </div>
          )}
          {event.note && (
            <p className="rounded-md border border-border bg-muted/40 px-3 py-1.5 text-xs italic text-muted-foreground">
              {event.note}
            </p>
          )}

          {allowAnnotate && annotating && (
            <div className="space-y-2" onClick={(e) => e.stopPropagation()}>
              <Input
                value={tagsText}
                onChange={(e) => setTagsText(e.target.value)}
                placeholder="Tags, comma separated (e.g. intruder, garage)"
              />
              <Textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Explanation for later analysis…"
                rows={2}
              />
              <div className="flex gap-2">
                <Button size="sm" onClick={saveAnnotate} disabled={patchMutation.isPending}>
                  {patchMutation.isPending ? "Saving…" : "Save"}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setAnnotating(false);
                    setTagsText((event.tags ?? []).join(", "));
                    setNote(event.note ?? "");
                  }}
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* full frame */}
        {event.image_url && (
          <div
            className="hidden h-20 w-32 shrink-0 cursor-zoom-in items-center justify-center overflow-hidden rounded-md bg-slate-900 md:flex"
            onClick={(e) => {
              if (onSeek) e.stopPropagation();
              setLightboxSrc(event.image_url);
            }}
          >
            <img
              src={event.image_url}
              alt={event.description}
              className="h-full w-full object-cover"
              loading="lazy"
            />
          </div>
        )}
      </div>

      {allowAnnotate && !annotating && (
        <div className="border-t border-border px-4 py-2">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs text-muted-foreground"
            onClick={(e) => {
              e.stopPropagation();
              setAnnotating(true);
            }}
          >
            {event.tags.length > 0 || event.note ? (
              <ChevronDown className="mr-1 h-3.5 w-3.5" />
            ) : (
              <Tag className="mr-1 h-3.5 w-3.5" />
            )}
            {event.tags.length > 0 || event.note
              ? "Edit tags / explanation"
              : "Add tags / explanation"}
          </Button>
        </div>
      )}

      <Lightbox src={lightboxSrc} alt={event.description} onClose={() => setLightboxSrc(null)} />
    </Card>
  );
}