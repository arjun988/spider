"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Shell } from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type ReviewFinding } from "@/lib/api";
import { formatDuration, formatUsd, shortSha } from "@/lib/utils";

function sevVariant(sev: string) {
  if (sev === "critical" || sev === "high") return "destructive" as const;
  if (sev === "medium") return "warning" as const;
  return "muted" as const;
}

export default function ReviewDetailPage() {
  const params = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["review", params.id],
    queryFn: () => api.getReview(params.id),
    enabled: !!params.id,
    refetchInterval: (query) =>
      query.state.data?.status &&
      !["completed", "failed"].includes(query.state.data.status)
        ? 5000
        : false,
  });

  const feedback = useMutation({
    mutationFn: ({
      findingId,
      feedback_type,
    }: {
      findingId: string;
      feedback_type: "helpful" | "false_positive" | "dismissed" | "fixed";
    }) => api.submitFeedback(findingId, { feedback_type }),
    onSuccess: () => {
      setFeedbackMsg("Feedback saved.");
      qc.invalidateQueries({ queryKey: ["review", params.id] });
    },
    onError: (err: Error) => setFeedbackMsg(err.message),
  });

  const findings = useMemo(() => {
    const list = data?.findings ?? [];
    if (severityFilter === "all") return list;
    return list.filter((f: ReviewFinding) => f.severity === severityFilter);
  }, [data?.findings, severityFilter]);

  return (
    <Shell
      title="Review details"
      description="Findings, verification, timeline, and cost"
      breadcrumb="Workspace / Reviews"
    >
      <div className="mb-3">
        <Link href="/pull-requests" className="text-xs text-primary hover:underline">
          ← Back to pull requests
        </Link>
      </div>

      {error ? (
        <p className="text-sm text-destructive">Failed to load review.</p>
      ) : isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : data ? (
        <div className="space-y-4">
          <Card>
            <CardContent className="flex flex-wrap items-start justify-between gap-4 p-4">
              <div className="min-w-0">
                <p className="eyebrow mb-1.5">{data.repository_full_name || "repository"}</p>
                <h2 className="text-lg font-semibold tracking-tight">
                  {data.pr_number != null ? `#${data.pr_number} ` : ""}
                  {data.pr_title || "Untitled PR"}
                </h2>
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <Badge
                    variant={
                      data.status === "completed"
                        ? "success"
                        : data.status === "failed"
                          ? "destructive"
                          : "accent"
                    }
                  >
                    {data.status}
                  </Badge>
                  <Badge variant="muted">{shortSha(data.commit_sha)}</Badge>
                  <Badge variant="muted">{data.trigger}</Badge>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {data.pr_html_url ? (
                  <a href={data.pr_html_url} target="_blank" rel="noreferrer">
                    <Button variant="outline" size="sm">
                      Open on GitHub
                    </Button>
                  </a>
                ) : null}
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">Status</p>
                <Badge
                  className="mt-1"
                  variant={
                    data.status === "completed"
                      ? "success"
                      : data.status === "failed"
                        ? "destructive"
                        : "accent"
                  }
                >
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

          {data.error_message ? (
            <Card className="border-destructive/40">
              <CardHeader>
                <CardTitle>Error</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="whitespace-pre-wrap text-sm text-destructive">
                  {data.error_message}
                </pre>
              </CardContent>
            </Card>
          ) : null}

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
            <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
              <CardTitle>
                Findings ({findings.length}/{data.findings?.length ?? 0}) · published{" "}
                {data.published_count} · rejected {data.rejected_count}
              </CardTitle>
              <select
                className="rounded-sm border border-border bg-card px-2 py-1 text-xs"
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
              >
                {["all", "critical", "high", "medium", "low", "informational"].map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </CardHeader>
            <CardContent className="space-y-3">
              {feedbackMsg ? (
                <p className="text-xs text-muted-foreground">{feedbackMsg}</p>
              ) : null}
              {findings.length === 0 ? (
                <p className="text-sm text-muted-foreground">No findings in this filter.</p>
              ) : (
                findings.map((f) => (
                  <div key={f.id} className="rounded-md border border-border p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={sevVariant(f.severity)}>{f.severity}</Badge>
                      <Badge variant="muted">{f.category}</Badge>
                      <Badge variant="muted">{f.verification_status}</Badge>
                      {f.published ? <Badge variant="success">published</Badge> : null}
                      <span className="text-sm font-medium">{f.title}</span>
                    </div>
                    <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                      {f.file_path}:{f.start_line}-{f.end_line} · conf {f.confidence?.toFixed?.(2)}
                    </p>
                    <p className="mt-2 text-sm">{f.explanation}</p>
                    <p className="mt-1 text-sm text-muted-foreground">{f.failure_scenario}</p>
                    {f.suggested_fix ? (
                      <p className="mt-1 text-sm text-primary">Suggested fix: {f.suggested_fix}</p>
                    ) : null}
                    {f.rejected_reason ? (
                      <p className="mt-1 text-xs text-destructive">Rejected: {f.rejected_reason}</p>
                    ) : null}
                    <div className="mt-2 flex flex-wrap gap-1">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={feedback.isPending}
                        onClick={() =>
                          feedback.mutate({ findingId: f.id, feedback_type: "helpful" })
                        }
                      >
                        Helpful
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={feedback.isPending}
                        onClick={() =>
                          feedback.mutate({ findingId: f.id, feedback_type: "false_positive" })
                        }
                      >
                        False positive
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={feedback.isPending}
                        onClick={() =>
                          feedback.mutate({ findingId: f.id, feedback_type: "dismissed" })
                        }
                      >
                        Dismiss
                      </Button>
                    </div>
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
                {(data.timeline ?? []).length === 0 ? (
                  <li className="text-muted-foreground">No timeline events.</li>
                ) : (
                  (data.timeline ?? []).map((t, i) => (
                    <li key={i} className="font-mono text-xs text-muted-foreground">
                      {String(t.stage)}: {String(t.status)}
                      {t.count != null ? ` (${String(t.count)})` : ""}
                      {t.published != null ? ` published=${String(t.published)}` : ""}
                    </li>
                  ))
                )}
              </ul>
            </CardContent>
          </Card>
        </div>
      ) : null}
    </Shell>
  );
}
