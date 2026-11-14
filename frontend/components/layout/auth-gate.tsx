"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

const PUBLIC_PATHS = ["/login", "/auth/callback"];

export function AuthGate({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  const system = useQuery({
    queryKey: ["system"],
    queryFn: api.systemStatus,
    retry: false,
    staleTime: 60_000,
  });

  const me = useQuery({
    queryKey: ["me"],
    queryFn: api.me,
    retry: false,
    enabled: !!getAccessToken() || system.data?.auth_required === false,
  });

  const isPublic = PUBLIC_PATHS.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  );
  const authRequired = system.data?.auth_required === true;
  const hasToken = typeof window !== "undefined" && !!getAccessToken();
  const signedIn = !!me.data && !me.isError;

  useEffect(() => {
    if (system.isLoading) return;
    if (isPublic) {
      setReady(true);
      return;
    }
    if (!authRequired) {
      setReady(true);
      return;
    }
    if (!hasToken) {
      router.replace(`/login?next=${encodeURIComponent(pathname || "/")}`);
      return;
    }
    if (me.isLoading) return;
    if (me.isError || !signedIn) {
      router.replace(`/login?next=${encodeURIComponent(pathname || "/")}`);
      return;
    }
    setReady(true);
  }, [
    system.isLoading,
    system.data,
    authRequired,
    isPublic,
    hasToken,
    me.isLoading,
    me.isError,
    signedIn,
    pathname,
    router,
  ]);

  if (isPublic) return <>{children}</>;
  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-[13px] text-muted-foreground">
        Checking session…
      </div>
    );
  }
  return <>{children}</>;
}
