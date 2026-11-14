import type { ReactNode } from "react";
import { Sidebar } from "./sidebar";

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
  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 border-b border-border/70 bg-background/75 px-6 py-5 backdrop-blur-xl supports-[backdrop-filter]:bg-background/65">
          <div className="mx-auto flex w-full max-w-[1280px] items-start justify-between gap-6">
            <div className="min-w-0 space-y-1.5">
              {breadcrumb ? <p className="eyebrow">{breadcrumb}</p> : null}
              <h1 className="page-title">{title}</h1>
              {description ? (
                <p className="max-w-2xl text-[13px] leading-relaxed text-muted-foreground">
                  {description}
                </p>
              ) : null}
            </div>
            {actions ? (
              <div className="flex shrink-0 flex-wrap items-center justify-end gap-2 pt-1">
                {actions}
              </div>
            ) : null}
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1280px] flex-1 space-y-6 overflow-auto px-6 py-6">
          {children}
        </main>
      </div>
    </div>
  );
}
