import { useCallback, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileVideo, FolderOpen, Loader2, UploadCloud } from "lucide-react";
import { api } from "@/lib/api";
import { queryKeys } from "@/hooks/useApi";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

const ACCEPTED = [".avi", ".mp4", ".mkv", ".mov", ".m4v"];
const ACCEPTED_STR = "video/avi,.avi,video/mp4,.mp4,video/x-matroska,.mkv,video/quicktime,.mov,.m4v";

interface UploadedRow {
  id: number;
  filename: string;
  status: "uploaded" | "failed";
  error?: string;
}

export function Upload() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [overall, setOverall] = useState(0);
  const [current, setCurrent] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [autoAnalyze, setAutoAnalyze] = useState(true);
  const [done, setDone] = useState<UploadedRow[]>([]);

  const analyzeMutation = useMutation({
    mutationFn: api.analyze,
  });

  const validFiles = useCallback((files: File[] | FileList): File[] => {
    const list = Array.from(files).filter((f) => {
      const ext = f.name.slice(f.name.lastIndexOf(".")).toLowerCase();
      return ACCEPTED.includes(ext);
    });
    if (list.length !== Array.from(files).length) {
      setError("Some files were skipped — allowed types: AVI, MP4, MKV, MOV, M4V");
    }
    return list;
  }, []);

  const handleFiles = useCallback(
    async (files: File[] | FileList) => {
      const list = validFiles(files);
      if (list.length === 0) {
        setError("No supported video files selected.");
        return;
      }
      setError(null);
      setUploading(true);
      setDone([]);
      setOverall(0);
      const rows: UploadedRow[] = [];
      for (let i = 0; i < list.length; i++) {
        const file = list[i];
        setCurrent(file.name);
        try {
          const res = await api.uploadVideo(file, (pct) => {
            setOverall(Math.round(((i + pct / 100) / list.length) * 100));
          });
          queryClient.invalidateQueries({ queryKey: queryKeys.videos });
          if (autoAnalyze) {
            try {
              await analyzeMutation.mutateAsync(res.id);
            } catch {
              /* analysis queue failure is non-fatal for the upload */
            }
          }
          rows.push({ id: res.id, filename: file.name, status: "uploaded" });
        } catch (e) {
          rows.push({
            id: rows.length + 1,
            filename: file.name,
            status: "failed",
            error: e instanceof Error ? e.message : "Upload failed",
          });
        }
        setDone([...rows]);
        setOverall(Math.round(((i + 1) / list.length) * 100));
      }
      setUploading(false);
      setCurrent("");
    },
    [autoAnalyze, analyzeMutation, queryClient, validFiles],
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
            Drop files (or a whole folder) — analysis starts automatically on the GPU.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div
            role="button"
            tabIndex={0}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(e) => e.key === "Enter" && fileInputRef.current?.click()}
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
              "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-6 py-14 text-center transition-colors",
              dragOver
                ? "border-primary bg-primary/5"
                : "border-border hover:border-primary/50 hover:bg-accent/50",
            )}
          >
            {uploading ? (
              <>
                <Loader2 className="h-12 w-12 animate-spin text-primary" />
                <div className="w-full max-w-xs space-y-2">
                  <Progress value={overall} />
                  <div className="truncate text-sm text-muted-foreground">
                    Uploading {current}… {overall}%
                  </div>
                </div>
              </>
            ) : (
              <>
                <UploadCloud className="h-12 w-12 text-primary" />
                <div className="space-y-1">
                  <div className="text-sm font-medium">Drag & drop videos here</div>
                  <div className="text-xs text-muted-foreground">
                    or click to browse · {ACCEPTED.join(" ")}
                  </div>
                </div>
              </>
            )}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_STR}
            multiple
            className="hidden"
            onChange={(e) => e.target.files && handleFiles(e.target.files)}
          />
          <input
            ref={folderInputRef}
            type="file"
            className="hidden"
            multiple
            onChange={(e) => e.target.files && handleFiles(e.target.files)}
            {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
          />

          <div className="flex items-center justify-between rounded-md border border-border px-3 py-2.5">
            <div className="text-sm">
              <span className="font-medium">Upload an entire folder</span>
              <span className="ml-2 text-xs text-muted-foreground">
                e.g. a DVR export directory — every supported file is uploaded
              </span>
            </div>
            <Button variant="outline" size="sm" onClick={() => folderInputRef.current?.click()}>
              <FolderOpen className="mr-1.5 h-4 w-4" /> Choose folder…
            </Button>
          </div>

          {done.length > 0 && (
            <div className="max-h-56 space-y-1.5 overflow-y-auto rounded-md border border-border p-2">
              {done.map((row) => (
                <div
                  key={`${row.id}-${row.filename}`}
                  className="flex items-center justify-between gap-3 rounded px-2 py-1 text-sm"
                >
                  <span className="truncate text-muted-foreground">{row.filename}</span>
                  {row.status === "uploaded" ? (
                    <Link to={`/videos/${row.id}`} className="shrink-0 text-primary hover:underline">
                      View →
                    </Link>
                  ) : (
                    <span className="shrink-0 text-destructive" title={row.error}>
                      failed
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}

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
              Analysis runs entirely on this PC — no video data leaves the machine.
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