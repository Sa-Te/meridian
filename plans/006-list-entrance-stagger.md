# 006 — Fade and stagger list items in on first load

- **Status**: DONE
- **Commit**: ccf3b91
- **Severity**: LOW
- **Category**: Missed opportunity / Cohesion
- **Estimated scope**: 4 files, 1 similar edit each

## Problem

Four list views render their items fully-formed the instant data arrives,
with no transition and no stagger — an "everything at once" entrance in each
case:

- `apps/web/app/components/meetings/MeetingsListView.tsx:73-84` (meeting cards)
- `apps/web/app/components/traces/TracesListView.tsx:99-103` (trace rows)
- `apps/web/app/components/meetings/MeetingTimeline.tsx:121-127` (decision/action-item entries)
- `apps/web/app/components/traces/TraceStageTimeline.tsx:21-46` (trace stage cards)

This happens once per page view (on mount, or after a filter/data change),
not per-interaction, so a subtle stagger is safe here in a way it would not
be on a tens-of-times-a-day interaction — but it must stay subtle (a 30ms
step, capped) to match this app's restrained, clinical "glass minimalism"
personality (see `CLAUDE.md` section 3), not read as bouncy or delay the
list from feeling loaded.

Current state, `apps/web/app/components/meetings/MeetingsListView.tsx:73-84`:

```tsx
      <div className="flex flex-col gap-3">
        {meetings.map((meeting) => (
          <Link key={meeting.id} href={`/meetings/${meeting.id}`}>
            <Card interactive>
              <p className="font-medium text-foreground">{meeting.title}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {meeting.date} &middot; {meeting.participants.join(", ")}
              </p>
            </Card>
          </Link>
        ))}
      </div>
```

Current state, `apps/web/app/components/traces/TracesListView.tsx:99-103`:

```tsx
      <div className="flex flex-col gap-3">
        {traces.map((trace) => (
          <TraceListRow key={trace.id} trace={trace} />
        ))}
      </div>
```

Current state, `apps/web/app/components/meetings/MeetingTimeline.tsx:121-127`:

```tsx
      <ol className="flex flex-col gap-3">
        {entries.map((entry) => (
          <li key={`${entry.kind}-${entry.item.id}`}>
            <TimelineEntryCard entry={entry} />
          </li>
        ))}
      </ol>
```

Current state, `apps/web/app/components/traces/TraceStageTimeline.tsx:21-46`:

```tsx
  return (
    <ol className="flex flex-col gap-3">
      {stages.map((stage, index) => (
        <li key={`${stage.name}-${index}`}>
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-mono text-sm text-foreground">{stage.name}</span>
              <span className="text-xs text-muted-foreground">
                {formatDuration(stage.duration_ms)}
              </span>
            </div>
            {Object.keys(stage.metadata).length > 0 && (
              <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                {Object.entries(stage.metadata).map(([key, value]) => (
                  <div key={key} className="flex gap-1">
                    <dt className="font-medium">{key}:</dt>
                    <dd>{String(value)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </Card>
        </li>
      ))}
    </ol>
  );
```

## Target

This plan depends on [plan 001](001-motion-tokens-foundation.md) having
already landed — it imports `LIST_ENTER_CLASSES` and `staggerDelayStyle`
from `apps/web/app/lib/motion.ts`. If that file does not exist yet, stop and
apply plan 001 first.

Each file gets the per-item wrapper element (already present in three of the
four cases) given a className and an inline style computed by
`staggerDelayStyle(index)`. No child component (`Card`, `TraceListRow`,
`TimelineEntryCard`) needs any prop changes — the entrance classes and
stagger delay are applied to the element that already wraps each item.

**`MeetingsListView.tsx`** — apply to the existing `<Link>` (Next.js
forwards `className`/`style` straight to the rendered `<a>`):

```tsx
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Card } from "@/app/components/ui/Card";
import { Panel } from "@/app/components/ui/Panel";
import { MeetingIngestUpload } from "@/app/components/meetings/MeetingIngestUpload";
import { listMeetings, toErrorMessage } from "@/app/lib/api/client";
import { LIST_ENTER_CLASSES, staggerDelayStyle } from "@/app/lib/motion";
import type { MeetingSummary } from "@/app/lib/api/types";

// ...

      <div className="flex flex-col gap-3">
        {meetings.map((meeting, index) => (
          <Link
            key={meeting.id}
            href={`/meetings/${meeting.id}`}
            className={LIST_ENTER_CLASSES}
            style={staggerDelayStyle(index)}
          >
            <Card interactive>
              <p className="font-medium text-foreground">{meeting.title}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {meeting.date} &middot; {meeting.participants.join(", ")}
              </p>
            </Card>
          </Link>
        ))}
      </div>
```

**`TracesListView.tsx`** — there is currently no per-item wrapper element
(`TraceListRow` is rendered directly); add a plain wrapper `<div>` around it
rather than changing `TraceListRow`'s props:

```tsx
import { useEffect, useState } from "react";

import { Button } from "@/app/components/ui/Button";
import { Panel } from "@/app/components/ui/Panel";
import { listTraces, toErrorMessage } from "@/app/lib/api/client";
import { LIST_ENTER_CLASSES, staggerDelayStyle } from "@/app/lib/motion";
import type { Trace, TraceOutcome } from "@/app/lib/api/types";

import { TraceFilters } from "./TraceFilters";
import { TraceListRow } from "./TraceListRow";

// ...

      <div className="flex flex-col gap-3">
        {traces.map((trace, index) => (
          <div key={trace.id} className={LIST_ENTER_CLASSES} style={staggerDelayStyle(index)}>
            <TraceListRow trace={trace} />
          </div>
        ))}
      </div>
```

**`MeetingTimeline.tsx`** — apply to the existing `<li>`:

```tsx
import { LIST_ENTER_CLASSES, staggerDelayStyle } from "@/app/lib/motion";

// ... (added alongside this file's other imports)

      <ol className="flex flex-col gap-3">
        {entries.map((entry, index) => (
          <li
            key={`${entry.kind}-${entry.item.id}`}
            className={LIST_ENTER_CLASSES}
            style={staggerDelayStyle(index)}
          >
            <TimelineEntryCard entry={entry} />
          </li>
        ))}
      </ol>
```

**`TraceStageTimeline.tsx`** — apply to the existing `<li>` (this file has no
`"use client"` directive and imports nothing from `react` today; add the
`motion` import only):

```tsx
import { Card } from "@/app/components/ui/Card";
import { formatDuration } from "@/app/lib/format";
import { LIST_ENTER_CLASSES, staggerDelayStyle } from "@/app/lib/motion";
import type { TraceStage } from "@/app/lib/api/types";

// ...

    <ol className="flex flex-col gap-3">
      {stages.map((stage, index) => (
        <li
          key={`${stage.name}-${index}`}
          className={LIST_ENTER_CLASSES}
          style={staggerDelayStyle(index)}
        >
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-mono text-sm text-foreground">{stage.name}</span>
              <span className="text-xs text-muted-foreground">
                {formatDuration(stage.duration_ms)}
              </span>
            </div>
            {Object.keys(stage.metadata).length > 0 && (
              <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                {Object.entries(stage.metadata).map(([key, value]) => (
                  <div key={key} className="flex gap-1">
                    <dt className="font-medium">{key}:</dt>
                    <dd>{String(value)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </Card>
        </li>
      ))}
    </ol>
```

(`TraceStageTimeline`'s `.map` callback already receives `index` today — it
is only newly *used* here, not newly added.)

## Repo conventions to follow

- `LIST_ENTER_CLASSES` and `staggerDelayStyle` come from
  `apps/web/app/lib/motion.ts` (added in plan 001): the same
  `@starting-style` fade-and-rise recipe as `ENTER_TRANSITION_CLASSES`, plus
  a `transition-delay` driven by a `--stagger-delay` custom property.
  `staggerDelayStyle(index)` returns a ready-to-use `CSSProperties` object —
  no per-file `CSSProperties` import or cast is needed at any of these four
  call sites.
- The stagger is capped at the first 8 items (index 0-7, each 30ms apart;
  everything from index 8 onward shares item 7's delay) — verified in plan
  001's `staggerDelayStyle` implementation — so a long trace or timeline list
  never makes the tail feel like it's waiting on the animation.
- Applying motion classes to the element that already wraps each item (an
  existing `<Link>`, `<li>`, or a newly-added thin `<div>`) means no child
  component (`Card`, `TraceListRow`, `TimelineEntryCard`) needs new
  className/style passthrough props — keeps this plan's footprint to
  exactly the four list-rendering files.

## Steps

1. In `apps/web/app/components/meetings/MeetingsListView.tsx`: add the
   `LIST_ENTER_CLASSES, staggerDelayStyle` import from `@/app/lib/motion`;
   change `meetings.map((meeting) => (` to
   `meetings.map((meeting, index) => (`; add `className={LIST_ENTER_CLASSES}`
   and `style={staggerDelayStyle(index)}` to the `<Link>` element (lines
   74-75 today).
2. In `apps/web/app/components/traces/TracesListView.tsx`: add the same
   import; replace lines 99-103 with the target block shown above (wrapping
   `<TraceListRow trace={trace} />` in a `<div key={trace.id} ...>`, moving
   `key` from `TraceListRow` to the new wrapper).
3. In `apps/web/app/components/meetings/MeetingTimeline.tsx`: add the same
   import; change `entries.map((entry) => (` to
   `entries.map((entry, index) => (`; add `className={LIST_ENTER_CLASSES}`
   and `style={staggerDelayStyle(index)}` to the `<li>` element (line 123
   today).
4. In `apps/web/app/components/traces/TraceStageTimeline.tsx`: add the same
   import; add `className={LIST_ENTER_CLASSES}` and
   `style={staggerDelayStyle(index)}` to the `<li>` element (line 24 today) —
   `index` is already a parameter of the `.map` callback, no signature
   change needed.
5. Save all four files.

## Boundaries

- Do NOT modify `Card.tsx`, `TraceListRow.tsx`, or `TimelineEntryCard.tsx` —
  every edit in this plan lands on the element that already wraps each
  mapped item, in the four files listed above, not on the child components
  they render.
- Do NOT modify any of the four components' test files.
- Do NOT change stagger timing beyond what `staggerDelayStyle` already
  provides (no per-file overrides of the 30ms step or the 8-item cap).
- Do NOT touch `TracesListView.tsx`'s pagination controls or loading/error
  text (lines 93-97, 105-127) in this plan — a related but distinct fix for
  that area is [plan 007](007-trace-list-stale-dim-on-refetch.md). If plan
  007 has already landed, the outer `<div className="flex flex-col gap-3">`
  wrapper on line 99 may carry an additional conditional `opacity-*` class —
  that is expected; only change the `.map()` body inside it as shown above,
  do not revert plan 007's change to the outer div's className.
- If any of the four "Current state" excerpts above has drifted, STOP and
  report instead of improvising the merge.

## Verification

- **Mechanical**: `cd apps/web && npm run typecheck && npm run lint && npm run test:ci && npm run build` — all must pass. None of `MeetingsListView.test.tsx`, `TracesListView.test.tsx`, `MeetingTimeline.test.tsx`, or `TraceStageTimeline.test.tsx` assert on `className`/`style` for these list items (verified: they assert on link `href`s, rendered text, and call counts only), so all four should pass unmodified.
- **Feel check**: run `npm run dev` and:
  - On `/meetings` with two or more ingested meetings, reload the page and watch the cards appear — each should fade/rise in with a slight, barely-perceptible stagger (not a strong cascading bounce).
  - On `/traces` with several traces, reload and confirm the same for trace rows.
  - Open a meeting detail page with multiple decisions/action items and confirm the timeline entries stagger in the same way.
  - Open a trace detail page with multiple stages and confirm the stage cards stagger in the same way.
  - In DevTools' Animations panel, scrub through the entrance at 10% speed and confirm each item's delay increases by a fixed, small step rather than jumping unevenly.
  - Toggle `prefers-reduced-motion: reduce` in DevTools' Rendering panel, reload each page, and confirm items still fade in together with no stagger delay and no rise.
- **Done when**: all four files build and lint cleanly, their existing test suites pass unmodified, and the feel-check above confirms a subtle, capped, reduced-motion-aware stagger on first load in all four views.
