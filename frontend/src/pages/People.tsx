import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, Sparkles, Tag, Users, X } from "lucide-react";
import { api } from "@/lib/api";
import { queryKeys, usePersons } from "@/hooks/useApi";
import type { Person, SimilarPerson } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Lightbox } from "@/components/Lightbox";
import { cn } from "@/lib/utils";

export function People() {
  const { data: persons, isLoading } = usePersons();
  const [lightbox, setLightbox] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<Record<number, string>>({});
  const [similar, setSimilar] = useState<Record<number, SimilarPerson[]>>({});
  const [similarLoading, setSimilarLoading] = useState<number | null>(null);
  const queryClient = useQueryClient();

  const renameMutation = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) => api.renamePerson(id, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.persons() });
      setRenaming({});
    },
  });

  const findSimilar = async (id: number) => {
    setSimilarLoading(id);
    try {
      const matches = await api.personSimilar(id);
      setSimilar((prev) => ({ ...prev, [id]: matches }));
    } finally {
      setSimilarLoading(null);
    }
  };

  const nameOf = (p: Person) => renaming[p.id] ?? p.name ?? "";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">People</h1>
        <p className="text-sm text-muted-foreground">
          Name people to tag them. Re-ID embeddings let you find similar-looking people across
          videos — tag those too.
        </p>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-64 rounded-lg" />)}
        </div>
      ) : (persons ?? []).length === 0 ? (
        <Card className="flex flex-col items-center gap-3 border-dashed py-16 text-center">
          <Users className="h-12 w-12 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">
            No people yet — analyze a video with Re-ID enabled to build a people list.
          </p>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {(persons ?? []).map((p) => (
            <PersonCard
              key={p.id}
              person={p}
              renaming={nameOf(p)}
              onRenameChange={(v) => setRenaming((prev) => ({ ...prev, [p.id]: v }))}
              onSaveName={() => {
                const v = nameOf(p).trim();
                renameMutation.mutate({ id: p.id, name: v });
              }}
              onClearName={() => {
                setRenaming((prev) => ({ ...prev, [p.id]: p.name ?? "" }));
              }}
              hasName={!!p.name}
              similar={similar[p.id]}
              similarLoading={similarLoading === p.id}
              onFindSimilar={() => findSimilar(p.id)}
              onOpen={(src) => setLightbox(src)}
              onTagSimilar={(id, name) => setNameFor(id, name, renameMutation.mutate)}
            />
          ))}
        </div>
      )}

      <Lightbox src={lightbox} alt="Person" onClose={() => setLightbox(null)} />
    </div>
  );
}

function setNameFor(
  id: number,
  name: string,
  mutate: (args: { id: number; name: string }) => void,
) {
  mutate({ id, name });
}

interface PersonCardProps {
  person: Person;
  renaming: string;
  onRenameChange: (v: string) => void;
  onSaveName: () => void;
  onClearName: () => void;
  hasName: boolean;
  similar?: SimilarPerson[];
  similarLoading: boolean;
  onFindSimilar: () => void;
  onOpen: (src: string) => void;
  onTagSimilar: (id: number, name: string) => void;
}

function PersonCard(props: PersonCardProps) {
  const {
    person: p, renaming, onRenameChange, onSaveName, onClearName, hasName,
    similar, similarLoading, onFindSimilar, onOpen, onTagSimilar,
  } = props;
  const tagAllName = renaming.trim();

  return (
    <Card className="overflow-hidden">
      <div className="flex items-start gap-4 p-4">
        <button
          className="h-20 w-20 shrink-0 cursor-zoom-in overflow-hidden rounded-md bg-slate-900"
          onClick={() => p.thumbnail_url && onOpen(p.thumbnail_url)}
        >
          {p.thumbnail_url ? (
            <img src={p.thumbnail_url} alt={`Person ${p.id}`} className="h-full w-full object-cover" />
          ) : (
            <Users className="m-auto h-8 w-8 text-muted-foreground/40" />
          )}
        </button>
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className={cn("text-sm font-semibold", p.name ? "text-foreground" : "text-muted-foreground")}>
              {p.name ?? `Person #${p.id}`}
            </span>
            {hasName && <Badge variant="outline" className="border-amber-500/30 text-amber-400">tagged</Badge>}
          </div>
          <div className="flex flex-wrap gap-x-3 text-xs text-muted-foreground">
            <span>{p.event_count} events</span>
            {p.video_id && (
              <Link to={`/videos/${p.video_id}`} className="text-primary hover:underline">
                video #{p.video_id}
              </Link>
            )}
          </div>

          <div className="flex gap-1.5">
            <Input
              value={renaming}
              onChange={(e) => onRenameChange(e.target.value)}
              placeholder="Name this person…"
              className="h-8 text-sm"
              onKeyDown={(e) => {
                if (e.key === "Enter") onSaveName();
                if (e.key === "Escape") onClearName();
              }}
            />
            <Button size="sm" className="h-8" onClick={onSaveName} disabled={!tagAllName}>
              <Tag className="mr-1 h-3.5 w-3.5" /> Save
            </Button>
          </div>

          <Button variant="outline" size="sm" onClick={onFindSimilar} disabled={similarLoading}>
            {similarLoading ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Sparkles className="mr-1.5 h-3.5 w-3.5" />
            )}
            Find similar people
          </Button>
        </div>
      </div>

      {similar && (
        <div className="space-y-1.5 border-t border-border bg-muted/30 p-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">
              {similar.length === 0
                ? "No matches above the Re-ID threshold (0.70)"
                : `${similar.length} similar appearance${similar.length > 1 ? "s" : ""}`}
            </span>
            {tagAllName && similar.length > 0 && (
              <button
                className="text-xs font-medium text-primary hover:underline"
                onClick={() => similar.forEach(({ person }) => onTagSimilar(person.id, tagAllName))}
              >
                Tag all as “{tagAllName}”
              </button>
            )}
          </div>
          {similar.map(({ person: sp, score }) => (
            <div key={sp.id} className="flex items-center gap-2.5 rounded-md bg-card px-2 py-1.5">
              {sp.thumbnail_url ? (
                <img src={sp.thumbnail_url} alt="" className="h-8 w-8 rounded object-cover" />
              ) : (
                <Users className="h-8 w-8 rounded bg-slate-800 p-1.5 text-muted-foreground/50" />
              )}
              <div className="min-w-0 flex-1">
                <div className="truncate text-xs font-medium">{sp.name ?? `Person #${sp.id}`}</div>
                <div className="text-[11px] text-muted-foreground">
                  {(score * 100).toFixed(0)}% match · {sp.event_count} events
                </div>
              </div>
              <button
                className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
                title={sp.name ? `Rename to ${tagAllName || "unnamed"}` : "Tag with current name"}
                onClick={() => onTagSimilar(sp.id, tagAllName)}
              >
                <Check className="h-3.5 w-3.5" />
              </button>
              <button
                className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
                title="Clear name"
                onClick={() => onTagSimilar(sp.id, "")}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}