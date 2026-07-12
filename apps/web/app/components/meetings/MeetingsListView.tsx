"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Card } from "@/app/components/ui/Card";
import { Panel } from "@/app/components/ui/Panel";
import { MeetingIngestUpload } from "@/app/components/meetings/MeetingIngestUpload";
import { listMeetings, toErrorMessage } from "@/app/lib/api/client";
import type { MeetingSummary } from "@/app/lib/api/types";

export function MeetingsListView() {
  const [meetings, setMeetings] = useState<MeetingSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Bumped after a successful ingest to re-run the fetch effect below,
  // so a newly ingested meeting shows up without a manual page reload.
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    // Resetting loading/error synchronously before the fetch starts is the
    // standard "reset state before an effect's async work" pattern from
    // React's own docs (https://react.dev/reference/react/useEffect#fetching-data-with-effects)
    // -- see docs/adr/0014 for why this is suppressed rather than restructured.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);

    listMeetings()
      .then((data) => {
        if (!cancelled) {
          setMeetings(data);
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
  }, [refreshToken]);

  const handleIngested = useCallback(() => {
    setRefreshToken((token) => token + 1);
  }, []);

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <Panel>
        <h1 className="text-lg font-medium text-foreground">Meetings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Browse ingested meetings to review their decisions and action items.
        </p>
      </Panel>

      <MeetingIngestUpload onIngested={handleIngested} />

      {loading && <p className="text-sm text-muted-foreground">Loading meetings...</p>}
      {error && <p className="text-sm text-danger">{error}</p>}
      {!loading && !error && meetings.length === 0 && (
        <p className="text-sm text-muted-foreground">No meetings have been ingested yet.</p>
      )}

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
    </div>
  );
}
