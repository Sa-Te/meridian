import { CitationChip } from "@/app/components/citations/CitationChip";
import { Badge } from "@/app/components/ui/Badge";
import { Card } from "@/app/components/ui/Card";
import { toErrorMessage, updateActionItemStatus } from "@/app/lib/api/client";
import type { ActionItem, ActionItemStatus, Decision } from "@/app/lib/api/types";
import { useState } from "react";
import { Button } from "../ui/Button";

export type TimelineEntry =
  | { kind: "decision"; item: Decision }
  | { kind: "action_item"; item: ActionItem };

const STATUS_LABEL: Record<ActionItem["status"], string> = {
  open: "Open",
  in_progress: "In progress",
  done: "Done",
};

const SEVERITY_LABEL: Record<Decision["severity"], string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

interface TimelineEntryCardProps {
  entry: TimelineEntry;
  onActionItemStatusChange: (actionItemId: string, newStatus: ActionItemStatus) => void;
}

/** One row of a meeting's decisions/action-items timeline -- a decision or
 * an action item, either way linked back to the transcript excerpt it was
 * extracted from via the shared CitationChip. */
export function TimelineEntryCard({
  entry,
  onActionItemStatusChange,
}: TimelineEntryCardProps) {
  const [isUpdating, setIsUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleMarkDone() {
    setIsUpdating(true);
    try {
      const updated = await updateActionItemStatus(
        entry.item.meeting_id,
        entry.item.id,
        "done",
      );
      onActionItemStatusChange(entry.item.id, updated.status);
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setIsUpdating(false);
    }
  }

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        {entry.kind === "decision" ? (
          <>
            <Badge tone="accent">Decision</Badge>
            <Badge tone="neutral">{SEVERITY_LABEL[entry.item.severity]}</Badge>
          </>
        ) : (
          <>
            <Badge tone="neutral">{STATUS_LABEL[entry.item.status]}</Badge>

            {entry.item.owner && (
              <span className="text-xs text-muted-foreground">
                {entry.item.owner}
              </span>
            )}
            {entry.item.status !== "done" && (
              <Button onClick={handleMarkDone} disabled={isUpdating}>
                {isUpdating ? "Marking..." : "Mark Done"}
              </Button>
            )}
          </>
        )}
      </div>
      <p className="mt-2 text-sm text-foreground">{entry.item.text}</p>
      {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
      <div className="mt-3">
        <CitationChip citation={entry.item.source_citation} />
      </div>
    </Card>
  );
}
