"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Shell } from "@/components/layout/shell";
import { StatCard } from "@/components/metrics/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

export default function WebhooksPage() {
  const qc = useQueryClient();
  const [deliveryId, setDeliveryId] = useState("");
  const metrics = useQuery({ queryKey: ["webhook-metrics"], queryFn: () => api.webhookMetrics(7) });
  const events = useQuery({ queryKey: ["webhooks-all"], queryFn: () => api.listWebhooks() });

  const replay = useMutation({
    mutationFn: (id: string) => api.replayWebhook(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["webhooks-all"] });
      qc.invalidateQueries({ queryKey: ["webhook-metrics"] });
    },
  });

  const redeliver = useMutation({
    mutationFn: (id: string) => api.redeliverWebhook(id),
    onSuccess: () => {
      setDeliveryId("");
      qc.invalidateQueries({ queryKey: ["webhooks-all"] });
      qc.invalidateQueries({ queryKey: ["webhook-metrics"] });
    },
  });

  const m = metrics.data;

  return (
    <Shell
      title="Webhook delivery"
      description="Latency, success rate, dead-letter replay, and GitHub redelivery by delivery ID."
      breadcrumb="System"
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Deliveries (7d)" value={m?.total ?? "…"} />
        <StatCard
          label="Success rate"
          value={
            m?.success_rate != null ? `${(m.success_rate * 100).toFixed(1)}%` : "…"
          }
          tone="accent"
        />
        <StatCard
          label="Avg latency"
          value={m?.avg_latency_ms != null ? `${Math.round(m.avg_latency_ms)}ms` : "…"}
        />
        <StatCard label="Failed" value={m?.failed ?? "…"} tone="danger" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Redeliver from GitHub</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="flex-1 text-[12px] text-muted-foreground">
            Delivery ID
            <input
              className="mt-1.5 w-full rounded-lg border border-input bg-background px-3 py-2.5 text-[13px]"
              value={deliveryId}
              onChange={(e) => setDeliveryId(e.target.value)}
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            />
          </label>
          <Button
            disabled={!deliveryId.trim() || redeliver.isPending}
            onClick={() => redeliver.mutate(deliveryId.trim())}
          >
            {redeliver.isPending ? "Queuing…" : "Redeliver"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent deliveries</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          <table className="data-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Event</th>
                <th>Status</th>
                <th>Latency</th>
                <th>Delivery</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {(events.data?.items ?? []).length === 0 ? (
                <tr>
                  <td colSpan={6} className="!text-muted-foreground">
                    No webhook events yet. Point GitHub App webhooks at your tunnel URL.
                  </td>
                </tr>
              ) : (
                events.data!.items.map((row) => (
                  <tr key={row.id}>
                    <td className="text-[12px] text-muted-foreground">
                      {row.created_at ? new Date(row.created_at).toLocaleString() : "—"}
                    </td>
                    <td>
                      <Badge variant="muted">{row.event_type}</Badge>
                    </td>
                    <td>
                      <Badge
                        variant={
                          row.status === "processed"
                            ? "success"
                            : row.status === "failed"
                              ? "destructive"
                              : "muted"
                        }
                      >
                        {row.status}
                      </Badge>
                    </td>
                    <td className="font-mono text-xs">
                      {row.latency_ms != null ? `${row.latency_ms}ms` : "—"}
                    </td>
                    <td className="max-w-[140px] truncate font-mono text-[11px]">
                      {row.delivery_id}
                    </td>
                    <td>
                      <div className="flex gap-1">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => replay.mutate(row.id)}
                          disabled={replay.isPending}
                        >
                          Replay
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => redeliver.mutate(row.delivery_id)}
                          disabled={redeliver.isPending}
                        >
                          GH
                        </Button>
                      </div>
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
