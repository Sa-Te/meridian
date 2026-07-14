# 003 — Animate the citation chip's expand reveal

- **Status**: DONE
- **Commit**: ccf3b91
- **Severity**: MEDIUM
- **Category**: Physicality & origin / Missed opportunity
- **Estimated scope**: 1 file, 2 lines changed

## Problem

`CitationChip` is a trigger-anchored disclosure — clicking the chip reveals a
`Card` with the full source excerpt directly beneath it — used in every chat
answer and every meeting-timeline entry, across two pages. Today the reveal
is a hard conditional render with no motion at all: the `Card` simply appears
and disappears, teleporting into existence with no visual connection to the
button that triggered it.

Current state, `apps/web/app/components/citations/CitationChip.tsx:21-46`:

```tsx
  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded((previous) => !previous)}
        aria-expanded={expanded}
        className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent-strong transition-colors hover:bg-accent/20"
      >
        <span>{citation.speaker}</span>
        <span aria-hidden="true">&middot;</span>
        <span>{formatTimestamp(citation.start_ts)}</span>
      </button>

      {expanded && (
        <Card className="mt-2 max-w-md text-sm">
          <p className="font-medium text-foreground">
            {citation.speaker}{" "}
            <span className="font-normal text-muted-foreground">
              &middot; {formatTimestamp(citation.start_ts)}
            </span>
          </p>
          <p className="mt-1 text-muted-foreground">{citation.text}</p>
        </Card>
      )}
    </div>
  );
```

`apps/web/app/components/citations/CitationChip.test.tsx:23` asserts
`expect(screen.queryByText(citation.text)).not.toBeInTheDocument();` when
collapsed — the collapsed state must genuinely remove the excerpt from the
DOM, not just hide it visually. This rules out an always-rendered
height-animation approach (e.g. a `grid-template-rows` trick): that would
leave the citation text permanently in the DOM (just visually collapsed),
which breaks that assertion. Keep the `{expanded && ...}` conditional render
exactly as-is, and animate only the **entrance** using a CSS `@starting-style`
transition, which fires automatically when a new element mounts and needs no
extra "is this the first render" state in React. This means collapsing stays
instant (no exit animation) — that is an intentional trade-off to avoid
touching the test file or adding unmount-delay logic for a MEDIUM-priority
polish fix.

## Target

This plan depends on [plan 001](001-motion-tokens-foundation.md) having
already landed — it imports `ENTER_TRANSITION_CLASSES` from
`apps/web/app/lib/motion.ts`. If that file does not exist yet, stop and apply
plan 001 first.

```tsx
import { cn } from "@/app/lib/cn";
import { ENTER_TRANSITION_CLASSES } from "@/app/lib/motion";

// ...

      {expanded && (
        <Card className={cn("mt-2 max-w-md text-sm", ENTER_TRANSITION_CLASSES)}>
          <p className="font-medium text-foreground">
            {citation.speaker}{" "}
            <span className="font-normal text-muted-foreground">
              &middot; {formatTimestamp(citation.start_ts)}
            </span>
          </p>
          <p className="mt-1 text-muted-foreground">{citation.text}</p>
        </Card>
      )}
```

This file does not currently import `cn` (its `Card`'s `className` is
currently a bare string literal) — add that import too.

## Repo conventions to follow

- Every other component with more than one conditional class already
  composes them with the shared `cn()` helper from `apps/web/app/lib/cn.ts`
  (e.g. `Card.tsx:18`, `Badge.tsx:25`) — follow the same import and call
  pattern here rather than a template literal.
- `ENTER_TRANSITION_CLASSES` comes from `apps/web/app/lib/motion.ts` (added
  in plan 001) so this exact fade-and-rise entrance recipe is defined once
  and reused everywhere an element mounts and should ease in, rather than
  re-typed per component. It compiles to an `@starting-style` block
  (verified against this repo's installed Tailwind v4.3.2) — Tailwind's
  native syntax for "the style this element had the instant it was inserted
  into the DOM," letting the browser transition from that starting style to
  the element's normal style with no `useEffect` or `data-mounted` attribute
  needed. The rise resolves to Tailwind's `--spacing` unit (4px by default in
  this project) — a small, subtle rise, not a large slide. The reduced-motion
  variant baked into the constant cancels only the vertical offset, per this
  audit's rule that reduced motion should keep opacity feedback and drop
  position changes, not remove all feedback.

## Steps

1. In `apps/web/app/components/citations/CitationChip.tsx`, add the imports:
   ```tsx
   import { cn } from "@/app/lib/cn";
   import { ENTER_TRANSITION_CLASSES } from "@/app/lib/motion";
   ```
   next to the existing `Card` import (after line 4, in the same import
   block, following this repo's `@/app/...` absolute-import convention).
2. Replace the `<Card className="mt-2 max-w-md text-sm">` opening tag (line
   35) with `<Card className={cn("mt-2 max-w-md text-sm", ENTER_TRANSITION_CLASSES)}>`.
3. Save.

## Boundaries

- Do NOT change the `{expanded && ...}` conditional — keep collapse
  instantaneous and DOM-removing.
- Do NOT modify `CitationChip.test.tsx`.
- Do NOT add exit-animation logic (delayed unmount, `AnimatePresence`-style
  state machines, etc.) — out of scope for this plan.
- Do NOT touch the trigger `<button>`'s classes — its press feedback is
  covered by a separate finding, not this plan.
- If the file has drifted from the "Current state" excerpt above, STOP and
  report instead of improvising the merge.

## Verification

- **Mechanical**: `cd apps/web && npm run typecheck && npm run lint && npm run test:ci && npm run build` — all must pass. `CitationChip.test.tsx` must pass unmodified, including the `not.toBeInTheDocument()` assertion on the collapsed state.
- **Feel check**: run `npm run dev`, open `/`, ask a question that returns a citation, and:
  - Click the citation chip — the excerpt card should fade and rise gently into place beneath the chip, not pop in instantly.
  - Click it again to collapse — the card should disappear instantly (this is expected and correct per this plan's scope).
  - In DevTools' Animations panel, set playback to 10% on the next expand and confirm the motion eases out (fast start, gentle settle) rather than linearly, and that it never overshoots past its final position.
  - Toggle `prefers-reduced-motion: reduce` in DevTools' Rendering panel, expand again, and confirm the card still fades in (opacity) but no longer visibly rises.
- **Done when**: the file builds and lints cleanly, the existing test suite passes unmodified, and the feel-check above confirms a gentle fade+rise entrance gated correctly by reduced motion.
