"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Bug,
  ClipboardList,
  GitPullRequest,
  LayoutDashboard,
  Moon,
  Rocket,
  Settings,
  Hexagon,
  Sun,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/lib/theme";
import { api } from "@/lib/api";
import { setAccessToken, setOrgId } from "@/lib/auth";
import { cn } from "@/lib/utils";

const workspace = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/repositories", label: "Repositories", icon: Hexagon },
  { href: "/pull-requests", label: "Pull Requests", icon: GitPullRequest },
  { href: "/analytics", label: "Usage & Cost", icon: Activity },
];

const system = [
  { href: "/onboarding", label: "Onboarding", icon: Rocket },
  { href: "/audit", label: "Audit", icon: ClipboardList },
  { href: "/settings", label: "Settings", icon: Settings },
];

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
        "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium tracking-tight transition-all duration-fast",
        active
          ? "bg-sidebar-active text-foreground shadow-sm"
          : "text-muted-foreground hover:bg-muted/80 hover:text-foreground",
      )}
    >
      {active ? (
        <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full bg-primary" />
      ) : null}
      <span
        className={cn(
          "flex h-8 w-8 items-center justify-center rounded-lg border transition-colors",
          active
            ? "border-primary/25 bg-primary/10 text-primary"
            : "border-transparent bg-transparent text-muted-foreground group-hover:border-border group-hover:bg-card group-hover:text-foreground",
        )}
      >
        <Icon className="h-4 w-4" strokeWidth={1.6} />
      </span>
      <span className="truncate">{label}</span>
    </Link>
  );
}

export function Sidebar({ onNavigate }: { onNavigate?: () => void } = {}) {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, toggleTheme } = useTheme();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: api.me,
    retry: false,
  });

  async function onSwitchOrg(orgId: string) {
    try {
      const res = await api.switchOrg(orgId);
      setAccessToken(res.access_token);
      setOrgId(res.organization_id);
      router.refresh();
      window.location.reload();
    } catch {
      setOrgId(orgId);
      window.location.reload();
    }
  }

  return (
    <aside className="flex h-screen w-[268px] shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
      <div className="flex h-16 items-center gap-3 border-b border-sidebar-border px-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
          <Bug className="h-4 w-4" strokeWidth={2.2} />
        </div>
        <div className="min-w-0 leading-tight">
          <div className="truncate text-[15px] font-semibold tracking-tight text-foreground">
            Spider
          </div>
          <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
            Code Review
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-5" onClick={onNavigate}>
        <div>
          <p className="eyebrow mb-2.5 px-3">Workspace</p>
          <div className="space-y-1">
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
          <p className="eyebrow mb-2.5 px-3">System</p>
          <div className="space-y-1">
            {system.map((item) => (
              <NavItem
                key={item.href}
                {...item}
                active={pathname.startsWith(item.href)}
              />
            ))}
            <NavItem
              href="/webhooks"
              label="Webhooks"
              icon={Activity}
              active={pathname.startsWith("/webhooks")}
            />
          </div>
        </div>
      </nav>

      <div className="space-y-3 border-t border-sidebar-border p-4">
        {me.data?.organizations && me.data.organizations.length > 1 ? (
          <select
            className="w-full rounded-lg border border-input bg-background px-2 py-2 text-[12px]"
            value={me.data.organization_id || me.data.organizations[0]?.id || ""}
            onChange={(e) => onSwitchOrg(e.target.value)}
          >
            {me.data.organizations.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name || o.github_org_login || o.slug || o.id}
              </option>
            ))}
          </select>
        ) : null}
        {me.data ? (
          <p className="truncate px-1 text-[11px] text-muted-foreground">
            @{me.data.github_login}
            {me.data.role ? ` · ${me.data.role}` : ""}
          </p>
        ) : (
          <Link href="/login">
            <Button variant="outline" size="sm" className="w-full rounded-xl">
              Sign in
            </Button>
          </Link>
        )}
        <Button
          variant="outline"
          size="sm"
          className="w-full justify-start gap-2.5 rounded-xl"
          onClick={toggleTheme}
          aria-label="Toggle color theme"
        >
          {theme === "dark" ? (
            <Sun className="h-3.5 w-3.5" strokeWidth={1.6} />
          ) : (
            <Moon className="h-3.5 w-3.5" strokeWidth={1.6} />
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
