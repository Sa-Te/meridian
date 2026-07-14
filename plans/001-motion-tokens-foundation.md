# 001 — Motion design tokens: CSS variables and a shared JS constants module

- **Status**: DONE
- **Commit**: ccf3b91
- **Severity**: MEDIUM
- **Category**: Cohesion & tokens
- **Estimated scope**: 2 files (1 edited, 1 new), ~30 lines added total

## Problem

`apps/web/app/globals.css` defines all of the app's design tokens (colors,
shadows) as CSS custom properties in `:root`, but no motion tokens exist at
all. The only motion currently in the app is five bare `transition-colors`
utility classes (`Nav.tsx:27`, `CitationChip.tsx:27`, `Button.tsx:27`,
`Card.tsx:19`, `Input.tsx:12`), none of which specify an explicit duration or
easing class — they all silently ride Tailwind's built-in defaults.

Plans 002 through 006 each add a deliberate transition (press feedback,
enter animations) to a different component, and every one of them needs the
same easing curve, the same duration values, and — because the class strings
themselves are identical or near-identical across files (an entrance fade
recipe reused in a chat panel, an upload status block, a citation reveal,
and four separate list views) — the same JS-level string constants. Landing
only the CSS tokens and letting each of plans 002-006 hand-roll its own copy
of e.g. `"transition-[opacity,transform] duration-[var(--duration-base)]
ease-[var(--ease-out)] starting:opacity-0 starting:translate-y-1
motion-reduce:starting:translate-y-0"` would recreate, in JS, the exact
"five hand-typed cubic-beziers that almost match" anti-pattern this audit
category exists to prevent — just one layer up from CSS. This plan
establishes both the CSS tokens and the one shared JS module every later
plan imports from.

Current state, `apps/web/app/globals.css:6-28`:

```css
:root {
  --background-start: #eef2f2;
  --background-end: #e6edec;
  --foreground: #1b2426;
  --muted-foreground: #5b6c6e;

  --surface: rgba(255, 255, 255, 0.6);
  --surface-solid: #f8fafa;
  --border-color: rgba(27, 36, 38, 0.09);

  --accent: #2f6f6a;
  --accent-strong: #245854;
  --accent-foreground: #f3faf9;
  --accent-soft: rgba(47, 111, 106, 0.1);

  --danger: #9a4a3f;
  --danger-soft: rgba(154, 74, 63, 0.1);

  --shadow-glass:
    0 1px 1px rgba(20, 30, 32, 0.04),
    0 8px 20px rgba(20, 30, 32, 0.07);
  --shadow-glass-inset: inset 0 1px 0 rgba(255, 255, 255, 0.5);
}
```

There is no `apps/web/app/lib/motion.ts` file yet.

## Target

### 1. `globals.css` — add three custom properties

Add exactly these three lines to the existing `:root` block, directly after
`--shadow-glass-inset` (i.e. as the new last lines before the closing `}` on
line 28):

```css
  --shadow-glass:
    0 1px 1px rgba(20, 30, 32, 0.04),
    0 8px 20px rgba(20, 30, 32, 0.07);
  --shadow-glass-inset: inset 0 1px 0 rgba(255, 255, 255, 0.5);

  --ease-out: cubic-bezier(0.23, 1, 0.32, 1);
  --duration-press: 140ms;
  --duration-base: 200ms;
}
```

Do not add these to the `@media (prefers-color-scheme: dark)` override block
(`globals.css:30-54`) — durations and easing curves are not color values and
do not need a dark-mode variant.

Do not add `--ease-in-out`, `--ease-drawer`, or a separate `--duration-fast`.
Every plan in this set (002-006) uses one easing curve and one of two
durations; a single shared entrance duration (`--duration-base`) is used
everywhere an element fades in, rather than a near-duplicate 180ms/200ms
pair, so nothing in this app has two barely-different timings to reconcile
later. Add more tokens only when a future finding actually needs a
genuinely different curve or timing.

### 2. New file `apps/web/app/lib/motion.ts`

```ts
import type { CSSProperties } from "react";

/** A single mounting element fades and rises into place using the
 * `@starting-style` CSS transition -- no mount-tracking React state is
 * needed, since `@starting-style` fires automatically the instant an
 * element is inserted into the DOM. Reduced motion keeps the opacity
 * fade and drops the rise. */
export const ENTER_TRANSITION_CLASSES =
  "transition-[opacity,transform] duration-[var(--duration-base)] ease-[var(--ease-out)] starting:opacity-0 starting:translate-y-1 motion-reduce:starting:translate-y-0";

/** Same entrance recipe, plus a per-item transition-delay driven by the
 * `--stagger-delay` custom property set via staggerDelayStyle(). */
export const LIST_ENTER_CLASSES = `${ENTER_TRANSITION_CLASSES} delay-[var(--stagger-delay)] motion-reduce:delay-0`;

/** Press feedback: pair with PRESS_ACTIVE_CLASSES on the same element (or
 * on a conditionally-applied variant of it) to get a smooth, reduced-
 * motion-aware scale-down on :active. Split in two because Card only
 * applies the :active classes when it is the `interactive` variant, but
 * still needs the base transition unconditionally (it already carries the
 * pre-existing color-hover transition). */
export const PRESS_TRANSITION_CLASSES =
  "transition duration-[var(--duration-press)] ease-[var(--ease-out)]";
export const PRESS_ACTIVE_CLASSES = "active:scale-97 motion-reduce:active:scale-100";

const MAX_STAGGERED_ITEMS = 7;
const STAGGER_STEP_MS = 30;

/** Caps the stagger at the first 8 items (index 0-7) so a long list's
 * cumulative delay never makes the tail feel like it's blocking on the
 * animation before it can be interacted with. */
export function staggerDelayStyle(index: number): CSSProperties {
  const delayMs = Math.min(index, MAX_STAGGERED_ITEMS) * STAGGER_STEP_MS;
  return { "--stagger-delay": `${delayMs}ms` } as CSSProperties;
}
```

This has been verified to compile cleanly under this repo's TypeScript
setup (`tsc --noEmit --strict`) exactly as written.

## Repo conventions to follow

- `apps/web/app/lib/` already holds small, single-purpose helper modules —
  `cn.ts` (class-name joining), `format.ts` (display formatting) — each
  exporting plain functions/constants with no side effects. `motion.ts`
  follows the same shape and placement.
- Tokens are consumed via Tailwind's arbitrary-value syntax referencing the
  CSS variable directly, e.g. `Card.tsx:19` already does
  `shadow-[var(--shadow-glass)]`. This has been verified against the
  installed Tailwind v4.3.2 (`@tailwindcss/postcss`):
  `duration-[var(--duration-base)]` compiles to
  `transition-duration: var(--duration-base)`; `ease-[var(--ease-out)]`
  compiles to `transition-timing-function: var(--ease-out)`;
  `starting:opacity-0` compiles to an `@starting-style` block;
  `motion-reduce:starting:translate-y-0` and `motion-reduce:delay-0` compile
  to `@media (prefers-reduced-motion: reduce)` blocks, stacking correctly
  with `@starting-style` and `:active`. Do not register the new tokens as
  `@theme inline` entries (unlike `--color-*`) — the color tokens use
  `@theme inline` so Tailwind generates matching `bg-*`/`text-*` utility
  names; there is no equivalent auto-generation guarantee for arbitrary
  `--ease-*`/`--duration-*` names in this Tailwind version, so stick to the
  proven `[var(--token)]` arbitrary-value form used by `--shadow-glass`.

## Steps

1. Open `apps/web/app/globals.css`. Inside the existing `:root { ... }`
   block, immediately after the line
   `--shadow-glass-inset: inset 0 1px 0 rgba(255, 255, 255, 0.5);`
   (currently line 27) and before the block's closing `}` (currently line
   28), insert a blank line followed by:
   ```css
   --ease-out: cubic-bezier(0.23, 1, 0.32, 1);
   --duration-press: 140ms;
   --duration-base: 200ms;
   ```
2. Create `apps/web/app/lib/motion.ts` with exactly the contents shown in
   the Target section above.
3. Save both files.

## Boundaries

- Do NOT touch the `@theme inline` block, the `body` selector, the `*`
  selector, or the dark-mode `@media` block in `globals.css`.
- Do NOT touch any file other than `apps/web/app/globals.css` and the new
  `apps/web/app/lib/motion.ts`.
- Do NOT add `--ease-in-out`, `--ease-drawer`, `--duration-fast`, or any
  token/constant not listed above — plans 002-006 are written against
  exactly this set.
- If `globals.css`'s `:root` block has drifted from the "Current state"
  excerpt above (e.g. tokens were renamed or reordered), STOP and report
  instead of guessing where to insert the new lines.

## Verification

- **Mechanical**: `cd apps/web && npm run typecheck && npm run lint && npm run test:ci && npm run build` — all four must succeed with no new errors or warnings. This change adds no component logic and is not yet imported anywhere, so the full test suite should pass unchanged.
- **Feel check**: not applicable — this plan adds no visible motion by itself. Confirm only that `npm run dev`, opening any page, and inspecting `:root` in DevTools' Computed/Styles panel shows `--ease-out`, `--duration-press`, and `--duration-base` resolved to the exact values above.
- **Done when**: the three new custom properties are present in `:root`, `apps/web/app/lib/motion.ts` exists with exactly the exports shown above, `npm run build` succeeds, and no other file has changed.
