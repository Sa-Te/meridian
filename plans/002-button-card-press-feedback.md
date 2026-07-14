# 002 — Add press feedback to Button and interactive Card

- **Status**: DONE
- **Commit**: ccf3b91
- **Severity**: MEDIUM
- **Category**: Physicality & origin
- **Estimated scope**: 2 files, 1 line changed each

## Problem

`Button` and interactive `Card` are the two most-clicked elements in the
entire app — every chat submit, every transcript upload, every pagination
click, and every meeting/trace list-row navigation goes through one of them.
Neither gives any tactile confirmation of a click beyond the (already
correct) color hover transition; the click itself produces no visual
feedback before the resulting state change appears.

Current state, `apps/web/app/components/ui/Button.tsx:23-35`:

```tsx
  return (
    <button
      type={type}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50",
        "disabled:cursor-not-allowed disabled:opacity-50",
        variantClasses[variant],
        className,
      )}
      {...props}
    />
  );
```

Current state, `apps/web/app/components/ui/Card.tsx:16-27`:

```tsx
  return (
    <div
      className={cn(
        "rounded-2xl border border-border bg-surface-solid/70 p-4 shadow-[var(--shadow-glass)] backdrop-blur-md transition-colors",
        interactive && "cursor-pointer hover:border-accent/40 hover:bg-accent-soft",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
```

## Target

This plan depends on [plan 001](001-motion-tokens-foundation.md) having
already landed — it imports `PRESS_TRANSITION_CLASSES` and
`PRESS_ACTIVE_CLASSES` from `apps/web/app/lib/motion.ts`, and those classes
reference the `--ease-out`/`--duration-press` tokens in `globals.css`. If
`apps/web/app/lib/motion.ts` does not exist yet, stop and apply plan 001
first.

`Button.tsx` target:

```tsx
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/app/lib/cn";
import { PRESS_ACTIVE_CLASSES, PRESS_TRANSITION_CLASSES } from "@/app/lib/motion";

// ...

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
```

`Card.tsx` target — only the `interactive` branch gets press feedback (a
non-interactive Card, e.g. an already-expanded citation, is not clickable and
must not scale on press):

```tsx
import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/app/lib/cn";
import { PRESS_ACTIVE_CLASSES, PRESS_TRANSITION_CLASSES } from "@/app/lib/motion";

// ...

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
```

Note the base `transition-colors` utility is replaced with
`PRESS_TRANSITION_CLASSES` (a bare `transition` utility plus the shared
duration/easing) on both components, not layered alongside it.

## Repo conventions to follow

- Both components already compose Tailwind utility strings through the local
  `cn()` helper (`apps/web/app/lib/cn.ts`) — keep using it, do not introduce a
  new class-merging approach. `cn()` drops falsy values, so nesting a
  `cn(...)` call as one of the arguments to an outer `cn(...)` call (as done
  for Card's `interactive` branch above) works correctly: the inner call
  returns a plain string, or `interactive && cn(...)` short-circuits to
  `false`, which the outer `cn()` filters out exactly as the current
  `interactive && "..."` string does today.
- `PRESS_TRANSITION_CLASSES`/`PRESS_ACTIVE_CLASSES` come from
  `apps/web/app/lib/motion.ts` (added in plan 001) specifically so this exact
  press-feedback recipe is defined once, not re-typed per component.
  `PRESS_TRANSITION_CLASSES` compiles to Tailwind's bare `transition`
  utility (verified against this repo's installed Tailwind v4.3.2): an
  explicit, curated `transition-property` list that already includes
  `color, background-color, border-color, ..., transform, scale, ...` — it is
  **not** `transition: all` and does not include layout-triggering properties
  like `width`/`height`/`margin`. This is what lets the existing hover-color
  fade and the new `active:scale-97` press feedback share one
  `transition-property` list, one duration, and one easing curve without two
  separate transition utilities fighting over which one wins in the
  generated stylesheet.
- `PRESS_ACTIVE_CLASSES` sets `--tw-scale-x`/`--tw-scale-y: 97%` under
  Tailwind's `:active` pseudo-class variant — the `scale(0.97)` press value
  specified for UI press feedback (kept within the 0.95-0.98 subtle range,
  not `scale(0)`) — and cancels it under
  `@media (prefers-reduced-motion: reduce)`, while the existing color-hover
  feedback (unaffected by that media query) still communicates the click.

## Steps

1. In `apps/web/app/components/ui/Button.tsx`, add the import
   `import { PRESS_ACTIVE_CLASSES, PRESS_TRANSITION_CLASSES } from "@/app/lib/motion";`
   below the existing `import { cn } from "@/app/lib/cn";` line, then replace
   the `className={cn(...)}` call (lines 26-32) with the target block shown
   above.
2. In `apps/web/app/components/ui/Card.tsx`, add the same import below its
   existing `cn` import, then replace the `className={cn(...)}` call (lines
   18-22) with the target block shown above.
3. Save both files.

## Boundaries

- Do NOT add press feedback to `Card` when `interactive` is false.
- Do NOT touch `Nav.tsx`, `Input.tsx`, or `CitationChip.tsx` in this plan — the citation chip's own button/reveal gets its motion treatment in a separate plan.
- Do NOT change any prop, variant name, or non-motion class.
- Do NOT add new dependencies.
- If `Button.tsx` or `Card.tsx` has drifted from the "Current state" excerpts above, STOP and report instead of improvising the merge.

## Verification

- **Mechanical**: `cd apps/web && npm run typecheck && npm run lint && npm run test:ci && npm run build` — all must pass. `Button.test.tsx:38` and `Button.test.tsx:44` assert `toHaveClass("bg-accent")` / `toHaveClass("bg-surface-solid")`; `Card.test.tsx:15,18` assert `toHaveClass("cursor-pointer")` / `not.toHaveClass("cursor-pointer")` — none of these assertions touch the classes this plan changes, so they should continue passing unmodified. Do not edit either test file.
- **Feel check**: run `npm run dev`, open `/`, and:
  - Click and hold the "Ask" button — it should visibly shrink slightly (not disappear or jump) and spring back on release, feeling immediate rather than sluggish.
  - Click and hold a meeting card on `/meetings` (once a meeting is ingested) — same subtle press-down feel.
  - In Chrome DevTools' Rendering tab, enable "Emulate CSS media feature prefers-reduced-motion: reduce", then repeat both clicks — the press should no longer visibly scale, but the existing hover/border color change must still occur.
  - In DevTools' Animations panel, set playback speed to 10% and confirm the scale change eases out smoothly (fast start, gentle settle) rather than linearly.
- **Done when**: both files build and lint cleanly, the existing Button/Card test suites pass unmodified, and the feel-check above confirms visible, reduced-motion-aware press feedback on both components.
