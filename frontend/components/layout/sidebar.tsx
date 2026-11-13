"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Bug,
  GitPullRequest,
  LayoutDashboard,
  Moon,
  Settings,
  Hexagon,
  Sun,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

const workspace = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/repositories", label: "Repositories", icon: Hexagon },
  { href: "/pull-requests", label: "Pull Requests", icon: GitPullRequest },
  { href: "/analytics", label: "Usage & Cost", icon: Activity },
];

const system = [{ href: "/settings", label: "Settings", icon: Settings }];

function NavItem({
  href,
  label,
  icon: Icon,
  active,
}: {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "group relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] font-medium transition-colors duration-fast",
        active
          ? "bg-sidebar-active text-foreground"
          : "text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      {active ? (
        <span className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-primary" />
      ) : null}
      <Icon
        className={cn(
          "h-4 w-4 shrink-0 transition-colors",
          active ? "text-primary" : "text-muted-foreground group-hover:text-foreground",
        )}
        strokeWidth={1.75}
      />
      <span className="truncate">{label}</span>
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();

  return (
    <aside className="flex h-screen w-[248px] shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
      <div className="flex h-14 items-center gap-3 border-b border-sidebar-border px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-sm">
          <Bug className="h-4 w-4" strokeWidth={2.25} />
        </div>
        <div className="min-w-0 leading-tight">
          <div className="truncate text-sm font-semibold tracking-tight text-foreground">
            Spider
          </div>
          <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
            Code Review
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
        <div>
          <p className="eyebrow mb-2 px-2.5">Workspace</p>
          <div className="space-y-0.5">
            {workspace.map((item) => (
              <NavItem
                key={item.href}
                {...item}
                active={
                  item.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.href)
                }
              />
            ))}
          </div>
        </div>

        <div>
          <p className="eyebrow mb-2 px-2.5">System</p>
          <div className="space-y-0.5">
            {system.map((item) => (
              <NavItem
                key={item.href}
                {...item}
                active={pathname.startsWith(item.href)}
              />
            ))}
          </div>
        </div>
      </nav>

      <div className="space-y-3 border-t border-sidebar-border p-3">
        <Button
          variant="outline"
          size="sm"
          className="w-full justify-start gap-2"
          onClick={toggleTheme}
          aria-label="Toggle color theme"
        >
          {theme === "dark" ? (
            <Sun className="h-3.5 w-3.5" strokeWidth={1.75} />
          ) : (
            <Moon className="h-3.5 w-3.5" strokeWidth={1.75} />
          )}
          {theme === "dark" ? "Light mode" : "Dark mode"}
        </Button>
        <p className="px-1 text-[11px] leading-relaxed text-muted-foreground">
          Optimize for real bugs — not more comments.
        </p>
      </div>
    </aside>
  );
}
