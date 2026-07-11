"use client";

import { useEffect, useState } from "react";

import { listMeetings } from "@/app/lib/api/client";
import type { MeetingSummary } from "@/app/lib/api/types";

interface MeetingScopeSelectProps {
  value: string;
  onChange: (meetingId: string) => void;
  disabled?: boolean;
}

/** Lets a question be scoped to one meeting or asked across all of them.
 * An empty value means "all meetings" (POST /ask); a meeting id means
 * POST /meetings/{id}/ask. Fetches the meeting list itself -- if that
 * fails, scoping is simply unavailable for this session; asking globally
 * still works, so the failure isn't surfaced as a blocking error. */
export function MeetingScopeSelect({ value, onChange, disabled }: MeetingScopeSelectProps) {
  const [meetings, setMeetings] = useState<MeetingSummary[]>([]);

  useEffect(() => {
    let cancelled = false;
    listMeetings()
      .then((data) => {
        if (!cancelled) {
          setMeetings(data);
        }
      })
      .catch(() => {
        // Scoping is a convenience, not a requirement -- asking globally
        // still works even if the meeting list can't be fetched.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <select
      aria-label="Scope this question to a meeting"
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
      className="w-full rounded-full border border-border bg-surface-solid/80 px-4 py-2 text-sm text-foreground shadow-[var(--shadow-glass-inset)] outline-none focus:border-accent/50 focus:ring-2 focus:ring-accent/30"
    >
      <option value="">All meetings</option>
      {meetings.map((meeting) => (
        <option key={meeting.id} value={meeting.id}>
          {meeting.title}
        </option>
      ))}
    </select>
  );
}
