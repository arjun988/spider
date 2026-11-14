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
      description="Findings, verification, timeline, and cost."
      breadcrumb="Workspace"
      actions={
        <Link href="/pull-requests">
          <Button variant="outline" size="sm">
            ← Pull requests
          </Button>
        </Link>
      }
    >
      {error ? (
        <p className="text-sm text-destructive">Failed to load review.</p>
      ) : isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : data ? (
        <div className="space-y-6">
          <Card>
            <CardContent className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="eyebrow mb-1.5">
                  {data.repository_full_name || "repository"}
                </p>
                <h2 className="text-[1.25rem] font-semibold tracking-tight">
                  {data.pr_number != null ? `#${data.pr_number} ` : ""}
                  {data.pr_title || "Untitled PR"}
                </h2>
                <div className="mt-3 flex flex-wrap items-center gap-1.5">
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
              {data.pr_html_url ? (
                <a href={data.pr_html_url} target="_blank" rel="noreferrer">
                  <Button variant="outline" size="sm">
                    Open on GitHub
                  </Button>
                </a>
              ) : null}
            </CardContent>
          </Card>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardContent className="space-y-2">
                <p className="eyebrow">Status</p>
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
              </CardContent>
            </Card>
            <Card>
              <CardContent className="space-y-2">
                <p className="eyebrow">Commit</p>
                <p className="font-mono text-sm tabular-nums">
                  {shortSha(data.commit_sha)}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="space-y-2">
                <p className="eyebrow">Duration</p>
                <p className="text-sm tabular-nums">
                  {formatDuration(data.duration_ms)}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="space-y-2">
                <p className="eyebrow">API cost</p>
                <p className="text-sm tabular-nums">
                  {formatUsd(data.estimated_cost_usd || 0)}
                </p>
                <p className="text-[11px] text-muted-foreground">
                  {data.input_tokens}/{data.output_tokens} tokens ·{" "}
                  {data.model_name || "—"}
                </p>
              </CardContent>
            </Card>
          </div>

          {data.error_message ? (
            <Card className="border-destructive/40 bg-destructive/5">
              <CardHeader>
                <CardTitle>Error</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="whitespace-pre-wrap font-mono text-[13px] text-destructive">
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
              <pre className="whitespace-pre-wrap text-[13px] leading-relaxed text-muted-foreground">
                {data.summary || "No summary"}
              </pre>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
              <div>
                <CardTitle>
                  Findings ({findings.length}/{data.findings?.length ?? 0})
                </CardTitle>
                <p className="mt-1 text-[12px] text-muted-foreground">
                  published {data.published_count} · rejected {data.rejected_count}
                </p>
              </div>
              <select
                className="rounded-lg border border-input bg-background px-3 py-2 text-[12px] outline-none focus-visible:shadow-focus"
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
              >
                {["all", "critical", "high", "medium", "low", "informational"].map(
                  (s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ),
                )}
              </select>
            </CardHeader>
            <CardContent className="space-y-3">
              {feedbackMsg ? (
                <p className="text-xs text-muted-foreground">{feedbackMsg}</p>
              ) : null}
              {findings.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No findings in this filter.
                </p>
              ) : (
                findings.map((f) => (
                  <div
                    key={f.id}
                    className="rounded-xl border border-border bg-muted/20 p-4"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={sevVariant(f.severity)}>{f.severity}</Badge>
                      <Badge variant="muted">{f.category}</Badge>
                      <Badge variant="muted">{f.verification_status}</Badge>
                      {f.published ? (
                        <Badge variant="success">published</Badge>
                      ) : null}
                      <span className="text-[13px] font-medium tracking-tight">
                        {f.title}
                      </span>
                    </div>
                    <p className="mt-2 font-mono text-[11px] text-muted-foreground">
                      {f.file_path}:{f.start_line}-{f.end_line} · conf{" "}
                      {f.confidence?.toFixed?.(2)}
                    </p>
                    <p className="mt-2 text-[13px] leading-relaxed">{f.explanation}</p>
                    <p className="mt-1 text-[13px] text-muted-foreground">
                      {f.failure_scenario}
                    </p>
                    {f.suggested_fix ? (
                      <p className="mt-2 text-[13px] text-primary">
                        Suggested fix: {f.suggested_fix}
                      </p>
                    ) : null}
                    {f.rejected_reason ? (
                      <p className="mt-1 text-xs text-destructive">
                        Rejected: {f.rejected_reason}
                      </p>
                    ) : null}
                    {f.decision_trace ? (
                      <div className="mt-3 rounded-lg border border-border/80 bg-background/60 p-3">
                        <p className="eyebrow mb-1">
                          Why {f.decision_trace.outcome === "published" ? "published" : "rejected"}
                        </p>
                        <p className="text-[12px] leading-relaxed text-muted-foreground">
                          {f.decision_trace.reason || "—"}
                        </p>
                        {(f.decision_trace.gates?.length ?? 0) > 0 ? (
                          <div className="mt-2 flex flex-wrap gap-1">
                            {f.decision_trace.gates!.map((g) => (
                              <Badge key={g} variant="muted">
                                {g}
                              </Badge>
                            ))}
                          </div>
                        ) : null}
                        {f.decision_trace.feedback_confidence_floor != null ? (
                          <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                            confidence floor {f.decision_trace.feedback_confidence_floor.toFixed(2)}
                          </p>
                        ) : null}
                      </div>
                    ) : null}
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={feedback.isPending}
                        onClick={() =>
                          feedback.mutate({
                            findingId: f.id,
                            feedback_type: "helpful",
                          })
                        }
                      >
                        Helpful
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={feedback.isPending}
                        onClick={() =>
                          feedback.mutate({
                            findingId: f.id,
                            feedback_type: "false_positive",
                          })
                        }
                      >
                        False positive
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={feedback.isPending}
                        onClick={() =>
                          feedback.mutate({
                            findingId: f.id,
                            feedback_type: "dismissed",
                          })
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
              <ul className="space-y-2">
                {(data.timeline ?? []).length === 0 ? (
                  <li className="text-sm text-muted-foreground">
                    No timeline events.
                  </li>
                ) : (
                  (data.timeline ?? []).map((t, i) => (
                    <li
                      key={i}
                      className="rounded-lg border border-border/70 bg-muted/30 px-3 py-2 font-mono text-[11px] text-muted-foreground"
                    >
                      {String(t.stage)}: {String(t.status)}
                      {t.count != null ? ` (${String(t.count)})` : ""}
                      {t.published != null
                        ? ` published=${String(t.published)}`
                        : ""}
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
