"use client";

import { useQuery } from "@tanstack/react-query";
import { Shell } from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
  const { data, isLoading, error } = useQuery({
    queryKey: ["pull-requests"],
    queryFn: () => api.pullRequests(),
  });

  return (
    <Shell title="Pull Requests" description="Reviewed and pending PRs across connected repos">
      <Card>
        <CardHeader>
          <CardTitle>
            Pull requests{" "}
            <span className="text-muted-foreground">({data?.total ?? 0})</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {error ? (
            <p className="p-4 text-sm text-destructive">Failed to load pull requests.</p>
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
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td colSpan={6} className="!text-muted-foreground">
                      Loading…
                    </td>
                  </tr>
                ) : (data?.items.length ?? 0) === 0 ? (
                  <tr>
                    <td colSpan={6} className="!text-muted-foreground">
                      No pull requests recorded yet. Webhooks will populate this list in Phase 2.
                    </td>
                  </tr>
                ) : (
                  data?.items.map((pr) => (
                    <tr key={pr.id}>
                      <td>
                        <div className="font-medium">
                          #{pr.number} {pr.title}
                        </div>
                      </td>
                      <td className="text-xs">{pr.repository_full_name || "—"}</td>
                      <td>{pr.author_login}</td>
                      <td>
                        <Badge variant={reviewVariant(pr.review_status)}>
                          {pr.review_status}
                        </Badge>
                      </td>
                      <td>
                        {pr.findings_count}
                        {pr.critical_count > 0 ? (
                          <span className="ml-1 text-xs text-destructive">
                            ({pr.critical_count} crit)
                          </span>
                        ) : null}
                      </td>
                      <td className="font-mono text-xs">{shortSha(pr.head_sha)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </Shell>
  );
}