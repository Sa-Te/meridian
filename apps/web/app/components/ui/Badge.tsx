import type { HTMLAttributes } from "react";

import { cn } from "@/app/lib/cn";

type BadgeTone = "neutral" | "accent" | "danger";

type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  tone?: BadgeTone;
};

const toneClasses: Record<BadgeTone, string> = {
  neutral: "bg-border/70 text-muted-foreground",
  accent: "bg-accent-soft text-accent-strong",
  // The one deliberate exception to "one accent colour" -- see
  // docs/adr/0014: a genuine error state (a failed trace, a declined
  // answer) needs to be distinguishable from a neutral or successful one,
  // which a single accent colour can't do on its own. Muted, low-chroma,
  // not a bright alert red -- still reads as restrained, not neon.
  danger: "bg-danger-soft text-danger",
};

export function Badge({ tone = "neutral", className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium tracking-wide",
        toneClasses[tone],
        className,
      )}
      {...props}
    />
  );
}
