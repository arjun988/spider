"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Shell } from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { shortSha } from "@/lib/utils";

function reviewVariant(status: string) {
  switch (status) {
    case "completed":
      return "success" as const;
    case "failed":
      return "destructive" as const;
    case "reviewing":
    case "queued":
      return "accent" as const;
    default:
      return "muted" as const;
  }
}

export default function PullRequestsPage() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["pull-requests"],
    queryFn: () => api.pullRequests(),
    refetchInterval: 15_000,
  });

  const reReview = useMutation({
    mutationFn: ({ id, force }: { id: string; force: boolean }) =>
      api.triggerReview(id, force),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pull-requests"] });
      qc.invalidateQueries({ queryKey: ["overview"] });
    },
  });

  return (
    <Shell
      title="Pull Requests"
      description="Reviewed and pending PRs across connected repos."
      breadcrumb="Workspace"
    >
      <section className="space-y-3">
        <div>
          <p className="eyebrow">Queue</p>
          <h2 className="section-title">
            Pull requests{" "}
            <span className="text-muted-foreground">({data?.total ?? 0})</span>
          </h2>
        </div>
        <Card>
          <CardContent className="p-0">
            {error ? (
              <p className="p-5 text-sm text-destructive">Failed to load pull requests.</p>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>PR</th>
                    <th>Repository</th>
                    <th>Author</th>
                    <th>Review</th>
                    <th>Findings</th>
                    <th>SHA</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading ? (
                    <tr>
                      <td colSpan={7} className="!text-muted-foreground">
                        Loading…
                      </td>
                    </tr>
                  ) : (data?.items.length ?? 0) === 0 ? (
                    <tr>
                      <td colSpan={7} className="!text-muted-foreground">
                        No pull requests yet. Open a PR on a connected repo to start a review.
                      </td>
                    </tr>
                  ) : (
                    data?.items.map((pr) => (
                      <tr key={pr.id}>
                        <td>
                          <div className="font-medium tracking-tight">
                            {pr.latest_review_job_id ? (
                              <Link
                                href={`/reviews/${pr.latest_review_job_id}`}
                                className="text-primary hover:underline"
                              >
                                #{pr.number} {pr.title}
                              </Link>
                            ) : pr.html_url ? (
                              <a
                                href={pr.html_url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-primary hover:underline"
                              >
                                #{pr.number} {pr.title}
                              </a>
                            ) : (
                              <>
                                #{pr.number} {pr.title}
                              </>
                            )}
                          </div>
                          {pr.html_url ? (
                            <a
                              href={pr.html_url}
                              target="_blank"
                              rel="noreferrer"
                              className="mt-0.5 inline-block text-[11px] text-muted-foreground hover:underline"
                            >
                              Open on GitHub
                            </a>
                          ) : null}
                        </td>
                        <td className="max-w-[180px] truncate text-[12px] text-muted-foreground">
                          {pr.repository_full_name || "—"}
                        </td>
                        <td className="text-[13px]">{pr.author_login}</td>
                        <td>
                          <Badge variant={reviewVariant(pr.review_status)}>
                            {pr.review_status}
                          </Badge>
                        </td>
                        <td className="tabular-nums">
                          {pr.findings_count}
                          {pr.critical_count > 0 ? (
                            <span className="ml-1 text-[11px] text-destructive">
                              ({pr.critical_count} crit)
                            </span>
                          ) : null}
                        </td>
                        <td className="font-mono text-xs tabular-nums">
                          {shortSha(pr.head_sha)}
                        </td>
                        <td>
                          <div className="flex flex-wrap gap-1.5">
                            {pr.latest_review_job_id ? (
                              <Link href={`/reviews/${pr.latest_review_job_id}`}>
                                <Button size="sm" variant="outline">
                                  Details
                                </Button>
                              </Link>
                            ) : null}
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={reReview.isPending}
                              onClick={() =>
                                reReview.mutate({
                                  id: pr.id,
                                  force: pr.review_status === "completed",
                                })
                              }
                            >
                              {pr.review_status === "failed"
                                ? "Retry"
                                : pr.review_status === "completed"
                                  ? "Re-review"
                                  : "Review"}
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      </section>
    </Shell>
  );
}
