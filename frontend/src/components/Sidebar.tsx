import { NavLink } from "react-router-dom";
import { Activity, Car, Info, LayoutDashboard, Search, Settings, UploadCloud, Users, Video } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSocket } from "@/hooks/useSocket";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/upload", label: "Upload", icon: UploadCloud },
  { to: "/people", label: "People", icon: Users },
  { to: "/vehicles", label: "Vehicles", icon: Car },
  { to: "/search", label: "Search", icon: Search },
  { to: "/system-status", label: "System Status", icon: Activity },
  { to: "/settings", label: "Settings", icon: Settings },
  { to: "/about", label: "About", icon: Info },
];

export function Sidebar() {
  const { connected } = useSocket();
  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col border-r border-border bg-card">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/15 text-primary">
          <Video className="h-5 w-5" />
        </div>
        <div>
          <div className="text-sm font-semibold leading-tight">CCTV Analyzer</div>
          <div className="text-[11px] text-muted-foreground">Local AI · RTX 5080</div>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-2">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/15 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-border px-5 py-4">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span
            className={cn(
              "inline-block h-2 w-2 rounded-full",
              connected ? "bg-emerald-500" : "bg-rose-500",
            )}
          />
          {connected ? "Live updates connected" : "Reconnecting…"}
        </div>
      </div>
    </aside>
  );
}
