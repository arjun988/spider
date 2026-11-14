"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { setAccessToken, setOrgId } from "@/lib/auth";
import { api } from "@/lib/api";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function finish() {
      try {
        const hash = typeof window !== "undefined" ? window.location.hash.replace(/^#/, "") : "";
        const params = new URLSearchParams(hash);
        const token = params.get("access_token");
        if (!token) {
          setError("Missing access token in callback.");
          return;
        }
        setAccessToken(token);
        const me = await api.me();
        if (me.organization_id) setOrgId(me.organization_id);
        else if (me.organizations?.[0]?.id) setOrgId(me.organizations[0].id);
        router.replace("/");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Login failed");
      }
    }
    finish();
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
      {error || "Completing sign-in…"}
    </div>
  );
}
