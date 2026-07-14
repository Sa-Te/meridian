# 005 — Fade in the ingest upload's status block

- **Status**: DONE
- **Commit**: ccf3b91
- **Severity**: LOW-MEDIUM
- **Category**: Missed opportunity (state change)
- **Estimated scope**: 1 file, 3 similar edits

## Problem

`MeetingIngestUpload` walks through `idle -> uploading -> success | error`,
and each of the three non-idle states teleports into view with no
transition — the same class of issue as [plan 004](004-chat-result-panels-enter-transition.md),
on the other primary write-path screen in the app (`/meetings`).

Current state, `apps/web/app/components/meetings/MeetingIngestUpload.tsx:87-106`:

```tsx
      {status === "uploading" && fileName && (
        <p className="mt-4 text-sm text-muted-foreground">Uploading {fileName}...</p>
      )}

      {status === "success" && result && (
        <div className="mt-4 flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="accent">Ingested</Badge>
            {result.flagged_for_prompt_injection && (
              <Badge tone="danger">Flagged for review</Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground">
            {result.chunk_count} chunks &middot; {result.decision_count} decisions &middot;{" "}
            {result.action_item_count} action items.
          </p>
        </div>
      )}

      {status === "error" && error && <p className="mt-4 text-sm text-danger">{error}</p>}
```

## Target

This plan depends on [plan 001](001-motion-tokens-foundation.md) having
already landed — it imports `ENTER_TRANSITION_CLASSES` from
`apps/web/app/lib/motion.ts`. If that file does not exist yet, stop and apply
plan 001 first.

```tsx
import { cn } from "@/app/lib/cn";
import { ENTER_TRANSITION_CLASSES } from "@/app/lib/motion";

// ...

      {status === "uploading" && fileName && (
        <p className={cn("mt-4 text-sm text-muted-foreground", ENTER_TRANSITION_CLASSES)}>
          Uploading {fileName}...
        </p>
      )}

      {status === "success" && result && (
        <div className={cn("mt-4 flex flex-col gap-2", ENTER_TRANSITION_CLASSES)}>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="accent">Ingested</Badge>
            {result.flagged_for_prompt_injection && (
              <Badge tone="danger">Flagged for review</Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground">
            {result.chunk_count} chunks &middot; {result.decision_count} decisions &middot;{" "}
            {result.action_item_count} action items.
          </p>
        </div>
      )}

      {status === "error" && error && (
        <p className={cn("mt-4 text-sm text-danger", ENTER_TRANSITION_CLASSES)}>{error}</p>
      )}
```

This file does not currently import `cn` (its status blocks use bare string
literal `className`s) — add that import too.

## Repo conventions to follow

- Other components in this codebase already compose more-than-one class
  source through the shared `cn()` helper (`apps/web/app/lib/cn.ts`), e.g.
  `Card.tsx:18`, `Badge.tsx:25` — use the same pattern here rather than a
  template literal, now that each of these three elements combines a static
  base string with the shared `ENTER_TRANSITION_CLASSES` constant.
- `ENTER_TRANSITION_CLASSES` comes from `apps/web/app/lib/motion.ts` (added
  in plan 001) — the same fade-and-rise `@starting-style` entrance recipe
  used identically in [plan 003](003-citation-chip-expand-motion.md) and
  [plan 004](004-chat-result-panels-enter-transition.md), verified to compile
  against this repo's installed Tailwind v4.3.2.

## Steps

1. In `apps/web/app/components/meetings/MeetingIngestUpload.tsx`, add the
   imports:
   ```tsx
   import { cn } from "@/app/lib/cn";
   import { ENTER_TRANSITION_CLASSES } from "@/app/lib/motion";
   ```
   to the top of the import block.
2. Replace the three conditional blocks at lines 87-89, 91-104, and 106 with
   the target versions shown above — only the outermost element's
   `className` changes in each case; no inner markup changes.
3. Save.

## Boundaries

- Do NOT touch the always-mounted `Panel` wrapper (line 59) or the upload
  button/input (lines 69-84) — those are covered by
  [plan 002](002-button-card-press-feedback.md) for press feedback, not this
  plan.
- Do NOT modify `MeetingIngestUpload.test.tsx`.
- Do NOT change the `status` state machine or any conditional logic.
- If the three blocks have drifted from the "Current state" excerpt above,
  STOP and report instead of improvising the merge.

## Verification

- **Mechanical**: `cd apps/web && npm run typecheck && npm run lint && npm run test:ci && npm run build` — all must pass. `MeetingIngestUpload.test.tsx` asserts on text content and `Badge` labels only, never on `className`, so it should pass unmodified.
- **Feel check**: run `npm run dev`, open `/meetings`, upload a `.txt` transcript, and confirm:
  - The "Uploading <filename>..." line fades and rises in rather than popping in.
  - Once ingestion completes, the "Ingested" success block fades/rises in.
  - Uploading a non-`.txt` file produces the error line with the same gentle entrance.
  - In DevTools' Animations panel at 10% playback, the motion eases out smoothly.
  - Toggling `prefers-reduced-motion: reduce` in DevTools' Rendering panel keeps the opacity fade but removes the rise.
- **Done when**: the file builds and lints cleanly, the existing test suite passes unmodified, and all three status states visibly ease in rather than teleporting.
