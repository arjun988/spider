"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  AlertTriangle,
  Clock,
  DollarSign,
  GitPullRequest,
  Hexagon,
  ShieldAlert,
} from "lucide-react";
import { Shell } from "@/components/layout/shell";
import { StatCard } from "@/components/metrics/stat-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatDuration, formatUsd } from "@/lib/utils";

export default function OverviewPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["overview"],
    queryFn: api.overview,
    refetchInterval: 30_000,
  });

  const m = data?.metrics;

  return (
    <Shell
      title="Overview"
      description="Live metrics from review jobs, findings, and API usage"
      breadcrumb="Workspace / Dashboard"
    >
      {error ? (
        <Card className="border-destructive/40">
          <CardContent className="p-4 text-sm text-destructive">
            Unable to reach the API. Ensure the backend is running on{" "}
            {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}.
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <StatCard
          label="Repositories"
          value={isLoading ? "…" : (m?.total_repositories ?? 0)}
          icon={Hexagon}
        />
        <StatCard
          label="PRs reviewed"
          value={isLoading ? "…" : (m?.total_prs_reviewed ?? 0)}
          icon={GitPullRequest}
        />
        <StatCard
          label="Findings"
          value={isLoading ? "…" : (m?.total_findings ?? 0)}
          icon={AlertTriangle}
        />
        <StatCard
          label="Critical"
          value={isLoading ? "…" : (m?.critical_findings ?? 0)}
          tone="danger"
          icon={ShieldAlert}
        />
        <StatCard
          label="High"
          value={isLoading ? "…" : (m?.high_findings ?? 0)}
          tone="danger"
          icon={AlertTriangle}
        />
        <StatCard
          label="Avg review time"
          value={isLoading ? "…" : formatDuration(m?.average_review_time_ms)}
          icon={Clock}
        />
        <StatCard
          label="API spend"
          value={isLoading ? "…" : formatUsd(m?.total_api_spend_usd ?? 0)}
          icon={DollarSign}
          tone="accent"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent reviews</CardTitle>
          <p className="text-xs text-muted-foreground">Latest completed and in-flight review jobs</p>
        </CardHeader>
        <CardContent className="p-0">
          <table className="data-table">
            <thead>
              <tr>
                <th>PR</th>
                <th>Status</th>
                <th>Findings</th>
                <th>Duration</th>
                <th>Cost</th>
                <th>When</th>
              </tr>
            </thead>
            <tbody>
              {(m?.recent_reviews ?? []).length === 0 ? (
                <tr>
                  <td colSpan={6} className="!text-muted-foreground">
                    {isLoading
                      ? "Loading…"
                      : "No reviews yet. Install the GitHub App, sync a repo, then open a PR."}
                  </td>
                </tr>
              ) : (
                m?.recent_reviews.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <Link href={`/reviews/${r.id}`} className="font-medium text-primary hover:underline">
                        {r.pr_number != null ? `#${r.pr_number}` : "review"}
                      </Link>
                      <div className="max-w-xs truncate text-xs text-muted-foreground">
                        {r.pr_title || "Untitled"}
                      </div>
                    </td>
                    <td>
                      <Badge
                        variant={
                          r.status === "completed"
                            ? "success"
                            : r.status === "failed"
                              ? "destructive"
                              : "muted"
                        }
                      >
                        {r.status}
                      </Badge>
                    </td>
                    <td>{r.findings_count}</td>
                    <td className="font-mono text-xs">{formatDuration(r.duration_ms)}</td>
                    <td className="font-mono text-xs">{formatUsd(r.cost_usd)}</td>
                    <td className="text-xs text-muted-foreground">
                      {r.created_at
                        ? new Date(r.created_at).toLocaleString()
                        : "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </Shell>
  );
}