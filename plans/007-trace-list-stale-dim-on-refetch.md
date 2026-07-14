# 007 — Dim the trace list while a filter/pagination refetch is in flight

- **Status**: DONE
- **Commit**: ccf3b91
- **Severity**: LOW
- **Category**: Missed opportunity (state change)
- **Estimated scope**: 1 file, 1 line changed

## Problem

`TracesListView` refetches over the network every time `endpoint`, `outcome`,
`date`, or `offset` changes (`apps/web/app/components/traces/TracesListView.tsx:26-62`)
— i.e. on every filter change and every Previous/Next click, which for
someone triaging traces is a "tens of times a day" interaction. During that
refetch, `loading` becomes `true`, but the previously-fetched `traces` array
is never cleared — it stays fully opaque and rendered exactly as before,
with no visual indication that it is stale, until the new page of results
replaces it outright with no transition. The user gets no feedback that
their click registered until the new data suddenly appears.

Current state, `apps/web/app/components/traces/TracesListView.tsx:93-103`:

```tsx
      {loading && <p className="text-sm text-muted-foreground">Loading traces...</p>}
      {error && <p className="text-sm text-danger">{error}</p>}
      {!loading && !error && traces.length === 0 && (
        <p className="text-sm text-muted-foreground">No traces match the selected filters.</p>
      )}

      <div className="flex flex-col gap-3">
        {traces.map((trace) => (
          <TraceListRow key={trace.id} trace={trace} />
        ))}
      </div>
```

## Target

This plan depends on [plan 001](001-motion-tokens-foundation.md) having
already landed (`--ease-out` and `--duration-base` must exist in
`globals.css`'s `:root` block). If they are not present, stop and apply plan
001 first. This plan does **not** depend on
[plan 006](006-list-entrance-stagger.md) — see "Boundaries" below for how to
apply this change whether or not plan 006 has already landed.

Only the results container's opening tag changes — dim it to 40% opacity
while `loading` is true, using the already-existing `loading` boolean (no
new state):

```tsx
      <div
        className={cn(
          "flex flex-col gap-3 transition-opacity duration-[var(--duration-base)] ease-[var(--ease-out)]",
          loading && "opacity-40",
        )}
      >
        {traces.map((trace) => (
          <TraceListRow key={trace.id} trace={trace} />
        ))}
      </div>
```

This file does not currently import `cn` — add that import.

## Repo conventions to follow

- Other components already compose a conditional class alongside a static
  base string through the shared `cn()` helper (`apps/web/app/lib/cn.ts`),
  e.g. `Card.tsx:18-20`, `Nav.tsx:26-31` — follow the same pattern here.
- This is a plain opacity fade (no transform/position change), so per this
  audit's accessibility rule it should NOT be gated behind
  `motion-reduce:` — reduced motion means dropping movement while keeping
  opacity/color feedback, and this change is entirely opacity-based.
- Uses the same `--duration-base`/`--ease-out` tokens from plan 001 that
  every other plan in this set uses, via the same
  `duration-[var(--duration-base)] ease-[var(--ease-out)]` arbitrary-value
  form already verified against this repo's installed Tailwind v4.3.2.

## Steps

1. In `apps/web/app/components/traces/TracesListView.tsx`, add
   `import { cn } from "@/app/lib/cn";` to the import block.
2. Replace the opening `<div className="flex flex-col gap-3">` tag
   (currently line 99) with the target block shown above. Leave everything
   inside the `<div>...</div>` — the `.map()` call and its contents —
   completely untouched.
3. Save.

## Boundaries

- Do NOT clear or mutate the `traces` array while loading — the fix is
  purely visual (dimming what's already rendered), not a data change.
- Do NOT touch the `{loading && <p>...}` / `{error && <p>...}` / empty-state
  lines (93-96) — those are separate, already-adequate pieces of feedback.
- Do NOT touch the pagination `Button`s or the `Previous`/`Next` logic
  (lines 105-127).
- Do NOT modify `TracesListView.test.tsx`.
- This plan's target touches only the results container's opening tag. If
  [plan 006](006-list-entrance-stagger.md) has already landed, the `.map()`
  body inside that container will look different (each `<TraceListRow>`
  wrapped in its own `<div>` carrying `LIST_ENTER_CLASSES` and
  `staggerDelayStyle(index)`) — that is expected and correct; apply this
  plan's `cn(...)` change to the outer div's opening tag exactly as shown,
  and leave the (possibly already-modified) `.map()` body inside it alone.
- If the outer `<div className="flex flex-col gap-3">` line has drifted in
  some other way (not explained by plan 006 having landed), STOP and report
  instead of improvising the merge.

## Verification

- **Mechanical**: `cd apps/web && npm run typecheck && npm run lint && npm run test:ci && npm run build` — all must pass. `TracesListView.test.tsx` asserts on rendered text, button states, and the arguments `listTraces` was called with — never on `className` — so it should pass unmodified.
- **Feel check**: run `npm run dev`, open `/traces` with more traces than fit on one page, and:
  - Click "Next" — the current page of rows should visibly dim for the duration of the request, then snap back to full opacity as the new page renders, rather than the old rows staying fully bright until an instant swap.
  - Change the endpoint or outcome filter and confirm the same dim-then-restore behavior.
  - In DevTools' Animations panel, confirm the opacity change eases rather than jumping.
  - Toggle `prefers-reduced-motion: reduce` in DevTools' Rendering panel and confirm the dim-on-refetch behavior is unchanged (this is intentional — it is an opacity cue, not a movement, so it should not be suppressed).
- **Done when**: the file builds and lints cleanly, the existing test suite passes unmodified, and the feel-check above confirms the trace list visibly dims during a background refetch instead of silently going stale.
