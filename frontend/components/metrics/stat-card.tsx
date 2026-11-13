import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "default",
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon?: LucideIcon;
  tone?: "default" | "danger" | "warning" | "accent";
}) {
  const toneClass = {
    default: "text-foreground",
    danger: "text-destructive",
    warning: "text-warning",
    accent: "text-primary",
  }[tone];

  return (
    <Card className="overflow-hidden">
      <CardContent className="relative p-4 sm:p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="eyebrow">{label}</p>
            <p
              className={cn(
                "mt-2 text-[1.75rem] font-semibold leading-none tracking-tight tabular",
                toneClass,
              )}
            >
              {value}
            </p>
            {hint ? (
              <p className="mt-2 text-[11px] leading-snug text-muted-foreground">{hint}</p>
            ) : null}
          </div>
          {Icon ? (
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border bg-muted/70 text-muted-foreground">
              <Icon className="h-4 w-4" strokeWidth={1.75} />
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
