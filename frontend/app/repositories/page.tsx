"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Shell } from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { api } from "@/lib/api";
import { authHeaders } from "@/lib/auth";
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
  const [rulesRepoId, setRulesRepoId] = useState<string | null>(null);
  const [ignorePaths, setIgnorePaths] = useState("");
  const [severity, setSeverity] = useState("medium");
  const [confidence, setConfidence] = useState("0.7");

  const { data, isLoading, error } = useQuery({
    queryKey: ["repositories"],
    queryFn: api.repositories,
    refetchInterval: 20_000,
  });
  const github = useQuery({
    queryKey: ["github-status"],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/api/github/status`, { headers: authHeaders() });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
  });
  const indexJobs = useQuery({
    queryKey: ["index-jobs", rulesRepoId],
    queryFn: () => api.indexJobs(rulesRepoId!),
    enabled: !!rulesRepoId,
    refetchInterval: 4000,
  });

  const reindex = useMutation({
    mutationFn: async ({ id, full }: { id: string; full: boolean }) => {
      const res = await fetch(
        `${API_URL}/api/repositories/${id}/reindex?full=${full ? "true" : "false"}`,
        { method: "POST", headers: authHeaders() },
      );
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ["repositories"] });
      qc.invalidateQueries({ queryKey: ["index-jobs", vars.id] });
    },
  });

  const toggleAuto = useMutation({
    mutationFn: async ({ id, enabled }: { id: string; enabled: boolean }) => {
      const res = await fetch(
        `${API_URL}/api/repositories/${id}/auto-review?enabled=${enabled}`,
        { method: "POST", headers: authHeaders() },
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
        { method: "POST", headers: authHeaders() },
      );
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["repositories"] }),
  });

  const saveRules = useMutation({
    mutationFn: async () => {
      if (!rulesRepoId) return;
      return api.putRepoRules(rulesRepoId, {
        ignore_paths: ignorePaths
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
        severity_threshold: severity,
        confidence_threshold: Number(confidence),
      });
    },
  });

  async function openRules(id: string) {
    setRulesRepoId(id);
    try {
      const rules = await api.getRepoRules(id);
      setIgnorePaths((rules.ignore_paths || []).join("\n"));
      setSeverity(rules.severity_threshold || "medium");
      setConfidence(String(rules.confidence_threshold ?? 0.7));
    } catch {
      setIgnorePaths("");
      setSeverity("medium");
      setConfidence("0.7");
    }
  }

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
                    <td colSpan={7}>
                      <EmptyState
                        title="No repositories yet"
                        description="Install the GitHub App and sync an organization to pull repos into Spider."
                        actionHref="/onboarding"
                        actionLabel="Open onboarding"
                      />
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
                              onClick={() => reindex.mutate({ id: repo.id, full: false })}
                              disabled={reindex.isPending}
                            >
                              Re-index
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => reindex.mutate({ id: repo.id, full: true })}
                              disabled={reindex.isPending}
                            >
                              Full
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => openRules(repo.id)}>
                              Rules
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

      {rulesRepoId ? (
        <Card>
          <CardHeader>
            <CardTitle>Review rules</CardTitle>
            <CardDescription>
              Per-repo ignore paths and thresholds. Progress:{" "}
              {indexJobs.data?.latest
                ? `${indexJobs.data.latest.progress_pct}% (${indexJobs.data.latest.files_processed}/${indexJobs.data.latest.total_files})`
                : "—"}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            <label className="text-xs text-muted-foreground sm:col-span-2">
              Ignore paths (one per line)
              <textarea
                className="mt-1.5 min-h-24 w-full rounded-lg border border-input bg-background px-3 py-2 text-[13px]"
                value={ignorePaths}
                onChange={(e) => setIgnorePaths(e.target.value)}
                placeholder={"vendor/**\n*.generated.ts"}
              />
            </label>
            <label className="text-xs text-muted-foreground">
              Severity threshold
              <select
                className="mt-1.5 w-full rounded-lg border border-input bg-background px-3 py-2 text-[13px]"
                value={severity}
                onChange={(e) => setSeverity(e.target.value)}
              >
                {["critical", "high", "medium", "low"].map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-muted-foreground">
              Confidence threshold
              <input
                className="mt-1.5 w-full rounded-lg border border-input bg-background px-3 py-2 text-[13px]"
                value={confidence}
                onChange={(e) => setConfidence(e.target.value)}
              />
            </label>
            <div className="flex gap-2 sm:col-span-2">
              <Button size="sm" onClick={() => saveRules.mutate()} disabled={saveRules.isPending}>
                {saveRules.isPending ? "Saving…" : "Save rules"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setRulesRepoId(null)}>
                Close
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </Shell>
  );
}
