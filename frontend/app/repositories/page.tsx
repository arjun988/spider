"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Shell } from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { shortSha } from "@/lib/utils";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["repositories"],
    queryFn: api.repositories,
    refetchInterval: 20_000,
  });
  const github = useQuery({
    queryKey: ["github-status"],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/api/github/status`);
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
  });

  const reindex = useMutation({
    mutationFn: async (id: string) => {
      const res = await fetch(`${API_URL}/api/repositories/${id}/reindex?full=true`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["repositories"] }),
  });

  const toggleAuto = useMutation({
    mutationFn: async ({ id, enabled }: { id: string; enabled: boolean }) => {
      const res = await fetch(
        `${API_URL}/api/repositories/${id}/auto-review?enabled=${enabled}`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["repositories"] }),
  });

  const syncRepos = useMutation({
    mutationFn: async (installationId: number) => {
      const res = await fetch(
        `${API_URL}/api/github/installations/${installationId}/sync-repos`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["repositories"] }),
  });

  return (
    <Shell
      title="Repositories"
      description="Connected repositories and indexing status."
      breadcrumb="Workspace"
    >
      <Card>
        <CardHeader>
          <CardTitle>GitHub App</CardTitle>
          <CardDescription>
            Install on an org, then sync to pull repositories into Spider.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3 text-[13px]">
          <Badge variant={github.data?.configured ? "success" : "warning"}>
            {github.data?.configured ? "configured" : "not configured"}
          </Badge>
          {github.data?.install_url ? (
            <a
              className="font-medium text-primary hover:underline"
              href={github.data.install_url}
              target="_blank"
              rel="noreferrer"
            >
              Install on organization
            </a>
          ) : (
            <span className="text-muted-foreground">
              Set GITHUB_APP_NAME for install link
            </span>
          )}
          {(github.data?.installations ?? []).map((inst: any) => (
            <Button
              key={inst.id}
              size="sm"
              variant="outline"
              onClick={() => syncRepos.mutate(inst.installation_id)}
              disabled={syncRepos.isPending}
            >
              Sync {inst.account_login}
            </Button>
          ))}
        </CardContent>
      </Card>

      <section className="space-y-3">
        <div className="flex items-end justify-between gap-3">
          <div>
            <p className="eyebrow">Catalog</p>
            <h2 className="section-title">
              Connected repos{" "}
              <span className="text-muted-foreground">({data?.total ?? 0})</span>
            </h2>
          </div>
        </div>
        <Card>
          <CardContent className="p-0">
            {error ? (
              <p className="p-5 text-sm text-destructive">Failed to load repositories.</p>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Repository</th>
                    <th>Language</th>
                    <th>Index</th>
                    <th>Last commit</th>
                    <th>PRs</th>
                    <th>Auto</th>
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
                        No repositories yet. Install the GitHub App and sync.
                      </td>
                    </tr>
                  ) : (
                    data?.items.map((repo) => (
                      <tr key={repo.id}>
                        <td>
                          <div className="font-medium tracking-tight">
                            {repo.html_url ? (
                              <a
                                href={repo.html_url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-primary hover:underline"
                              >
                                {repo.full_name}
                              </a>
                            ) : (
                              repo.full_name
                            )}
                          </div>
                        </td>
                        <td className="text-muted-foreground">
                          {repo.primary_language || "—"}
                        </td>
                        <td>
                          <Badge variant={statusVariant(repo.indexing_status)}>
                            {repo.indexing_status}
                          </Badge>
                        </td>
                        <td className="font-mono text-xs tabular-nums">
                          {shortSha(repo.last_indexed_commit_sha)}
                        </td>
                        <td className="tabular-nums">{repo.prs_reviewed_count}</td>
                        <td>
                          <Badge variant={repo.auto_review_enabled ? "success" : "muted"}>
                            {repo.auto_review_enabled ? "on" : "off"}
                          </Badge>
                        </td>
                        <td>
                          <div className="flex flex-wrap gap-1.5">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => reindex.mutate(repo.id)}
                              disabled={reindex.isPending}
                            >
                              Re-index
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() =>
                                toggleAuto.mutate({
                                  id: repo.id,
                                  enabled: !repo.auto_review_enabled,
                                })
                              }
                            >
                              {repo.auto_review_enabled ? "Disable" : "Enable"}
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
