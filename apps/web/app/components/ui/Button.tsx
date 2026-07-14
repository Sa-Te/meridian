import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/app/lib/cn";
import { PRESS_ACTIVE_CLASSES, PRESS_TRANSITION_CLASSES } from "@/app/lib/motion";

type ButtonVariant = "primary" | "secondary" | "ghost";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
};

const variantClasses: Record<ButtonVariant, string> = {
  primary: "bg-accent text-accent-foreground hover:bg-accent-strong",
  secondary: "border border-border bg-surface-solid text-foreground hover:border-accent/40",
  ghost: "bg-transparent text-muted-foreground hover:text-foreground",
};

export function Button({
  variant = "primary",
  className,
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium",
        PRESS_TRANSITION_CLASSES,
        PRESS_ACTIVE_CLASSES,
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50",
        "disabled:cursor-not-allowed disabled:opacity-50",
        variantClasses[variant],
        className,
      )}
      {...props}
    />
  );
}
