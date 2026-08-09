import { Bot, Cpu, Database, FolderOpen, HardDrive, MemoryStick, ScanFace } from "lucide-react";
import { useHealth } from "@/hooks/useApi";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";

export function Settings() {
  const { data: health, isLoading } = useHealth();

  if (isLoading || !health) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-40 w-full rounded-lg" />
        <Skeleton className="h-72 w-full rounded-lg" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings & system status</h1>
        <p className="text-sm text-muted-foreground">
          Hardware, models and local AI services — everything runs on this machine.
        </p>
      </div>

      {/* hardware */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Cpu className="h-4 w-4 text-primary" /> Hardware
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <Row label="GPU" value={health.gpu_name ?? "Not detected"} ok={health.cuda_available} />
          <Row label="CUDA" value={health.cuda_available ? "Available" : "Unavailable (falling back to CPU)"} ok={health.cuda_available} />
          <Row label="Torch device" value={health.device} ok />
          <Row label="PyTorch version" value={health.torch_version ?? "n/a"} ok />
        </CardContent>
      </Card>

      {/* AI models */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <MemoryStick className="h-4 w-4 text-primary" /> AI models
          </CardTitle>
          <CardDescription>Model availability is checked live. Missing pieces degrade gracefully — no silent placeholders.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <ModelRow
            icon={ScanFace}
            name={health.yolo.name}
            available={health.yolo.available}
            detail={health.yolo.detail}
          />
          <ModelRow
            icon={ScanFace}
            name={health.reid.name}
            available={health.reid.available}
            detail={health.reid.detail}
          />
          <ModelRow
            icon={Bot}
            name={health.ollama.name}
            available={health.ollama.available}
            detail={health.ollama.detail}
          />
          {health.ollama_models.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {health.ollama_models.map((m) => (
                <Badge key={m} variant="outline">{m}</Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* storage */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <HardDrive className="h-4 w-4 text-primary" /> Storage
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <Row
            label="Storage used"
            value={`${health.storage_used_mb.toFixed(1)} MB (${health.videos} video${health.videos === 1 ? "" : "s"})`}
            ok
          />
          <Row label="Data directory" value={health.storage_dir} ok />
        </CardContent>
      </Card>

      {/* notes */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Database className="h-4 w-4 text-primary" /> Notes
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-xs text-muted-foreground">
          <p>• Analysis pipeline: motion gate → YOLO11x (batched) → ByteTrack → Re-ID → rule events → Qwen2.5-VL.</p>
          <p>• The VLM only receives important event keyframes, never every frame.</p>
          <p>• Search uses Ollama embeddings when available, keyword matching otherwise.</p>
          <p>• Database: SQLite (PostgreSQL-compatible schema). Set <code className="rounded bg-muted px-1">DATABASE_URL</code> in .env to switch.</p>
          <Separator className="my-2" />
          <p className="flex items-center gap-1"><FolderOpen className="h-3.5 w-3.5" /> Storage path: {health.storage_dir}</p>
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ label, value, ok = true }: { label: string; value: string; ok?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="flex items-center gap-2 text-right">
        <span className="break-all">{value}</span>
        <span className={`h-2 w-2 shrink-0 rounded-full ${ok ? "bg-emerald-500" : "bg-rose-500"}`} />
      </span>
    </div>
  );
}

function ModelRow({ icon: Icon, name, available, detail }: { icon: typeof Cpu; name: string; available: boolean; detail: string }) {
  return (
    <div className="flex items-start gap-3 rounded-md border border-border bg-muted/30 px-3 py-3">
      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${available ? "text-primary" : "text-rose-400"}`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{name}</span>
          <Badge variant={available ? "success" : "destructive"}>{available ? "ready" : "unavailable"}</Badge>
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">{detail}</p>
      </div>
    </div>
  );
}
