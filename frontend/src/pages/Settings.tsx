import { Bot, Cpu, Database, FolderOpen, HardDrive, MemoryStick, ScanFace } from "lucide-react";
import { useHealth } from "@/hooks/useApi";
import { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

export function Settings() {
  const { data: health, isLoading } = useHealth();
  const [settings, setSettings] = useState({
    default_watch_dir: "",
    auto_scan_new_videos: true,
  });

  useEffect(() => {
    api.getWatchDir().then((data) => setSettings(data));
  }, []);

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
          <Separator className="my-2" />
          <p className="flex items-center gap-1"><FolderOpen className="h-3.5 w-3.5" /> Storage path: {health.storage_dir}</p>
        </CardContent>
      </Card>

      {/* directory watching */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <FolderOpen className="h-4 w-4 text-primary" /> Directory Watching
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <p className="text-muted-foreground">
            Monitor a directory for new video files and auto-analyze them.
          </p>
          <div className="grid gap-2 md:grid-cols-2">
            <div>
              <label className="block text-sm font-medium mb-1">
                Watch directory
              </label>
              <input
                type="text"
                id="watch-dir-input"
                value={settings.default_watch_dir || ""}
                onChange={(e) => setSettings((s) => ({ ...s, default_watch_dir: e.target.value }))}
                className="w-full rounded-md border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                readOnly
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  if (!settings.default_watch_dir) {
                    api.setWatchDir(settings.storage_dir).then(() => api.getWatchDir().then(setSettings));
                  } else {
                    api.setWatchDir("").then(() => api.getWatchDir().then(setSettings));
                  }
                }}
                className="mt-1 w-full"
                title={settings.default_watch_dir ? "Clear watch directory" : "Set to storage dir"}
              >
                {settings.default_watch_dir ? "Clear" : "Set to storage dir"}
              </Button>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">
                Auto-scan new files
              </label>
              <div className="flex items-center gap-2">
                <span className={settings.auto_scan_new_videos ? "text-primary" : "text-muted-foreground"}>
                  {settings.auto_scan_new_videos ? "Enabled" : "Disabled"}
                </span>
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                  className="cursor-pointer hover:text-primary transition-colors"
                  onClick={() => {
                    api.setAutoScanToggle(!settings.auto_scan_new_videos).then(() => api.getWatchDir().then(setSettings));
                  }}
                >
                  <path d="M5 13l4 4L19 7" />
                </svg>
              </div>
            </div>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => api.scanWatchDir()}
            disabled={!settings.default_watch_dir}
            className="w-full mt-2">
            {settings.default_watch_dir ? "Scan now" : "Set a watch directory first"}
          </Button>
          <div className="mt-2 text-xs text-muted-foreground" id="watch-dir-status">
            {settings.default_watch_dir && "Watch directory is active - use Scan now to check for new files"}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function setAutoScanToggle(enabled: boolean) {
  api.setAutoScanToggle(enabled).then(() => api.getWatchDir().then(setSettings));
}