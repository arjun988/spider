import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

const variants: Record<string, string> = {
  default: "border-border bg-secondary text-secondary-foreground",
  success: "border-success/25 bg-success/10 text-success",
  warning: "border-warning/30 bg-warning/10 text-warning",
  destructive: "border-destructive/25 bg-destructive/10 text-destructive",
  muted: "border-border bg-muted text-muted-foreground",
  accent: "border-primary/25 bg-primary/10 text-primary",
};

export function Badge({
  className,
  variant = "default",
  ...props
}: HTMLAttributes<HTMLSpanElement> & { variant?: keyof typeof variants }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-[0.1em]",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
