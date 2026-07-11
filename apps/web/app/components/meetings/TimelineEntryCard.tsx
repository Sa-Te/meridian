import { CitationChip } from "@/app/components/citations/CitationChip";
import { Badge } from "@/app/components/ui/Badge";
import { Card } from "@/app/components/ui/Card";
import type { ActionItem, Decision } from "@/app/lib/api/types";

export type TimelineEntry =
  | { kind: "decision"; item: Decision }
  | { kind: "action_item"; item: ActionItem };

const STATUS_LABEL: Record<ActionItem["status"], string> = {
  open: "Open",
  in_progress: "In progress",
  done: "Done",
};

interface TimelineEntryCardProps {
  entry: TimelineEntry;
}

/** One row of a meeting's decisions/action-items timeline -- a decision or
 * an action item, either way linked back to the transcript excerpt it was
 * extracted from via the shared CitationChip. */
export function TimelineEntryCard({ entry }: TimelineEntryCardProps) {
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        {entry.kind === "decision" ? (
          <Badge tone="accent">Decision</Badge>
        ) : (
          <>
            <Badge tone="neutral">{STATUS_LABEL[entry.item.status]}</Badge>
            {entry.item.owner && (
              <span className="text-xs text-muted-foreground">{entry.item.owner}</span>
            )}
          </>
        )}
      </div>
      <p className="mt-2 text-sm text-foreground">{entry.item.text}</p>
      <div className="mt-3">
        <CitationChip citation={entry.item.source_citation} />
      </div>
    </Card>
  );
}
