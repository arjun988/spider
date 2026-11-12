"use client";

import { useQuery } from "@tanstack/react-query";
import { Shell } from "@/components/layout/shell";
import { StatCard } from "@/components/metrics/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatUsd } from "@/lib/utils";

export default function AnalyticsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["overview"],
    queryFn: api.overview,
  });

  const m = data?.metrics;

  return (
    <Shell
      title="Usage & Cost"
      description="Gemini API expenditure derived from recorded usage events"
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total spend"
          value={isLoading ? "…" : formatUsd(m?.total_api_spend_usd ?? 0)}
          tone="accent"
        />
        <StatCard
          label="PRs reviewed"
          value={isLoading ? "…" : (m?.total_prs_reviewed ?? 0)}
        />
        <StatCard
          label="Findings published"
          value={isLoading ? "…" : (m?.total_findings ?? 0)}
        />
        <StatCard
          label="Cost / PR"
          value={
            isLoading
              ? "…"
              : formatUsd(
                  m && m.total_prs_reviewed > 0
                    ? m.total_api_spend_usd / m.total_prs_reviewed
                    : 0,
                )
          }
        />
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Charts</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Daily and monthly spend charts will populate once review jobs record token usage
            (Phase 6). All metrics already read from live database tables — no fabricated data.
          </p>
        </CardContent>
      </Card>
    </Shell>
  );
}