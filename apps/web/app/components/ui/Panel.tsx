import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/app/lib/cn";

type PanelProps = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode;
};

/** The page-level glass surface: a translucent, blurred, softly-shadowed
 * container. Use for major sections; Card is the smaller, per-item unit. */
export function Panel({ className, children, ...props }: PanelProps) {
  return (
    <div
      className={cn(
        "rounded-3xl border border-border bg-surface p-6 shadow-[var(--shadow-glass)] backdrop-blur-xl",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
