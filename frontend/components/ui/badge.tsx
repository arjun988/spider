import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

const variants: Record<string, string> = {
  default: "bg-secondary text-secondary-foreground",
  success: "bg-success/15 text-success border-success/30",
  warning: "bg-warning/15 text-warning border-warning/30",
  destructive: "bg-destructive/15 text-destructive border-destructive/30",
  muted: "bg-muted text-muted-foreground",
  accent: "bg-accent/15 text-accent border-accent/30",
};

export function Badge({
  className,
  variant = "default",
  ...props
}: HTMLAttributes<HTMLSpanElement> & { variant?: keyof typeof variants }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-wide",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}