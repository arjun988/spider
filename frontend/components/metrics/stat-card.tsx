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
    <Card className="overflow-hidden transition-colors duration-fast hover:border-primary/25">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-2.5">
            <p className="eyebrow">{label}</p>
            <p
              className={cn(
                "text-[1.875rem] font-semibold leading-none tracking-tighter tabular",
                toneClass,
              )}
            >
              {value}
            </p>
            {hint ? (
              <p className="text-[12px] leading-snug text-muted-foreground">{hint}</p>
            ) : null}
          </div>
          {Icon ? (
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-muted/60 text-muted-foreground">
              <Icon className="h-4 w-4" strokeWidth={1.6} />
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
