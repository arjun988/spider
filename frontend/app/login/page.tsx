"use client";

import { Bug } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

export default function LoginPage() {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function startGithub() {
    setLoading(true);
    setError(null);
    try {
      const { authorize_url } = await api.githubLoginUrl();
      window.location.href = authorize_url;
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "GitHub OAuth is not configured. In development the dashboard works without login.",
      );
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md space-y-6 rounded-2xl border border-border bg-card p-8 shadow-panel">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Bug className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Sign in to Spider</h1>
            <p className="text-[13px] text-muted-foreground">GitHub OAuth SSO</p>
          </div>
        </div>
        <p className="text-[13px] leading-relaxed text-muted-foreground">
          Staging and production require GitHub SSO. Local development can bypass auth only when
          AUTH_DISABLED_IN_DEV is enabled.
        </p>
        <Button className="w-full" onClick={startGithub} disabled={loading}>
          {loading ? "Redirecting…" : "Continue with GitHub"}
        </Button>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
      </div>
    </div>
  );
}
