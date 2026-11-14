"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Shell } from "@/components/layout/shell";
import { StatCard } from "@/components/metrics/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

export default function AuditPage() {
  const qc = useQueryClient();
  const metrics = useQuery({ queryKey: ["audit-metrics"], queryFn: api.auditMetrics });
  const logs = useQuery({ queryKey: ["audit-logs"], queryFn: () => api.auditLogs() });
  const webhooks = useQuery({
    queryKey: ["webhooks-failed"],
    queryFn: () => api.listWebhooks("failed"),
  });

  const replay = useMutation({
    mutationFn: (id: string) => api.replayWebhook(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["webhooks-failed"] });
      qc.invalidateQueries({ queryKey: ["audit-logs"] });
    },
  });

  const m = metrics.data;

  return (
    <Shell
      title="Audit & Observability"
      description="Action history, worker signals, and webhook dead-letter replay."
      breadcrumb="System"
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Reviews (7d)" value={m?.reviews_started ?? "…"} />
        <StatCard label="Failed reviews" value={m?.reviews_failed ?? "…"} tone="danger" />
        <StatCard label="Webhook failures" value={m?.webhook_failures ?? "…"} tone="warning" />
        <StatCard
          label="Week spend"
          value={m ? `$${m.week_cost_usd.toFixed(4)}` : "…"}
          tone={m?.cost_spike ? "danger" : "accent"}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Audit log</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <table className="data-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Action</th>
                <th>Resource</th>
                <th>Actor</th>
              </tr>
            </thead>
            <tbody>
              {(logs.data?.items ?? []).length === 0 ? (
                <tr>
                  <td colSpan={4} className="!text-muted-foreground">
                    No audit events yet.
                  </td>
                </tr>
              ) : (
                logs.data!.items.map((row) => (
                  <tr key={row.id}>
                    <td className="text-[12px] text-muted-foreground">
                      {row.created_at ? new Date(row.created_at).toLocaleString() : "—"}
                    </td>
                    <td>
                      <Badge variant="muted">{row.action}</Badge>
                    </td>
                    <td className="font-mono text-xs">
                      {row.resource_type}/{row.resource_id || "—"}
                    </td>
                    <td className="font-mono text-xs">{row.actor_user_id || "system"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Failed webhooks (DLQ)</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <table className="data-table">
            <thead>
              <tr>
                <th>Delivery</th>
                <th>Event</th>
                <th>Retries</th>
                <th>Error</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {(webhooks.data?.items ?? []).length === 0 ? (
                <tr>
                  <td colSpan={5} className="!text-muted-foreground">
                    No failed webhooks.
                  </td>
                </tr>
              ) : (
                webhooks.data!.items.map((w) => (
                  <tr key={w.id}>
                    <td className="font-mono text-xs">{w.delivery_id}</td>
                    <td>{w.event_type}</td>
                    <td>{w.retry_count}</td>
                    <td className="max-w-xs truncate text-[12px] text-muted-foreground">
                      {w.error_message || "—"}
                    </td>
                    <td>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={replay.isPending || !!w.dead_lettered_at}
                        onClick={() => replay.mutate(w.id)}
                      >
                        Replay
                      </Button>
                    </td>
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