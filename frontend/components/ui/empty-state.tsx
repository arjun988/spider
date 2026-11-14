import Link from "next/link";
import { Button } from "@/components/ui/button";

export function EmptyState({
  title,
  description,
  actionHref,
  actionLabel,
}: {
  title: string;
  description: string;
  actionHref?: string;
  actionLabel?: string;
}) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-xl border border-dashed border-border bg-muted/20 px-5 py-8">
      <div>
        <p className="text-[14px] font-semibold tracking-tight text-foreground">{title}</p>
        <p className="mt-1 max-w-xl text-[13px] text-muted-foreground">{description}</p>
      </div>
      {actionHref && actionLabel ? (
        <Link href={actionHref}>
          <Button size="sm">{actionLabel}</Button>
        </Link>
      ) : null}
    </div>
  );
}

export function ConfigBanner({
  message,
  href = "/settings",
}: {
  message: string;
  href?: string;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-[13px]">
      <p className="text-foreground">{message}</p>
      <Link href={href} className="font-medium text-primary hover:underline">
        Fix in Settings
      </Link>
    </div>
  );
}
