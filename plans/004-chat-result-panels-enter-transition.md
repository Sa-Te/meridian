# 004 — Fade in ChatView's result panels instead of teleporting

- **Status**: DONE
- **Commit**: ccf3b91
- **Severity**: MEDIUM
- **Category**: Missed opportunity (state change)
- **Estimated scope**: 1 file, 4 similar edits

## Problem

`ChatView` is the app's home route (`/`) and its primary screen. After
submitting a question, one of four mutually-exclusive `Panel`s appears below
the form: loading, error, a supported answer, or a declined answer. All four
currently teleport into the DOM with zero transition — a hard content swap on
the single most-used screen in the product.

Current state, `apps/web/app/components/chat/ChatView.tsx:75-106`:

```tsx
      {loading && (
        <Panel data-testid="chat-loading">
          <p className="text-sm text-muted-foreground">Thinking...</p>
        </Panel>
      )}

      {error && (
        <Panel data-testid="chat-error">
          <Badge tone="danger">Error</Badge>
          <p className="mt-2 text-sm text-foreground">{error}</p>
        </Panel>
      )}

      {answer && !loading && answer.supported && (
        <Panel data-testid="chat-answer">
          <p className="text-sm leading-relaxed text-foreground">{answer.answer}</p>
          {answer.citations.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {answer.citations.map((citation) => (
                <CitationChip key={citation.chunk_id} citation={citation} />
              ))}
            </div>
          )}
        </Panel>
      )}

      {answer && !loading && !answer.supported && (
        <Panel data-testid="chat-declined">
          <Badge tone="neutral">Not well-supported</Badge>
          <p className="mt-2 text-sm text-muted-foreground">{answer.answer}</p>
        </Panel>
      )}
```

## Target

This plan depends on [plan 001](001-motion-tokens-foundation.md) having
already landed — it imports `ENTER_TRANSITION_CLASSES` from
`apps/web/app/lib/motion.ts`. If that file does not exist yet, stop and apply
plan 001 first.

Add the import and apply the constant to all four `Panel`s:

```tsx
import { ENTER_TRANSITION_CLASSES } from "@/app/lib/motion";

// ...

      {loading && (
        <Panel data-testid="chat-loading" className={ENTER_TRANSITION_CLASSES}>
          <p className="text-sm text-muted-foreground">Thinking...</p>
        </Panel>
      )}

      {error && (
        <Panel data-testid="chat-error" className={ENTER_TRANSITION_CLASSES}>
          <Badge tone="danger">Error</Badge>
          <p className="mt-2 text-sm text-foreground">{error}</p>
        </Panel>
      )}

      {answer && !loading && answer.supported && (
        <Panel data-testid="chat-answer" className={ENTER_TRANSITION_CLASSES}>
          <p className="text-sm leading-relaxed text-foreground">{answer.answer}</p>
          {answer.citations.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {answer.citations.map((citation) => (
                <CitationChip key={citation.chunk_id} citation={citation} />
              ))}
            </div>
          )}
        </Panel>
      )}

      {answer && !loading && !answer.supported && (
        <Panel data-testid="chat-declined" className={ENTER_TRANSITION_CLASSES}>
          <Badge tone="neutral">Not well-supported</Badge>
          <p className="mt-2 text-sm text-muted-foreground">{answer.answer}</p>
        </Panel>
      )}
```

## Repo conventions to follow

- `Panel` (`apps/web/app/components/ui/Panel.tsx:11-23`) already accepts and
  merges an optional `className` prop via `cn()` — no change to `Panel.tsx`
  itself is needed, only to how `ChatView.tsx` calls it.
- `ENTER_TRANSITION_CLASSES` comes from `apps/web/app/lib/motion.ts` (added
  in plan 001) so this exact fade-and-rise entrance recipe — used identically
  here and in [plan 003](003-citation-chip-expand-motion.md) and
  [plan 005](005-ingest-upload-status-enter-transition.md) — is defined once
  rather than re-typed per file. It compiles to an `@starting-style`-based
  transition (verified against this repo's installed Tailwind v4.3.2) that
  needs no extra mount-tracking state, since these panels already mount and
  unmount via plain React conditional rendering.

## Steps

1. In `apps/web/app/components/chat/ChatView.tsx`, add
   `import { ENTER_TRANSITION_CLASSES } from "@/app/lib/motion";` to the
   import block (after the existing `MeetingScopeSelect` import).
2. Add `className={ENTER_TRANSITION_CLASSES}` to each of the four `Panel`
   elements at lines 76, 82, 89, and 102, exactly as shown in the Target
   section. Do not change `data-testid`, conditions, or any child markup.
3. Save.

## Boundaries

- Do NOT touch the top form `Panel` (lines 51-73) — it is always mounted
  (never conditionally rendered), so an entrance transition would never fire
  and is out of scope.
- Do NOT modify `ChatView.test.tsx`.
- Do NOT change the conditional logic that decides which panel renders.
- Do NOT add exit animations — these panels replace each other via React's
  normal mount/unmount; only the entrance is in scope, matching plan 003's
  same trade-off.
- If any of the four `Panel` blocks has drifted from the "Current state"
  excerpt above, STOP and report instead of improvising the merge.

## Verification

- **Mechanical**: `cd apps/web && npm run typecheck && npm run lint && npm run test:ci && npm run build` — all must pass. `ChatView.test.tsx` asserts on `data-testid` presence/absence and text content only (e.g. `chat-loading`, `chat-answer`, `chat-declined`, `chat-error`), never on `className`, so it should pass unmodified.
- **Feel check**: run `npm run dev`, open `/`, and:
  - Submit a question — the "Thinking..." panel should fade and rise gently into place, not pop in.
  - Once the answer arrives, the loading panel is replaced by the answer panel — confirm the answer panel also fades/rises in rather than teleporting.
  - Trigger an error (e.g. stop the API server before submitting) and confirm the error panel does the same.
  - In DevTools' Animations panel, set playback to 10% and confirm the motion eases out smoothly rather than linearly.
  - Toggle `prefers-reduced-motion: reduce` in DevTools' Rendering panel and confirm each panel still fades in but no longer visibly rises.
- **Done when**: the file builds and lints cleanly, `ChatView.test.tsx` passes unmodified, and all four panels visibly ease in rather than teleporting, correctly softened under reduced motion.
