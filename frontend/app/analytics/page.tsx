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

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchUsage() {
  const res = await fetch(`${API_URL}/api/analytics/usage?days=30`, { cache: "no-store" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export default function AnalyticsPage() {
  const overview = useQuery({ queryKey: ["overview"], queryFn: api.overview });
  const usage = useQuery({ queryKey: ["usage"], queryFn: fetchUsage });
  const m = overview.data?.metrics;

  return (
    <Shell
      title="Usage & Cost"
      description="Gemini API expenditure derived from recorded usage events"
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total spend"
          value={overview.isLoading ? "…" : formatUsd(m?.total_api_spend_usd ?? 0)}
          tone="accent"
        />
        <StatCard label="PRs reviewed" value={overview.isLoading ? "…" : (m?.total_prs_reviewed ?? 0)} />
        <StatCard label="Findings" value={overview.isLoading ? "…" : (m?.total_findings ?? 0)} />
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

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Daily API spend (30d)</CardTitle>
          </CardHeader>
          <CardContent className="h-64">
            {(usage.data?.timeseries?.length ?? 0) === 0 ? (
              <p className="text-sm text-muted-foreground">No usage recorded yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={usage.data.timeseries}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2a3d" />
                  <XAxis dataKey="date" tick={{ fill: "#8b9bb4", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#8b9bb4", fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ background: "#0f172a", border: "1px solid #1f2a3d" }}
                  />
                  <Line type="monotone" dataKey="cost_usd" stroke="#2dd4bf" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Review volume</CardTitle>
          </CardHeader>
          <CardContent className="h-64">
            {(usage.data?.reviews?.length ?? 0) === 0 ? (
              <p className="text-sm text-muted-foreground">No reviews yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={usage.data.reviews}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2a3d" />
                  <XAxis dataKey="date" tick={{ fill: "#8b9bb4", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#8b9bb4", fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ background: "#0f172a", border: "1px solid #1f2a3d" }}
                  />
                  <Legend />
                  <Bar dataKey="reviews" fill="#38bdf8" />
                  <Bar dataKey="findings" fill="#f59e0b" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
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
                usage.data.models.map((row: any) => (
                  <tr key={row.model}>
                    <td className="font-mono text-xs">{row.model}</td>
                    <td>{row.requests}</td>
                    <td>{row.input_tokens}</td>
                    <td>{row.output_tokens}</td>
                    <td>{formatUsd(row.cost_usd)}</td>
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