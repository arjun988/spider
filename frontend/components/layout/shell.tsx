"use client";

import type { ReactNode } from "react";
import { useState } from "react";
import { Menu, X } from "lucide-react";
import { Sidebar } from "./sidebar";
import { Button } from "@/components/ui/button";

export function Shell({
  children,
  title,
  description,
  actions,
  breadcrumb,
}: {
  children: ReactNode;
  title: string;
  description?: string;
  actions?: ReactNode;
  breadcrumb?: string;
}) {
  const [navOpen, setNavOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-background">
      {/* Desktop sidebar */}
      <div className="hidden md:flex">
        <Sidebar />
      </div>

      {/* Mobile drawer */}
      {navOpen ? (
        <div className="fixed inset-0 z-40 md:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/50"
            aria-label="Close navigation"
            onClick={() => setNavOpen(false)}
          />
          <div className="relative z-50 h-full w-[268px] shadow-xl">
            <Sidebar onNavigate={() => setNavOpen(false)} />
          </div>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 border-b border-border/70 bg-background/75 px-4 py-4 backdrop-blur-xl supports-[backdrop-filter]:bg-background/65 sm:px-6 sm:py-5">
          <div className="mx-auto flex w-full max-w-[1280px] items-start justify-between gap-4 sm:gap-6">
            <div className="flex min-w-0 items-start gap-3">
              <Button
                variant="outline"
                size="sm"
                className="mt-0.5 shrink-0 md:hidden"
                onClick={() => setNavOpen(true)}
                aria-label="Open navigation"
              >
                {navOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
              </Button>
              <div className="min-w-0 space-y-1.5">
                {breadcrumb ? <p className="eyebrow">{breadcrumb}</p> : null}
                <h1 className="page-title text-[1.35rem] sm:text-[1.6rem]">{title}</h1>
                {description ? (
                  <p className="max-w-2xl text-[13px] leading-relaxed text-muted-foreground">
                    {description}
                  </p>
                ) : null}
              </div>
            </div>
            {actions ? (
              <div className="flex shrink-0 flex-wrap items-center justify-end gap-2 pt-1">
                {actions}
              </div>
            ) : null}
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1280px] flex-1 space-y-6 overflow-auto px-4 py-5 sm:px-6 sm:py-6">
          {children}
        </main>
      </div>
    </div>
  );
}
