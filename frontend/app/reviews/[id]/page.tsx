"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Shell } from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDuration, formatUsd, shortSha } from "@/lib/utils";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchReview(id: string) {
  const res = await fetch(`${API_URL}/api/reviews/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function sevVariant(sev: string) {
  if (sev === "critical" || sev === "high") return "destructive" as const;
  if (sev === "medium") return "warning" as const;
  return "muted" as const;
}

export default function ReviewDetailPage() {
  const params = useParams<{ id: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["review", params.id],
    queryFn: () => fetchReview(params.id),
    enabled: !!params.id,
  });

  return (
    <Shell title="Review details" description="Findings, verification, timeline, and cost">
      {error ? (
        <p className="text-sm text-destructive">Failed to load review.</p>
      ) : isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : data ? (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">Status</p>
                <Badge className="mt-1" variant={data.status === "completed" ? "success" : "muted"}>
                  {data.status}
                </Badge>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">Commit</p>
                <p className="mt-1 font-mono text-sm">{shortSha(data.commit_sha)}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">Duration</p>
                <p className="mt-1 text-sm">{formatDuration(data.duration_ms)}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">API cost</p>
                <p className="mt-1 text-sm">{formatUsd(data.estimated_cost_usd || 0)}</p>
                <p className="text-[11px] text-muted-foreground">
                  {data.input_tokens}/{data.output_tokens} tokens · {data.model_name || "—"}
                </p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="whitespace-pre-wrap text-sm text-muted-foreground">
                {data.summary || "No summary"}
              </pre>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>
                Findings ({data.findings?.length ?? 0}) · published {data.published_count} · rejected{" "}
                {data.rejected_count}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {(data.findings ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">No findings recorded.</p>
              ) : (
                data.findings.map((f: any) => (
                  <div key={f.id} className="rounded-md border border-border p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={sevVariant(f.severity)}>{f.severity}</Badge>
                      <Badge variant="muted">{f.category}</Badge>
                      <Badge variant={f.published ? "success" : "warning"}>
                        {f.verification_status}
                      </Badge>
                      <span className="text-sm font-medium">{f.title}</span>
                    </div>
                    <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                      {f.file_path}:{f.start_line}-{f.end_line} · conf {f.confidence?.toFixed?.(2)}
                    </p>
                    <p className="mt-2 text-sm">{f.explanation}</p>
                    <p className="mt-1 text-sm text-muted-foreground">{f.failure_scenario}</p>
                    {f.suggested_fix ? (
                      <p className="mt-1 text-sm text-accent">Suggested fix: {f.suggested_fix}</p>
                    ) : null}
                    {f.rejected_reason ? (
                      <p className="mt-1 text-xs text-destructive">Rejected: {f.rejected_reason}</p>
                    ) : null}
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Timeline</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-1 text-sm">
                {(data.timeline ?? []).map((t: any, i: number) => (
                  <li key={i} className="font-mono text-xs text-muted-foreground">
                    {t.stage}: {t.status}
                    {t.count != null ? ` (${t.count})` : ""}
                    {t.published != null ? ` published=${t.published}` : ""}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      ) : null}
    </Shell>
  );
}