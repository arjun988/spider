import { cn } from "@/lib/utils";
import type { ButtonHTMLAttributes } from "react";

const variants = {
  default:
    "bg-primary text-primary-foreground shadow-sm hover:brightness-110 active:brightness-95",
  secondary:
    "border border-border bg-secondary text-secondary-foreground hover:bg-muted",
  outline:
    "border border-border bg-card/80 text-foreground hover:bg-muted/80",
  ghost:
    "text-muted-foreground hover:bg-muted hover:text-foreground",
  destructive:
    "bg-destructive text-destructive-foreground hover:brightness-110",
};

const sizes = {
  default: "h-9 gap-1.5 px-3.5 text-[13px]",
  sm: "h-8 gap-1.5 px-3 text-xs",
  lg: "h-10 gap-2 px-4 text-sm",
  icon: "h-9 w-9",
};

export function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof variants;
  size?: keyof typeof sizes;
}) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-lg font-medium tracking-tight transition-all duration-fast focus-visible:outline-none focus-visible:shadow-focus disabled:pointer-events-none disabled:opacity-45",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  );
}
