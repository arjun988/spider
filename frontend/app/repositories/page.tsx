"use client";

import { useQuery } from "@tanstack/react-query";
import { Shell } from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { shortSha } from "@/lib/utils";

function statusVariant(status: string) {
  switch (status) {
    case "ready":
      return "success" as const;
    case "indexing":
      return "accent" as const;
    case "failed":
      return "destructive" as const;
    case "stale":
      return "warning" as const;
    default:
      return "muted" as const;
  }
}

export default function RepositoriesPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["repositories"],
    queryFn: api.repositories,
  });

  return (
    <Shell
      title="Repositories"
      description="Connected repositories and indexing status"
    >
      <Card>
        <CardHeader>
          <CardTitle>
            Connected repos{" "}
            <span className="text-muted-foreground">({data?.total ?? 0})</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {error ? (
            <p className="p-4 text-sm text-destructive">Failed to load repositories.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Repository</th>
                  <th>Language</th>
                  <th>Index</th>
                  <th>Last commit</th>
                  <th>PRs reviewed</th>
                  <th>Auto review</th>
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
                      No repositories yet. Install the GitHub App (Phase 2) to discover repos.
                    </td>
                  </tr>
                ) : (
                  data?.items.map((repo) => (
                    <tr key={repo.id}>
                      <td>
                        <div className="font-medium">{repo.full_name}</div>
                        <div className="text-xs text-muted-foreground">{repo.owner_login}</div>
                      </td>
                      <td>{repo.primary_language || "—"}</td>
                      <td>
                        <Badge variant={statusVariant(repo.indexing_status)}>
                          {repo.indexing_status}
                        </Badge>
                      </td>
                      <td className="font-mono text-xs">
                        {shortSha(repo.last_indexed_commit_sha)}
                      </td>
                      <td>{repo.prs_reviewed_count}</td>
                      <td>
                        <Badge variant={repo.auto_review_enabled ? "success" : "muted"}>
                          {repo.auto_review_enabled ? "on" : "off"}
                        </Badge>
                      </td>
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