"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Bug,
  GitPullRequest,
  LayoutDashboard,
  Settings,
  Hexagon,
} from "lucide-react";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/repositories", label: "Repositories", icon: Hexagon },
  { href: "/pull-requests", label: "Pull Requests", icon: GitPullRequest },
  { href: "/analytics", label: "Usage & Cost", icon: Activity },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col border-r border-border bg-[#0b1220]">
      <div className="flex h-14 items-center gap-2.5 border-b border-border px-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-accent/20 text-accent">
          <Bug className="h-4 w-4" />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold tracking-tight text-foreground">Spider</div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Code Review
          </div>
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-0.5 p-2">
        {nav.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors",
                active
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-border p-3">
        <p className="text-[11px] text-muted-foreground">
          Optimize for real bugs, not more comments.
        </p>
      </div>
    </aside>
  );
}