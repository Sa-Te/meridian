"use client";

import { useEffect, useState } from "react";

import { Panel } from "@/app/components/ui/Panel";
import { getMeeting, toErrorMessage } from "@/app/lib/api/client";
import type { MeetingSummary } from "@/app/lib/api/types";

import { MeetingTimeline } from "./MeetingTimeline";

interface MeetingDetailViewProps {
  meetingId: string;
}

export function MeetingDetailView({ meetingId }: MeetingDetailViewProps) {
  const [meeting, setMeeting] = useState<MeetingSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    // See MeetingsListView's identical comment: resetting loading/error
    // before the fetch starts is React's own documented data-fetching
    // pattern, not the "cascading renders" case this rule targets.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);

    getMeeting(meetingId)
      .then((data) => {
        if (!cancelled) {
          setMeeting(data);
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

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <Panel>
        {loading && <p className="text-sm text-muted-foreground">Loading meeting...</p>}
        {error && <p className="text-sm text-danger">{error}</p>}
        {meeting && (
          <>
            <h1 className="text-lg font-medium text-foreground">{meeting.title}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {meeting.date} &middot; {meeting.participants.join(", ")}
            </p>
          </>
        )}
      </Panel>

      {meeting && <MeetingTimeline meetingId={meetingId} />}
    </div>
  );
}
