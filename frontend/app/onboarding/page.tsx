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

  const steps = [
    {
      title: "Install GitHub App",
      done: !!system.data?.github_app_configured,
      href: "/repositories",
      detail: "Configure the app and sync an organization.",
    },
    {
      title: "Configure LLM",
      done: !!llm.data?.configured || llm.data?.connection_status === "connected",
      href: "/settings",
      detail: "Add a Gemini or LiteLLM key and validate the connection.",
    },
    {
      title: "Sync & index repositories",
      done: (repos.data?.total ?? 0) > 0,
      href: "/repositories",
      detail: "Sync repos from the installation, then run an index job.",
    },
    {
      title: "Complete a first review",
      done: (overview.data?.metrics.total_prs_reviewed ?? 0) > 0,
      href: "/pull-requests",
      detail: "Open a PR or trigger a review from the Pull Requests page.",
    },
  ];

  return (
    <Shell
      title="Onboarding"
      description="Get Spider from install to first verified review."
      breadcrumb="System"
    >
      <div className="grid gap-3">
        {steps.map((step, i) => (
          <Card key={step.title}>
            <CardHeader className="flex flex-row items-center justify-between gap-3">
              <div>
                <p className="eyebrow">Step {i + 1}</p>
                <CardTitle>{step.title}</CardTitle>
                <p className="mt-1 text-[13px] text-muted-foreground">{step.detail}</p>
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
