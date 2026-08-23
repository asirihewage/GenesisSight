import { Compass, ListChecks, ShieldCheck, Video } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const CAPABILITIES = [
  ["👤", "People and their movements"],
  ["🚶", "Activity and movement patterns"],
  ["🎥", "Important events and moments"],
  ["🔎", "Specific activity within long recordings"],
  ["🕒", "When events occurred"],
  ["🔗", "Related activity across multiple video segments"],
] as const;

export function About() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">About genesisSight</h1>
        <p className="text-sm text-muted-foreground">
          Turning CCTV footage into useful insights.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Video className="h-4 w-4 text-primary" /> Turning CCTV Footage Into Useful Insights
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
          <p>
            We built <span className="font-semibold text-foreground">genesisSight</span> to make CCTV footage
            easier to understand, search, and analyze.
          </p>
          <p>
            Traditional CCTV systems are good at recording everything — but when something happens, finding the
            important moments can mean hours of manually reviewing video. Our goal is to change that.
          </p>
          <p>
            Our AI-powered video analysis platform automatically processes CCTV footage, identifies meaningful
            events, tracks activity across video, and helps users quickly understand what happened without
            watching hours of recordings.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <ListChecks className="h-4 w-4 text-primary" /> What We Do
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
          <p>Our platform transforms raw CCTV recordings into structured, searchable information.</p>
          <p>It can help identify:</p>
          <ul className="grid gap-2 sm:grid-cols-2">
            {CAPABILITIES.map(([emoji, label]) => (
              <li key={label} className="flex items-center gap-2 rounded-md border border-border bg-muted/40 px-3 py-2 text-foreground/90">
                <span className="text-base">{emoji}</span>
                <span>{label}</span>
              </li>
            ))}
          </ul>
          <p className="rounded-md border border-primary/30 bg-primary/5 px-4 py-3 font-medium text-foreground">
            Instead of asking "Where is the footage?", you can ask <span className="text-primary">"What happened?"</span>
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <ShieldCheck className="h-4 w-4 text-primary" /> Built With Privacy in Mind
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
          <p>We believe video data should remain under your control.</p>
          <p>
            Our platform is designed with privacy and local processing in mind, allowing organizations and
            individuals to analyze their footage without unnecessarily sending sensitive video to third-party
            services.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Compass className="h-4 w-4 text-primary" /> Our Vision
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
          <p>We believe CCTV should be more than a storage system.</p>
          <p>
            The next generation of surveillance systems should be able to understand video, highlight important
            events, and help people make sense of what happened.
          </p>
          <p>
            Our vision is to build an intelligent video analysis platform that turns hours of passive recordings
            into actionable information — while keeping the technology accessible, efficient, and
            privacy-conscious.
          </p>
          <p className="pt-2 font-semibold text-foreground">
            Record less time searching. Spend more time understanding.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <ShieldCheck className="h-4 w-4 text-primary" /> Developer
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
          <p>
            <span className="font-semibold text-foreground">Asiri Hewage</span><br/>
            <span className="text-muted-foreground">Software Engineer from Sri Lanka</span>
          </p>
          <p className="text-sm">
            <a href="https://www.linkedin.com/in/asirihewage" target="_blank" rel="noopener noreferrer" className="text-primary hover:text-primary/90 underline">
              LinkedIn
            </a>
            ·
            <a href="https://github.com/asirihewage" target="_blank" rel="noopener noreferrer" className="text-primary hover:text-primary/90 underline">
              GitHub
            </a>
          </p>
          <p>
            Creator and lead developer of genesisSight — a local AI CCTV analysis platform built with
            YOLO11x, ByteTrack, Re-ID, and Qwen2.5-VL models, running entirely offline.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}