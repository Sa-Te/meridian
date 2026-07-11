import type { InputHTMLAttributes } from "react";

import { cn } from "@/app/lib/cn";

type InputProps = InputHTMLAttributes<HTMLInputElement>;

export function Input({ className, ...props }: InputProps) {
  return (
    <input
      className={cn(
        "w-full rounded-full border border-border bg-surface-solid/80 px-4 py-2.5 text-sm text-foreground",
        "placeholder:text-muted-foreground shadow-[var(--shadow-glass-inset)] outline-none transition-colors",
        "focus:border-accent/50 focus:ring-2 focus:ring-accent/30",
        className,
      )}
      {...props}
    />
  );
}
