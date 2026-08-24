import { Bot, Cpu, Database, FolderOpen, HardDrive, MemoryStick, ScanFace, FolderPlus, RotateCcw, ToggleLeft, ToggleRight, CheckCircle, AlertCircle } from "lucide-react";
import { useHealth } from "@/hooks/useApi";
import { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { Row } from "@/components/ui/settings-helpers";
import { useTheme } from "@/lib/theme";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

export function SystemStatus() {
  const { data: health, isLoading } = useHealth();
  const { setTheme, theme } = useTheme();
  const [settings, setSettings] = useState({
    default_watch_dir: "",
    auto_scan_new_videos: true,
  });
  const [watchDirInput, setWatchDirInput] = useState("");
  const [scanResult, setScanResult] = useState<{ found: number; added: number; message: string } | null>(null);
  const [scanning, setScanning] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.getWatchDir().then((data: any) => {
      setSettings(data);
      setWatchDirInput(data.default_watch_dir || "");
    });
  }, []);

  const handleSaveWatchDir = async () => {
    setSaving(true);
    try {
      const result = await api.setWatchDir(watchDirInput);
      setSettings(result);
      setScanResult(null);
    } catch (error) {
      console.error("Failed to save watch directory:", error);
    } finally {
      setSaving(false);
    }
  };

  const handleScanWatchDir = async () => {
    setScanning(true);
    setScanResult(null);
    try {
      const result = await api.scanWatchDir();
      setScanResult(result);
    } catch (error) {
      console.error("Failed to scan watch directory:", error);
      setScanResult({ found: 0, added: 0, message: "Scan failed" });
    } finally {
      setScanning(false);
    }
  };

  const handleAutoScanToggle = async (enabled: boolean) => {
    try {
      const result = await api.setAutoScanToggle(enabled);
      setSettings((prev) => ({ ...prev, auto_scan_new_videos: result.auto_scan_new_videos }));
    } catch (error) {
      console.error("Failed to toggle auto-scan:", error);
    }
  };

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
      {/* hardware */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Cpu className="h-4 w-4 text-primary" /> { "Hardware" }
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
            <MemoryStick className="h-4 w-4 text-primary" /> { "AI models" }
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2">
            <ScanFace className="h-4 w-4" />
            <span>
              <span className="font-medium">YOLO</span>: {health.yolo.name}
              {health.yolo.detail && <span className="text-xs text-muted-foreground">{health.yolo.detail}</span>}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <ScanFace className="h-4 w-4" />
            <span>
              <span className="font-medium">Re-ID</span>: {health.reid.name}
              {health.reid.detail && <span className="text-xs text-muted-foreground">{health.reid.detail}</span>}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <ScanFace className="h-4 w-4" />
            <span>
              <span className="font-medium">Ollama</span>: {health.ollama.name}
              {health.ollama.detail && <span className="text-xs text-muted-foreground">{health.ollama.detail}</span>}
            </span>
          </div>
          {health.ollama_models.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {health.ollama_models.map((m: any) => (
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
            <HardDrive className="h-4 w-4 text-primary" /> { "Storage" }
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

      {/* directory watching */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <FolderPlus className="h-4 w-4 text-primary" /> { "Directory Watching" }
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <Label htmlFor="watch-dir">CCTV Recording Folder</Label>
            <div className="flex gap-2">
              <Input
                id="watch-dir"
                type="text"
                placeholder="Enter path to CCTV recordings folder (e.g., C:\\Recordings or /mnt/cctv)"
                value={watchDirInput}
                onChange={(e) => setWatchDirInput(e.target.value)}
                className="flex-1"
              />
              <Button onClick={handleSaveWatchDir} disabled={saving}>
                {saving ? "Saving..." : "Save Folder"}
              </Button>
            </div>
            {settings.default_watch_dir && (
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <FolderOpen className="h-3.5 w-3.5" />
                Current: {settings.default_watch_dir}
              </p>
            )}
          </div>

          <Separator />

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <RotateCcw className="h-5 w-5 text-muted-foreground" />
              <div>
                <div className="font-medium">Auto-scan new videos</div>
                <p className="text-xs text-muted-foreground">
                  Automatically analyze videos when they appear in the watch folder
                </p>
              </div>
            </div>
            <Switch
              checked={settings.auto_scan_new_videos}
              onChange={(e) => handleAutoScanToggle(e.target.checked)}
              aria-label="Auto-scan new videos"
            />
          </div>

          <Separator />

          <div className="flex items-center gap-3">
            <Button onClick={handleScanWatchDir} disabled={scanning || !settings.default_watch_dir}>
              {scanning ? "Scanning..." : "Scan Folder Now"}
            </Button>
            {!settings.default_watch_dir && (
              <span className="text-xs text-muted-foreground">Set a watch folder first</span>
            )}
          </div>

          {scanResult && (
            <div
              className={`p-3 rounded-md text-sm ${
                scanResult.added > 0
                  ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                  : scanResult.found === 0
                  ? "bg-amber-50 text-amber-800 border border-amber-200"
                  : "bg-blue-50 text-blue-800 border border-blue-200"
              }`}
            >
              <div className="flex items-center gap-2">
                {scanResult.added > 0 ? (
                  <CheckCircle className="h-4 w-4" />
                ) : scanResult.found === 0 ? (
                  <AlertCircle className="h-4 w-4" />
                ) : (
                  <RotateCcw className="h-4 w-4" />
                )}
                <span className="font-medium">{scanResult.message}</span>
              </div>
              {scanResult.added > 0 && (
                <p className="text-xs mt-1 opacity-80">
                  {scanResult.added} new video{scanResult.added === 1 ? "" : "s"} queued for analysis
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* notes */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Database className="h-4 w-4 text-primary" /> { "Notes" }
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-xs text-muted-foreground">
          <Separator className="my-2" />
          <p className="flex items-center gap-1">
            <FolderOpen className="h-3.5 w-3.5" /> Storage path: {health.storage_dir}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}