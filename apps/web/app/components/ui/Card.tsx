import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/app/lib/cn";
import { PRESS_ACTIVE_CLASSES, PRESS_TRANSITION_CLASSES } from "@/app/lib/motion";

type CardProps = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode;
  /** Adds a hover affordance for a clickable/expandable card (a citation
   * chip, a trace row) without deciding what the click does. */
  interactive?: boolean;
};

/** The compact, per-item glass surface: one decision, one action item, one
 * trace row. Panel is for page-level sections; Card is for the items
 * inside them. */
export function Card({ className, children, interactive = false, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-border bg-surface-solid/70 p-4 shadow-[var(--shadow-glass)] backdrop-blur-md",
        PRESS_TRANSITION_CLASSES,
        interactive && cn("cursor-pointer hover:border-accent/40 hover:bg-accent-soft", PRESS_ACTIVE_CLASSES),
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
