import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle, CheckCircle2, Cpu, Download, Loader2, Plug, Rocket, Sparkles, Video,
} from "lucide-react";
import { api } from "@/lib/api";
import type { SetupStatus } from "@/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

const STEPS = ["System check", "Detection model", "AI analysis", "Finish"];

function pct(done: number, total: number) {
  return total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;
}

export function SetupWizard({ onComplete }: { onComplete: () => void }) {
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [connected, setConnected] = useState(true);
  const [ollamaSkipped, setOllamaSkipped] = useState(false);
  const [step, setStep] = useState(0);
  const [finishing, setFinishing] = useState(false);
  const lastStepRef = useRef(0);

  const yoloReady = status?.yolo.ready ?? false;
  const vlmReady = status?.ollama.vlm_ready ?? false;

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const s = await api.setupStatus();
        if (!alive) return;
        if (s.complete) {
          onComplete();
          return;
        }
        setStatus(s);
        setConnected(true);
        if (step === 1 && s.yolo.ready) setStep(2);
        if (step === 2 && s.ollama.vlm_ready) setStep(3);
      } catch {
        if (alive) setConnected(false);
      }
    };
    tick();
    const id = setInterval(tick, 2000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [step]);

  useEffect(() => {
    lastStepRef.current = step;
  }, [step]);

  const yoloRunning = status?.yolo.download.state === "downloading";
  const yoloFailed = status?.yolo.download.state === "failed";
  const pullRunning = status?.ollama.pull.state === "running";
  const pullFailed = status?.ollama.pull.state === "failed";
  const installRunning = status?.ollama.install.state === "downloading";

  const canAdvance0 = step === 0;
  const canFinish =
    yoloReady && vlmReady;

  const finish = async () => {
    setFinishing(true);
    try {
      await api.setupComplete(ollamaSkipped);
      onComplete();
    } finally {
      setFinishing(false);
    }
  };

  if (!connected) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[#0a0f1e] text-slate-200">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <p className="text-sm text-slate-400">Waiting for the analysis service to start…</p>
      </div>
    );
  }

  const statusItem = (ok: boolean, label: string) => (
    <span className={cn("flex items-center gap-2 text-sm", ok ? "text-emerald-400" : "text-slate-400")}>
      {ok ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4 text-amber-400" />}
      {label}
    </span>
  );

  return (
    <div className="flex min-h-screen flex-col bg-[#0a0f1e] text-slate-200">
      <header className="flex items-center gap-3 border-b border-slate-800 px-8 py-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Video className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-lg font-semibold leading-tight">CCTV Analyzer setup</h1>
          <p className="text-xs text-slate-400">One-time first-run configuration — everything stays on this PC.</p>
        </div>
      </header>

      <div className="mx-auto w-full max-w-2xl flex-1 space-y-6 px-8 py-8">
        {/* stepper */}
        <ol className="flex items-center gap-2 text-xs">
          {STEPS.map((label, i) => (
            <li key={label} className="flex flex-1 items-center gap-2">
              <span
                className={cn(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold",
                  i < step ? "bg-emerald-500/20 text-emerald-400" : i === step ? "bg-primary text-primary-foreground" : "bg-slate-800 text-slate-500",
                )}
              >
                {i < step ? "✓" : i + 1}
              </span>
              <span className={cn("font-medium", i === step ? "text-slate-100" : "text-slate-500")}>{label}</span>
              {i < STEPS.length - 1 && <span className="h-px flex-1 bg-slate-800" />}
            </li>
          ))}
        </ol>

        {step === 0 && (
          <Card className="border-slate-800 bg-slate-900/60">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Cpu className="h-4 w-4 text-primary" /> System check
              </CardTitle>
              <CardDescription>
                Your PC runs the whole pipeline — detection, tracking, description and search.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {statusItem(status?.system.backend_ok ?? false, `Analysis service connected`)}
              {statusItem(status?.system.storage_writable ?? false, "Storage area is writable (your videos, frames and database)")}
              {statusItem(!!status?.system.cuda, "NVIDIA GPU with CUDA available — fast processing")}
              {!status?.system.cuda && (
                <p className="text-xs text-slate-500">
                  No CUDA GPU detected; analysis will run on CPU (slower, still works).
                </p>
              )}
            </CardContent>
          </Card>
        )}

        {step === 1 && (
          <Card className="border-slate-800 bg-slate-900/60">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Download className="h-4 w-4 text-primary" /> Detection model
              </CardTitle>
              <CardDescription>
                YOLO11x — the neural network that finds people in every frame.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {yoloReady ? (
                <div className="flex items-center gap-2 text-sm text-emerald-400">
                  <CheckCircle2 className="h-4 w-4" /> Model ready at {status?.yolo.path}
                </div>
              ) : (
                <>
                  <p className="text-sm text-slate-300">
                    The weights file (<span className="font-mono text-xs">yolo11x.pt</span>, ≈112 MB) has
                    not been downloaded yet. One-time download from the official Ultralytics release.
                  </p>
                  <Button
                    onClick={() => api.setupDownloadYolo()}
                    disabled={yoloRunning}
                    className="w-full"
                  >
                    {yoloRunning ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Downloading… {pct(status!.yolo.download.done, status!.yolo.download.total)}%
                      </>
                    ) : (
                      <>
                        <Download className="mr-2 h-4 w-4" /> Download YOLO weights
                      </>
                    )}
                  </Button>
                  {yoloRunning && (
                    <Progress
                      value={pct(status!.yolo.download.done, status!.yolo.download.total)}
                      className="h-2"
                    />
                  )}
                  {yoloFailed && (
                    <p className="text-xs text-destructive">
                      Download failed: {status?.yolo.download.error}. Check your internet connection and retry.
                    </p>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        )}

        {step === 2 && (
          <Card className="border-slate-800 bg-slate-900/60">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Sparkles className="h-4 w-4 text-primary" /> AI analysis (Ollama + Qwen2.5-VL)
              </CardTitle>
              <CardDescription>
                Adds written descriptions of what happened in each event and semantic search.
                Optional — the app fully works without it.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {vlmReady ? (
                <div className="flex items-center gap-2 text-sm text-emerald-400">
                  <CheckCircle2 className="h-4 w-4" />
                  {status?.ollama.vlm_model} installed and running
                </div>
              ) : (
                <>
                  {!status?.ollama.installed && (
                    <>
                      <p className="text-sm text-slate-300">
                        Ollama is not installed — it runs the vision model completely offline.
                      </p>
                      <Button onClick={() => api.setupInstallOllama()} disabled={installRunning} className="w-full">
                        {installRunning ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Downloading Ollama installer…
                          </>
                        ) : (
                          <>
                            <Download className="mr-2 h-4 w-4" /> Download & run the Ollama installer
                          </>
                        )}
                      </Button>
                      <p className="text-xs text-slate-500">
                        The installer opens in a separate window. Complete it, then come back here and click
                        “Check again”.
                      </p>
                    </>
                  )}
                  {status?.ollama.installed && !status.ollama.reachable && (
                    <>
                      <p className="text-sm text-slate-300">
                        Ollama is installed but the service isn’t running. Start the Ollama app from your
                        Start menu, then continue.
                      </p>
                      <Button variant="outline" onClick={() => setStep(2)} className="w-full" disabled>
                        <Plug className="mr-2 h-4 w-4" /> Waiting for Ollama…
                      </Button>
                    </>
                  )}
                  {status?.ollama.installed && status.ollama.reachable && !vlmReady && (
                    <>
                      <p className="text-sm text-slate-300">
                        Ollama is running but {status.ollama.vlm_model} isn’t pulled yet (one-time, ≈6 GB).
                      </p>
                      <Button onClick={() => api.setupPullOllama()} disabled={pullRunning} className="w-full">
                        {pullRunning ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Pulling {status.ollama.vlm_model}… hold on, this takes a while
                          </>
                        ) : (
                          <>
                            <Download className="mr-2 h-4 w-4" /> Pull {status.ollama.vlm_model}
                          </>
                        )}
                      </Button>
                      <Button variant="outline" onClick={() => setStep(3)} className="w-full"
                        title="You can pull it later from Ollama itself">
                        Skip for now
                      </Button>
                      {pullRunning && (
                        <div className="rounded-md border border-slate-800 bg-slate-950 p-2 text-[11px] text-slate-400">
                          <pre className="max-h-32 overflow-y-auto whitespace-pre-wrap">
                            {status.ollama.pull.log || "starting…"}
                          </pre>
                        </div>
                      )}
                    </>
                  )}
                  {pullFailed && (
                    <p className="text-xs text-destructive">
                      Pull failed: {status?.ollama.pull.error}. Retry, or skip and enable AI analysis later.
                    </p>
                  )}
                  <button
                    onClick={() => {
                      setOllamaSkipped(true);
                      setStep(3);
                    }}
                    className="mx-auto block text-xs text-slate-500 underline-offset-2 hover:text-slate-300 hover:underline"
                  >
                    Skip AI analysis — rule-based descriptions only
                  </button>
                </>
              )}
            </CardContent>
          </Card>
        )}

        {step === 3 && (
          <Card className="border-slate-800 bg-slate-900/60">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Rocket className="h-4 w-4 text-primary" /> You’re all set
              </CardTitle>
              <CardDescription>Everything is in place — launch the app.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2 rounded-md border border-slate-800 bg-slate-950/60 p-3 text-sm">
                {statusItem(yoloReady, "YOLO11x detection model")}
                {statusItem(vlmReady, `AI descriptions (${status?.ollama.vlm_model})`)}
                {!vlmReady && !ollamaSkipped && (
                  <button
                    onClick={() => setStep(2)}
                    className="text-xs text-primary hover:underline"
                  >
                    Set up AI analysis now →
                  </button>
                )}
                {ollamaSkipped && (
                  <p className="text-xs text-amber-400">
                    Ollama skipped — event descriptions fall back to rules; enable AI later in Settings.
                  </p>
                )}
              </div>
              <Button onClick={finish} disabled={finishing || !canFinish} className="w-full" size="lg">
                {finishing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Rocket className="mr-2 h-4 w-4" />}
                Launch CCTV Analyzer
              </Button>
              {!canFinish && (
                <p className="text-center text-xs text-slate-500">
                  Finish the detection model step first.
                </p>
              )}
            </CardContent>
          </Card>
        )}

        <div className="flex justify-between">
          <Button variant="ghost" size="sm" disabled={step === 0} onClick={() => setStep(step - 1)}>
            Back
          </Button>
          {canAdvance0 && (
            <Button size="sm" onClick={() => setStep(1)}>
              Continue
            </Button>
          )}
          {step === 1 && yoloReady && (
            <Button size="sm" onClick={() => setStep(2)}>
              Continue
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}