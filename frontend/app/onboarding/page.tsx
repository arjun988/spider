"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Shell } from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

export default function OnboardingPage() {
  const system = useQuery({ queryKey: ["system"], queryFn: api.systemStatus });
  const llm = useQuery({ queryKey: ["gemini"], queryFn: api.geminiConfig });
  const repos = useQuery({ queryKey: ["repositories"], queryFn: api.repositories });
  const overview = useQuery({ queryKey: ["overview"], queryFn: api.overview });
  const webhooks = useQuery({
    queryKey: ["webhooks-all"],
    queryFn: () => api.listWebhooks(),
    retry: false,
  });

  const missingApp =
    !system.data?.github_app_configured ||
    !system.data?.private_key_configured ||
    !system.data?.webhook_secret_configured;
  const missingKey =
    !(llm.data?.configured || llm.data?.connection_status === "connected");
  const missingOauth = system.data && !system.data.github_oauth_configured;
  const missingTunnel =
    (webhooks.data?.items?.length ?? 0) === 0 &&
    !!system.data?.github_app_configured;

  const steps = [
    {
      title: "Install GitHub App + private key",
      done: !missingApp,
      href: "/settings",
      detail: missingApp
        ? "Missing App ID, webhook secret, or PEM key — configure env and restart."
        : "GitHub App credentials look present.",
      auto: missingApp ? "Detected: App / key / webhook secret incomplete" : null,
    },
    {
      title: "GitHub OAuth SSO",
      done: !missingOauth,
      href: "/login",
      detail: missingOauth
        ? "Set GITHUB_APP_CLIENT_ID and CLIENT_SECRET for dashboard login."
        : "OAuth client is configured for SSO.",
      auto: missingOauth ? "Detected: OAuth client missing" : null,
    },
    {
      title: "Configure LLM",
      done: !missingKey,
      href: "/settings",
      detail: "Add a Gemini or LiteLLM key and validate the connection.",
      auto: missingKey ? "Detected: no LLM key connected" : null,
    },
    {
      title: "Webhook tunnel / public URL",
      done: !missingTunnel,
      href: "/webhooks",
      detail: missingTunnel
        ? "No deliveries yet — start cloudflared (or similar) and set the webhook URL on the GitHub App."
        : "Webhook deliveries have been received.",
      auto: missingTunnel ? "Detected: zero webhook deliveries" : null,
    },
    {
      title: "Sync & index repositories",
      done: (repos.data?.total ?? 0) > 0,
      href: "/repositories",
      detail: "Sync repos from the installation, then run an index job.",
      auto: null,
    },
    {
      title: "Complete a first review",
      done: (overview.data?.metrics.total_prs_reviewed ?? 0) > 0,
      href: "/pull-requests",
      detail: "Open a PR or trigger a review from the Pull Requests page.",
      auto: null,
    },
  ];

  const next = steps.find((s) => !s.done);

  return (
    <Shell
      title="First-run wizard"
      description="Auto-detects missing App credentials, LLM keys, and webhook tunnel."
      breadcrumb="System"
      actions={
        next ? (
          <Link href={next.href}>
            <Button size="sm">Continue: {next.title}</Button>
          </Link>
        ) : null
      }
    >
      {next ? (
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="p-4 text-[13px]">
            Next up: <span className="font-medium text-foreground">{next.title}</span>
            {next.auto ? (
              <span className="mt-1 block text-muted-foreground">{next.auto}</span>
            ) : null}
          </CardContent>
        </Card>
      ) : (
        <Card className="border-success/30 bg-success/5">
          <CardContent className="p-4 text-[13px] text-muted-foreground">
            Setup looks complete — Spider is ready for reviews.
          </CardContent>
        </Card>
      )}

      <div className="grid gap-3">
        {steps.map((step, i) => (
          <Card key={step.title}>
            <CardHeader className="flex flex-row items-center justify-between gap-3">
              <div>
                <p className="eyebrow">Step {i + 1}</p>
                <CardTitle>{step.title}</CardTitle>
                <p className="mt-1 text-[13px] text-muted-foreground">{step.detail}</p>
                {step.auto && !step.done ? (
                  <p className="mt-1 text-[12px] text-warning">{step.auto}</p>
                ) : null}
              </div>
              <Badge variant={step.done ? "success" : "muted"}>
                {step.done ? "done" : "todo"}
              </Badge>
            </CardHeader>
            <CardContent>
              <Link href={step.href}>
                <Button size="sm" variant={step.done ? "outline" : "default"}>
                  {step.done ? "Review" : "Continue"}
                </Button>
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>
    </Shell>
  );
}
