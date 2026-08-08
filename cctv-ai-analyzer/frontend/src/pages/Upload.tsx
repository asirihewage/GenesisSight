import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileVideo, Loader2, UploadCloud } from "lucide-react";
import { api } from "@/lib/api";
import { queryKeys } from "@/hooks/useApi";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

const ACCEPTED = [".avi", ".mp4", ".mkv", ".mov", ".m4v"];
const ACCEPTED_STR = "video/avi,.avi,video/mp4,.mp4,video/x-matroska,.mkv,video/quicktime,.mov,.m4v";

export function Upload() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [autoAnalyze, setAutoAnalyze] = useState(true);

  const analyzeMutation = useMutation({
    mutationFn: api.analyze,
  });

  const handleFiles = useCallback(
    async (files: FileList | File[]) => {
      const file = Array.from(files)[0];
      if (!file) return;
      const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
      if (!ACCEPTED.includes(ext)) {
        setError(`Unsupported file type "${ext}". Allowed: ${ACCEPTED.join(", ")}`);
        return;
      }
      setError(null);
      setUploading(true);
      setProgress(0);
      try {
        const res = await api.uploadVideo(file, setProgress);
        queryClient.invalidateQueries({ queryKey: queryKeys.videos });
        if (autoAnalyze) {
          await analyzeMutation.mutateAsync(res.id);
        }
        navigate(`/videos/${res.id}`);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Upload failed");
        setUploading(false);
      }
    },
    [autoAnalyze, analyzeMutation, navigate, queryClient],
  );

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Upload CCTV footage</h1>
        <p className="text-sm text-muted-foreground">AVI, MP4, MKV or MOV — processed entirely on this PC.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Upload video</CardTitle>
          <CardDescription>
            Large files are uploaded chunk-by-chunk. Analysis starts automatically on the GPU.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div
            role="button"
            tabIndex={0}
            onClick={() => inputRef.current?.click()}
            onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              handleFiles(e.dataTransfer.files);
            }}
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-6 py-16 text-center transition-colors",
              dragOver
                ? "border-primary bg-primary/5"
                : "border-border hover:border-primary/50 hover:bg-accent/50",
            )}
          >
            {uploading ? (
              <>
                <Loader2 className="h-12 w-12 animate-spin text-primary" />
                <div className="w-full max-w-xs space-y-2">
                  <Progress value={progress} />
                  <div className="text-sm text-muted-foreground">Uploading… {progress}%</div>
                </div>
              </>
            ) : (
              <>
                <UploadCloud className="h-12 w-12 text-primary" />
                <div className="space-y-1">
                  <div className="text-sm font-medium">Drag & drop a video here</div>
                  <div className="text-xs text-muted-foreground">
                    or click to browse · {ACCEPTED.join(" ")}
                  </div>
                </div>
              </>
            )}
          </div>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED_STR}
            className="hidden"
            onChange={(e) => e.target.files && handleFiles(e.target.files)}
          />

          {error && (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}

          <div className="flex items-center justify-between rounded-md border border-border px-3 py-3">
            <div>
              <div className="text-sm font-medium">Analyze after upload</div>
              <div className="text-xs text-muted-foreground">
                Automatically start person detection and event timeline generation.
              </div>
            </div>
            <button
              type="button"
              onClick={() => setAutoAnalyze((v) => !v)}
              className={cn(
                "relative h-6 w-11 rounded-full transition-colors",
                autoAnalyze ? "bg-primary" : "bg-muted",
              )}
              aria-label="Toggle auto analysis"
            >
              <span
                className={cn(
                  "absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all",
                  autoAnalyze ? "left-[22px]" : "left-0.5",
                )}
              />
            </button>
          </div>

          <div className="flex items-start gap-3 rounded-md border border-border bg-muted/40 px-3 py-3 text-xs text-muted-foreground">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
            <span>
              <span className="font-medium text-foreground">Local AI pipeline:</span> YOLO11x detection →
              ByteTrack tracking → person re-identification → event timeline → Qwen2.5-VL descriptions
              (via Ollama). Nothing leaves this PC.
            </span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Pipeline preview</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2 text-xs">
          {["Frame extraction", "Motion detection", "YOLO11x detection", "ByteTrack tracking",
            "Re-ID identity matching", "Event generation", "Qwen2.5-VL analysis", "Timeline search"].map(
            (step, i, arr) => (
              <span key={step} className="flex items-center gap-2">
                <span className="rounded-md border border-border bg-card px-2 py-1 text-muted-foreground">
                  {step}
                </span>
                {i < arr.length - 1 && <FileVideo className="h-3 w-3 text-muted-foreground/50" />}
              </span>
            ),
          )}
        </CardContent>
      </Card>
    </div>
  );
}
