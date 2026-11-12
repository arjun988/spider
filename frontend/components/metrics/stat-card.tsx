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
    accent: "text-accent",
  }[tone];

  return (
    <Card>
      <CardContent className="flex items-start justify-between gap-3 p-4">
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className={cn("mt-1 text-2xl font-semibold tracking-tight", toneClass)}>
            {value}
          </p>
          {hint ? <p className="mt-1 text-[11px] text-muted-foreground">{hint}</p> : null}
        </div>
        {Icon ? (
          <div className="rounded-md border border-border bg-secondary/50 p-2 text-muted-foreground">
            <Icon className="h-4 w-4" />
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}