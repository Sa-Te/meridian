"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/app/components/ui/Badge";
import { Card } from "@/app/components/ui/Card";
import { listMeetingActionItems, listMeetingDecisions, toErrorMessage } from "@/app/lib/api/client";
import type { ActionItem, ActionItemStatus, Decision } from "@/app/lib/api/types";

import { ActionItemFilters } from "./ActionItemFilters";
import { TimelineEntryCard } from "./TimelineEntryCard";
import type { TimelineEntry } from "./TimelineEntryCard";

interface MeetingTimelineProps {
  meetingId: string;
}

/** Decisions and action items merged into one chronological timeline,
 * ordered by each item's source_citation.start_ts -- when it was actually
 * said in the meeting, not created_at (extraction insert time, which is
 * nearly identical across every item from one ingest and so carries no
 * real ordering signal). Action items can be filtered by owner/status;
 * decisions are always shown. See docs/adr/0014.
 */
export function MeetingTimeline({ meetingId }: MeetingTimelineProps) {
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [actionItems, setActionItems] = useState<ActionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<ActionItemStatus | "">("");
  const [ownerFilter, setOwnerFilter] = useState("");

  useEffect(() => {
    let cancelled = false;
    // See MeetingsListView's identical comment: resetting loading/error
    // before the fetch starts is React's own documented data-fetching
    // pattern, not the "cascading renders" case this rule targets.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);

    Promise.all([listMeetingDecisions(meetingId), listMeetingActionItems(meetingId)])
      .then(([decisionData, actionItemData]) => {
        if (!cancelled) {
          setDecisions(decisionData);
          setActionItems(actionItemData);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(toErrorMessage(caught));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [meetingId]);

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading timeline...</p>;
  }

  if (error) {
    return (
      <Card>
        <Badge tone="danger">Error</Badge>
        <p className="mt-2 text-sm text-foreground">{error}</p>
      </Card>
    );
  }

  if (decisions.length === 0 && actionItems.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No decisions or action items were extracted from this meeting.
      </p>
    );
  }

  const owners = Array.from(
    new Set(actionItems.map((item) => item.owner).filter((owner): owner is string => owner !== null)),
  ).sort();

  const filteredActionItems = actionItems.filter((item) => {
    if (statusFilter && item.status !== statusFilter) {
      return false;
    }
    if (ownerFilter && item.owner !== ownerFilter) {
      return false;
    }
    return true;
  });

  const entries: TimelineEntry[] = [
    ...decisions.map((item): TimelineEntry => ({ kind: "decision", item })),
    ...filteredActionItems.map((item): TimelineEntry => ({ kind: "action_item", item })),
  ].sort((a, b) => a.item.source_citation.start_ts - b.item.source_citation.start_ts);

  return (
    <div className="flex flex-col gap-4">
      {actionItems.length > 0 && (
        <ActionItemFilters
          owners={owners}
          status={statusFilter}
          owner={ownerFilter}
          onStatusChange={setStatusFilter}
          onOwnerChange={setOwnerFilter}
        />
      )}

      {entries.length === 0 && (
        <p className="text-sm text-muted-foreground">No action items match the selected filters.</p>
      )}

      <ol className="flex flex-col gap-3">
        {entries.map((entry) => (
          <li key={`${entry.kind}-${entry.item.id}`}>
            <TimelineEntryCard entry={entry} />
          </li>
        ))}
      </ol>
    </div>
  );
}
