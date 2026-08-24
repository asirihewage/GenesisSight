import { Bot, Cpu, Database, FolderOpen, HardDrive, MemoryStick, ScanFace, Globe, Clock, Users, Car, PawPrint, RotateCcw, ChevronDown, User, Shield, Eye, Brain, Palette, Dog, Cat, Bird, Truck, Bus, Bike } from "lucide-react";
import { useHealth } from "@/hooks/useApi";
import { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/lib/theme";
import { Row } from "@/components/ui/settings-helpers";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select } from "@/components/ui/select";

const LANGUAGES = [
  { code: "en", name: "English" },
  { code: "es", name: "Español" },
  { code: "fr", name: "Français" },
  { code: "de", name: "Deutsch" },
  { code: "zh", name: "中文" },
  { code: "ja", name: "日本語" },
  { code: "ko", name: "한국어" },
  { code: "ru", name: "Русский" },
  { code: "ar", name: "العربية" },
  { code: "hi", name: "हिन्दी" },
  { code: "ta", name: "தமிழ்" },
  { code: "si", name: "සිංහල" },
];

const SCHEDULE_PRESETS = [
  { value: "", label: "Disabled (manual only)" },
  { value: "0 * * * *", label: "Hourly" },
  { value: "0 2 * * *", label: "Daily at 2:00 AM" },
  { value: "0 3 * * 0", label: "Weekly on Sunday at 3:00 AM" },
  { value: "0 4 1 * *", label: "Monthly on 1st at 4:00 AM" },
];

export function Settings() {
  const { data: health, isLoading } = useHealth();
  const { setTheme, theme } = useTheme();
  const [settings, setSettings] = useState({
    default_watch_dir: "",
    auto_scan_new_videos: true,
    // People
    detect_people: true,
    detect_faces: true,
    detect_person_attributes: false,
    detect_behavior: true,
    // Vehicles
    detect_vehicles: true,
    detect_license_plates: true,
    detect_vehicle_color: true,
    detect_vehicle_make_model: false,
    // Animals
    detect_animals: false,
    detect_dogs: true,
    detect_cats: true,
    detect_birds: true,
    language: "en",
    auto_scan_schedule: "",
    auto_scan_enabled: false,
  });
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    api.getSettings().then((data: any) => setSettings(data));
  }, []);

  const handleSaveDetection = async () => {
    setSaving("detection");
    try {
      const result = await api.setDetectionPreferences({
        detect_people: settings.detect_people,
        detect_faces: settings.detect_faces,
        detect_person_attributes: settings.detect_person_attributes,
        detect_behavior: settings.detect_behavior,
        detect_vehicles: settings.detect_vehicles,
        detect_license_plates: settings.detect_license_plates,
        detect_vehicle_color: settings.detect_vehicle_color,
        detect_vehicle_make_model: settings.detect_vehicle_make_model,
        detect_animals: settings.detect_animals,
        detect_dogs: settings.detect_dogs,
        detect_cats: settings.detect_cats,
        detect_birds: settings.detect_birds,
      });
      setSettings((s) => ({ ...s, ...result }));
    } catch (error) {
      console.error("Failed to save detection preferences:", error);
    } finally {
      setSaving(null);
    }
  };

  const handleSaveLanguage = async () => {
    setSaving("language");
    try {
      const result = await api.setLanguage(settings.language);
      setSettings((s) => ({ ...s, ...result }));
    } catch (error) {
      console.error("Failed to save language:", error);
    } finally {
      setSaving(null);
    }
  };

  const handleSaveScheduler = async () => {
    setSaving("scheduler");
    try {
      const result = await api.setScheduler({
        auto_scan_schedule: settings.auto_scan_schedule,
        auto_scan_enabled: settings.auto_scan_enabled,
      });
      setSettings((s) => ({ ...s, ...result }));
    } catch (error) {
      console.error("Failed to save scheduler:", error);
    } finally {
      setSaving(null);
    }
  };

  const handleWatchDirChange = async (dir: string) => {
    setSaving("watchdir");
    try {
      const result = await api.setWatchDir(dir);
      setSettings((s) => ({ ...s, ...result }));
    } catch (error) {
      console.error("Failed to save watch directory:", error);
    } finally {
      setSaving(null);
    }
  };

  const handleAutoScanToggle = async () => {
    setSaving("autoscan");
    try {
      const result = await api.setAutoScanToggle(!settings.auto_scan_new_videos);
      setSettings((s) => ({ ...s, ...result }));
    } catch (error) {
      console.error("Failed to toggle auto-scan:", error);
    } finally {
      setSaving(null);
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
      {/* directory watching */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <FolderOpen className="h-4 w-4 text-primary" /> { "Directory Watching" }
          </CardTitle>
          <CardDescription>Monitor a directory for new video files and auto-analyze them.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="watch-dir">Watch Directory</Label>
              <div className="flex gap-2 mt-1">
                <Input
                  id="watch-dir"
                  type="text"
                  value={settings.default_watch_dir || ""}
                  onChange={(e) => setSettings((s) => ({ ...s, default_watch_dir: e.target.value }))}
                  className="flex-1"
                  placeholder="Enter path to watch..."
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleWatchDirChange(settings.default_watch_dir ? "" : health.storage_dir)}
                  disabled={saving === "watchdir"}
                >
                  {settings.default_watch_dir ? "Clear" : "Set to storage dir"}
                </Button>
              </div>
            </div>
            <div>
              <Label htmlFor="auto-scan">Auto-scan New Files</Label>
              <div className="flex items-center gap-2 mt-1">
                <Switch
                  id="auto-scan"
                  checked={settings.auto_scan_new_videos}
                  onChange={(e) => handleAutoScanToggle()}
                  disabled={saving === "autoscan"}
                />
                <span className="text-sm">
                  {settings.auto_scan_new_videos ? "Enabled" : "Disabled"}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => api.scanWatchDir()}
              disabled={!settings.default_watch_dir || saving === "scan"}
            >
              {settings.default_watch_dir ? "Scan Now" : "Set a watch directory first"}
            </Button>
          </div>

          <div className="text-xs text-muted-foreground">
            {settings.default_watch_dir && "Watch directory is active - use Scan Now to check for new files"}
          </div>
        </CardContent>
      </Card>

      {/* detection preferences */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <ScanFace className="h-4 w-4 text-primary" /> { "Detection Preferences" }
          </CardTitle>
          <CardDescription>Configure what to detect and analyze. Master toggles control sub-features.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* People Section */}
          <div className="space-y-4">
            <div className="flex items-center gap-3 p-3 border rounded-lg bg-muted/30">
              <Users className="h-6 w-6 text-primary" />
              <div className="flex-1">
                <Label className="font-medium text-lg">People Detection</Label>
                <p className="text-xs text-muted-foreground">Person detection, tracking, Re-ID, and events</p>
              </div>
              <Switch
                checked={settings.detect_people}
                onChange={(e) => setSettings((s) => ({ ...s, detect_people: e.target.checked }))}
              />
            </div>
            {settings.detect_people && (
              <div className="grid gap-3 md:grid-cols-3 pl-9 border-l-2 border-border/50">
                <div className="flex items-center gap-3 p-3 border rounded-lg hover:bg-accent/50 transition-colors">
                  <User className="h-5 w-5 text-sky-500" />
                  <div className="flex-1">
                    <Label className="font-medium">Face Detection</Label>
                    <p className="text-xs text-muted-foreground">Detect and crop faces for identification</p>
                  </div>
                  <Switch
                    checked={settings.detect_faces}
                    onChange={(e) => setSettings((s) => ({ ...s, detect_faces: e.target.checked }))}
                  />
                </div>
                <div className="flex items-center gap-3 p-3 border rounded-lg hover:bg-accent/50 transition-colors">
                  <Brain className="h-5 w-5 text-violet-500" />
                  <div className="flex-1">
                    <Label className="font-medium">Person Attributes</Label>
                    <p className="text-xs text-muted-foreground">Gender, age range, clothing colors</p>
                  </div>
                  <Switch
                    checked={settings.detect_person_attributes}
                    onChange={(e) => setSettings((s) => ({ ...s, detect_person_attributes: e.target.checked }))}
                  />
                </div>
                <div className="flex items-center gap-3 p-3 border rounded-lg hover:bg-accent/50 transition-colors">
                  <Shield className="h-5 w-5 text-amber-500" />
                  <div className="flex-1">
                    <Label className="font-medium">Behavior Analysis</Label>
                    <p className="text-xs text-muted-foreground">Loitering, running, carrying, entered/exited</p>
                  </div>
                  <Switch
                    checked={settings.detect_behavior}
                    onChange={(e) => setSettings((s) => ({ ...s, detect_behavior: e.target.checked }))}
                  />
                </div>
              </div>
            )}
          </div>

          <Separator />

          {/* Vehicles Section */}
          <div className="space-y-4">
            <div className="flex items-center gap-3 p-3 border rounded-lg bg-muted/30">
              <Car className="h-6 w-6 text-primary" />
              <div className="flex-1">
                <Label className="font-medium text-lg">Vehicle Detection</Label>
                <p className="text-xs text-muted-foreground">Cars, trucks, buses, motorcycles tracking</p>
              </div>
              <Switch
                checked={settings.detect_vehicles}
                onChange={(e) => setSettings((s) => ({ ...s, detect_vehicles: e.target.checked }))}
              />
            </div>
            {settings.detect_vehicles && (
              <div className="grid gap-3 md:grid-cols-3 pl-9 border-l-2 border-border/50">
                <div className="flex items-center gap-3 p-3 border rounded-lg hover:bg-accent/50 transition-colors">
                  <Eye className="h-5 w-5 text-emerald-500" />
                  <div className="flex-1">
                    <Label className="font-medium">License Plate Recognition</Label>
                    <p className="text-xs text-muted-foreground">Detect and OCR license plates (LPR)</p>
                  </div>
                  <Switch
                    checked={settings.detect_license_plates}
                    onChange={(e) => setSettings((s) => ({ ...s, detect_license_plates: e.target.checked }))}
                  />
                </div>
                <div className="flex items-center gap-3 p-3 border rounded-lg hover:bg-accent/50 transition-colors">
                  <Palette className="h-5 w-5 text-rose-500" />
                  <div className="flex-1">
                    <Label className="font-medium">Vehicle Color</Label>
                    <p className="text-xs text-muted-foreground">Classify primary vehicle color</p>
                  </div>
                  <Switch
                    checked={settings.detect_vehicle_color}
                    onChange={(e) => setSettings((s) => ({ ...s, detect_vehicle_color: e.target.checked }))}
                  />
                </div>
                <div className="flex items-center gap-3 p-3 border rounded-lg hover:bg-accent/50 transition-colors">
                  <Truck className="h-5 w-5 text-orange-500" />
                  <div className="flex-1">
                    <Label className="font-medium">Make/Model</Label>
                    <p className="text-xs text-muted-foreground">Identify vehicle make and model (requires additional model)</p>
                  </div>
                  <Switch
                    checked={settings.detect_vehicle_make_model}
                    onChange={(e) => setSettings((s) => ({ ...s, detect_vehicle_make_model: e.target.checked }))}
                  />
                </div>
              </div>
            )}
          </div>

          <Separator />

          {/* Animals Section */}
          <div className="space-y-4">
            <div className="flex items-center gap-3 p-3 border rounded-lg bg-muted/30">
              <PawPrint className="h-6 w-6 text-primary" />
              <div className="flex-1">
                <Label className="font-medium text-lg">Animal Detection</Label>
                <p className="text-xs text-muted-foreground">Dogs, cats, birds and other animals</p>
              </div>
              <Switch
                checked={settings.detect_animals}
                onChange={(e) => setSettings((s) => ({ ...s, detect_animals: e.target.checked }))}
              />
            </div>
            {settings.detect_animals && (
              <div className="grid gap-3 md:grid-cols-3 pl-9 border-l-2 border-border/50">
                <div className="flex items-center gap-3 p-3 border rounded-lg hover:bg-accent/50 transition-colors">
                  <Dog className="h-5 w-5 text-amber-600" />
                  <div className="flex-1">
                    <Label className="font-medium">Dogs</Label>
                    <p className="text-xs text-muted-foreground">Detect and track dogs</p>
                  </div>
                  <Switch
                    checked={settings.detect_dogs}
                    onChange={(e) => setSettings((s) => ({ ...s, detect_dogs: e.target.checked }))}
                  />
                </div>
                <div className="flex items-center gap-3 p-3 border rounded-lg hover:bg-accent/50 transition-colors">
                  <Cat className="h-5 w-5 text-purple-600" />
                  <div className="flex-1">
                    <Label className="font-medium">Cats</Label>
                    <p className="text-xs text-muted-foreground">Detect and track cats</p>
                  </div>
                  <Switch
                    checked={settings.detect_cats}
                    onChange={(e) => setSettings((s) => ({ ...s, detect_cats: e.target.checked }))}
                  />
                </div>
                <div className="flex items-center gap-3 p-3 border rounded-lg hover:bg-accent/50 transition-colors">
                  <Bird className="h-5 w-5 text-sky-600" />
                  <div className="flex-1">
                    <Label className="font-medium">Birds</Label>
                    <p className="text-xs text-muted-foreground">Detect and track birds</p>
                  </div>
                  <Switch
                    checked={settings.detect_birds}
                    onChange={(e) => setSettings((s) => ({ ...s, detect_birds: e.target.checked }))}
                  />
                </div>
              </div>
            )}
          </div>

<Button onClick={handleSaveDetection} disabled={saving === "detection"} className="w-full">
            {saving === "detection" ? "Saving..." : "Save Detection Preferences"}
          </Button>
        </CardContent>
      </Card>

      {/* language */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Globe className="h-4 w-4 text-primary" /> { "Language" }
          </CardTitle>
          <CardDescription>Select the display language for the interface.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="language">Interface Language</Label>
              <Select
                id="language"
                value={settings.language}
                onChange={(e) => setSettings((s) => ({ ...s, language: e.target.value }))}
                className="mt-1"
              >
                {LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.name}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <Button onClick={handleSaveLanguage} disabled={saving === "language"}>
            {saving === "language" ? "Saving..." : "Save Language"}
          </Button>
        </CardContent>
      </Card>

      {/* auto-scan scheduler */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Clock className="h-4 w-4 text-primary" /> { "Auto-Scan Scheduler" }
          </CardTitle>
          <CardDescription>
            Automatically scan the watch directory on a schedule. Uses cron expressions (minute hour day month weekday).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="scheduler-enabled">Enable Scheduler</Label>
              <div className="flex items-center gap-2 mt-1">
                <Switch
                  id="scheduler-enabled"
                  checked={settings.auto_scan_enabled}
                  onChange={(e) => setSettings((s) => ({ ...s, auto_scan_enabled: e.target.checked }))}
                />
                <span className="text-sm">
                  {settings.auto_scan_enabled ? "Enabled" : "Disabled"}
                </span>
              </div>
            </div>
            <div>
              <Label htmlFor="schedule">Schedule (Cron Expression)</Label>
              <Select
                id="schedule"
                value={settings.auto_scan_schedule}
                onChange={(e) => setSettings((s) => ({ ...s, auto_scan_schedule: e.target.value }))}
                disabled={!settings.auto_scan_enabled}
                className="mt-1"
              >
                {SCHEDULE_PRESETS.map((preset) => (
                  <option key={preset.value} value={preset.value}>
                    {preset.label}
                  </option>
                ))}
              </Select>
              <p className="text-xs text-muted-foreground mt-1">
                Format: minute hour day month weekday (e.g., "0 2 * * *" = daily at 2 AM)
              </p>
            </div>
          </div>

          <Button onClick={handleSaveScheduler} disabled={saving === "scheduler"}>
            {saving === "scheduler" ? "Saving..." : "Save Scheduler Settings"}
          </Button>

          {settings.auto_scan_enabled && settings.auto_scan_schedule && (
            <div className="p-3 rounded-md bg-emerald-50 text-emerald-800 border border-emerald-200 text-sm">
              <div className="flex items-center gap-2">
                <RotateCcw className="h-4 w-4" />
                <span>Scheduler active - next scan will run per cron schedule</span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* theme settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Bot className="h-4 w-4 text-primary" /> { "Appearance" }
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="grid gap-2 md:grid-cols-2">
            <div>
              <Label htmlFor="theme">Theme</Label>
              <div className="flex items-center gap-2 mt-1">
                <button
                  onClick={() => setTheme("light")}
                  className={`px-3 py-1.5 rounded text-sm transition-colors ${
                    theme === "light" ? "bg-primary text-primary-foreground" : "hover:text-primary"
                  }`}
                >
                  Light
                </button>
                <button
                  onClick={() => setTheme("dark")}
                  className={`px-3 py-1.5 rounded text-sm transition-colors ${
                    theme === "dark" ? "bg-primary text-primary-foreground" : "hover:text-primary"
                  }`}
                >
                  Dark
                </button>
                <button
                  onClick={() => setTheme("system")}
                  className={`px-3 py-1.5 rounded text-sm transition-colors ${
                    theme === "system" ? "bg-primary text-primary-foreground" : "hover:text-primary"
                  }`}
                >
                  System
                </button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}