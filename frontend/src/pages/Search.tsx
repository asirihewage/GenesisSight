import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Search as SearchIcon, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import type { SearchResponse } from "@/types";
import { EventItem } from "@/components/EventItem";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const SUGGESTIONS = [
  "Find person carrying a backpack",
  "Show all events where someone entered",
  "Who was running?",
  "Events where a person left the area",
  "Anyone standing still for a long time",
  "Person moving right through the warehouse",
];

export function Search() {
  const [query, setQuery] = useState("");
  const [lastQuery, setLastQuery] = useState("");

  const searchMutation = useMutation({
    mutationFn: (q: string) => api.search(q),
  });

  const results: SearchResponse | undefined = searchMutation.data;
  const isSearching = searchMutation.isPending;

  const run = (q: string) => {
    const trimmed = q.trim();
    if (!trimmed || isSearching) return;
    setLastQuery(trimmed);
    searchMutation.mutate(trimmed);
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Event search</h1>
        <p className="text-sm text-muted-foreground">
          Describe what you are looking for in plain English — search is powered by local AI embeddings.
        </p>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          run(query);
        }}
      >
        <div className="flex gap-2">
          <div className="relative flex-1">
            <SearchIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. Find person carrying a backpack"
              className="pl-9"
            />
          </div>
          <Button type="submit" disabled={isSearching || !query.trim()}>
            {isSearching ? <Loader2 className="animate-spin" /> : <SearchIcon />}
            {isSearching ? "Searching…" : "Search"}
          </Button>
        </div>
      </form>

      <div className="flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button key={s} type="button" onClick={() => { setQuery(s); run(s); }}>
            <Badge variant="outline" className="cursor-pointer text-muted-foreground hover:border-primary/50 hover:text-foreground">
              {s}
            </Badge>
          </button>
        ))}
      </div>

      {isSearching && (
        <Card className="flex items-center justify-center gap-3 py-16 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <span className="text-sm">Analyzing descriptions with local embeddings…</span>
        </Card>
      )}

      {results && !isSearching && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              <span className="font-medium text-foreground">"{lastQuery}"</span> — {results.results.length} result{results.results.length === 1 ? "" : "s"}
            </span>
            <Badge variant="outline" className="flex items-center gap-1 border-primary/40 text-primary">
              <Sparkles className="h-3 w-3" />
              {results.method === "ollama_embedding" ? "semantic match (Ollama)" : "keyword match (offline)"}
            </Badge>
          </div>

          {results.results.length === 0 ? (
            <Card className="py-12 text-center text-sm text-muted-foreground">
              No matching events found. Try different wording, or analyze a video first.
            </Card>
          ) : (
            <div className="space-y-3">
              {results.results.map(({ event, score }) => (
                <EventItem key={event.id} event={event} showVideoLink score={score} />
              ))}
            </div>
          )}
        </div>
      )}

      {!results && !isSearching && (
        <Card className="py-12 text-center text-sm text-muted-foreground">
          <div className="mb-2">Example queries:</div>
          <div className="space-y-1 text-xs">
            <div>“Show all events where someone entered with a bag”</div>
            <div>“Person exited the warehouse quickly”</div>
            <div>“Anyone loitering near the entrance?”</div>
          </div>
        </Card>
      )}
    </div>
  );
}
