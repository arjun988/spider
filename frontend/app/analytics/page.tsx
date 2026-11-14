"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Shell } from "@/components/layout/shell";
import { StatCard } from "@/components/metrics/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatUsd } from "@/lib/utils";

const tooltipStyle = {
  background: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 10,
  color: "hsl(var(--foreground))",
  boxShadow: "var(--panel-shadow)",
  fontSize: 12,
};

export default function AnalyticsPage() {
  const overview = useQuery({ queryKey: ["overview"], queryFn: api.overview });
  const usage = useQuery({ queryKey: ["usage"], queryFn: () => api.usage(30) });
  const scorecard = useQuery({ queryKey: ["scorecard"], queryFn: () => api.scorecard(30) });
  const evalData = useQuery({ queryKey: ["eval"], queryFn: () => api.evalHarness(90) });
  const m = overview.data?.metrics;

  return (
    <Shell
      title="Usage & Cost"
      description="Spend, review quality scorecard, and precision/recall eval over labeled feedback."
      breadcrumb="Workspace"
      actions={
        <>
          <a href={api.exportUsageUrl(30)}>
            <button className="inline-flex h-8 items-center rounded-lg border border-border bg-card px-3 text-xs font-medium hover:bg-muted">
              Export usage CSV
            </button>
          </a>
          <a href={api.exportFindingsUrl(30)}>
            <button className="inline-flex h-8 items-center rounded-lg border border-border bg-card px-3 text-xs font-medium hover:bg-muted">
              Export findings CSV
            </button>
          </a>
        </>
      }
    >
      <section className="space-y-3">
        <div>
          <p className="eyebrow">Spend</p>
          <h2 className="section-title">Cost snapshot</h2>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Total spend"
            value={overview.isLoading ? "…" : formatUsd(m?.total_api_spend_usd ?? 0)}
            tone="accent"
          />
          <StatCard
            label="PRs reviewed"
            value={overview.isLoading ? "…" : (m?.total_prs_reviewed ?? 0)}
          />
          <StatCard
            label="Findings"
            value={overview.isLoading ? "…" : (m?.total_findings ?? 0)}
          />
          <StatCard
            label="Cost / PR"
            value={
              overview.isLoading
                ? "…"
                : formatUsd(
                    m && m.total_prs_reviewed > 0
                      ? m.total_api_spend_usd / m.total_prs_reviewed
                      : 0,
                  )
            }
          />
        </div>
      </section>

      <section className="space-y-3">
        <div>
          <p className="eyebrow">Quality</p>
          <h2 className="section-title">Review scorecard</h2>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Precision"
            value={
              scorecard.data?.org.precision != null
                ? `${(scorecard.data.org.precision * 100).toFixed(1)}%`
                : "—"
            }
            tone="accent"
          />
          <StatCard
            label="FP rate"
            value={
              scorecard.data?.org.fp_rate != null
                ? `${(scorecard.data.org.fp_rate * 100).toFixed(1)}%`
                : "—"
            }
            tone="warning"
          />
          <StatCard
            label="Labeled findings"
            value={scorecard.data?.org.labeled_findings ?? "—"}
          />
          <StatCard
            label="Avg time to comment"
            value={
              scorecard.data?.org.avg_time_to_first_comment_ms != null
                ? `${Math.round(scorecard.data.org.avg_time_to_first_comment_ms / 1000)}s`
                : "—"
            }
          />
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Per repository</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Repository</th>
                  <th>Precision</th>
                  <th>FP rate</th>
                  <th>Time to comment</th>
                  <th>Labeled</th>
                </tr>
              </thead>
              <tbody>
                {(scorecard.data?.by_repository ?? []).length === 0 ? (
                  <tr>
                    <td colSpan={5} className="!text-muted-foreground">
                      Label findings as helpful / false positive to populate the scorecard.
                    </td>
                  </tr>
                ) : (
                  scorecard.data!.by_repository.map((row) => (
                    <tr key={row.repository_id}>
                      <td className="text-[13px]">{row.repository}</td>
                      <td className="tabular-nums">
                        {row.precision != null ? `${(row.precision * 100).toFixed(0)}%` : "—"}
                      </td>
                      <td className="tabular-nums">
                        {row.fp_rate != null ? `${(row.fp_rate * 100).toFixed(0)}%` : "—"}
                      </td>
                      <td className="tabular-nums">
                        {row.time_to_first_comment_ms != null
                          ? `${Math.round(row.time_to_first_comment_ms / 1000)}s`
                          : "—"}
                      </td>
                      <td className="tabular-nums">{row.labeled}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Eval harness (weekly)</CardTitle>
          </CardHeader>
          <CardContent className="h-64 pt-2">
            {(evalData.data?.series?.length ?? 0) === 0 ? (
              <p className="text-sm text-muted-foreground">
                {evalData.data?.note || "No labeled feedback yet — close the precision loop by rating findings."}
              </p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={evalData.data!.series}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--chart-grid))" />
                  <XAxis dataKey="week" tick={{ fill: "hsl(var(--chart-tick))", fontSize: 11 }} />
                  <YAxis domain={[0, 1]} tick={{ fill: "hsl(var(--chart-tick))", fontSize: 11 }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend />
                  <Line type="monotone" dataKey="precision" stroke="hsl(var(--chart-1))" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="recall_proxy" stroke="hsl(var(--chart-2))" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Daily API spend (30d)</CardTitle>
          </CardHeader>
          <CardContent className="h-64 pt-2">
            {usage.error ? (
              <p className="text-sm text-destructive">Failed to load usage data.</p>
            ) : (usage.data?.timeseries?.length ?? 0) === 0 ? (
              <p className="text-sm text-muted-foreground">No usage recorded yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={usage.data.timeseries}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--chart-grid))" />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "hsl(var(--chart-tick))", fontSize: 11 }}
                  />
                  <YAxis tick={{ fill: "hsl(var(--chart-tick))", fontSize: 11 }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Line
                    type="monotone"
                    dataKey="cost_usd"
                    stroke="hsl(var(--chart-1))"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Review volume</CardTitle>
          </CardHeader>
          <CardContent className="h-64 pt-2">
            {(usage.data?.reviews?.length ?? 0) === 0 ? (
              <p className="text-sm text-muted-foreground">No reviews yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={usage.data.reviews}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--chart-grid))" />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "hsl(var(--chart-tick))", fontSize: 11 }}
                  />
                  <YAxis tick={{ fill: "hsl(var(--chart-tick))", fontSize: 11 }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend />
                  <Bar dataKey="reviews" fill="hsl(var(--chart-2))" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="findings" fill="hsl(var(--chart-3))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Model breakdown</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Requests</th>
                  <th>Input tokens</th>
                  <th>Output tokens</th>
                  <th>Cost</th>
                </tr>
              </thead>
              <tbody>
                {(usage.data?.models ?? []).length === 0 ? (
                  <tr>
                    <td colSpan={5} className="!text-muted-foreground">
                      No model usage yet.
                    </td>
                  </tr>
                ) : (
                  usage.data!.models.map((row: any) => (
                    <tr key={row.model}>
                      <td className="font-mono text-xs">{row.model}</td>
                      <td className="tabular-nums">{row.requests}</td>
                      <td className="tabular-nums">{row.input_tokens}</td>
                      <td className="tabular-nums">{row.output_tokens}</td>
                      <td className="font-mono text-xs tabular-nums">
                        {formatUsd(row.cost_usd)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Cost by repository</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Repository</th>
                  <th>Reviews</th>
                  <th>Cost</th>
                </tr>
              </thead>
              <tbody>
                {(usage.data?.by_repository ?? []).length === 0 ? (
                  <tr>
                    <td colSpan={3} className="!text-muted-foreground">
                      No repository cost data yet.
                    </td>
                  </tr>
                ) : (
                  usage.data!.by_repository.map((row) => (
                    <tr key={row.repository}>
                      <td className="text-[13px]">{row.repository}</td>
                      <td className="tabular-nums">{row.reviews}</td>
                      <td className="font-mono text-xs tabular-nums">
                        {formatUsd(row.cost_usd)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </section>
    </Shell>
  );
}
