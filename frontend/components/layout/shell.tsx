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
        <header className="sticky top-0 z-20 border-b border-border/80 bg-background/80 px-6 py-4 backdrop-blur-md">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 space-y-1">
              {breadcrumb ? <p className="eyebrow">{breadcrumb}</p> : null}
              <h1 className="text-[1.35rem] font-semibold tracking-tight text-foreground">
                {title}
              </h1>
              {description ? (
                <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
                  {description}
                </p>
              ) : null}
            </div>
            {actions ? (
              <div className="flex shrink-0 flex-wrap items-center justify-end gap-2 pt-0.5">
                {actions}
              </div>
            ) : null}
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1400px] flex-1 space-y-5 overflow-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
