import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listMeetingActionItems, listMeetingDecisions } from "@/app/lib/api/client";
import type { ActionItem, Decision } from "@/app/lib/api/types";

import { MeetingTimeline } from "./MeetingTimeline";

vi.mock("@/app/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/app/lib/api/client")>(
    "@/app/lib/api/client",
  );
  return {
    ...actual,
    listMeetingDecisions: vi.fn(),
    listMeetingActionItems: vi.fn(),
  };
});

function citation(startTs: number, speaker: string) {
  return {
    chunk_id: `chunk-${startTs}`,
    meeting_id: "m1",
    speaker,
    start_ts: startTs,
    end_ts: startTs + 10,
    text: `Excerpt at ${startTs}`,
  };
}

const earlyDecision: Decision = {
  id: "d1",
  meeting_id: "m1",
  text: "Freeze the schema.",
  source_citation: citation(60, "Dhruvisha"),
  confidence: 0.9,
  created_at: "2026-01-29T00:00:00Z",
};

const laterActionItem: ActionItem = {
  id: "a1",
  meeting_id: "m1",
  text: "Send the source by Friday.",
  owner: "Dr. Vasquez",
  due_date: null,
  source_citation: citation(400, "Dhruvisha"),
  confidence: 0.9,
  status: "open",
  created_at: "2026-01-29T00:00:00Z",
};

const doneActionItem: ActionItem = {
  id: "a2",
  meeting_id: "m1",
  text: "Already shipped this one.",
  owner: "Naomi",
  due_date: null,
  source_citation: citation(200, "Naomi"),
  confidence: 0.9,
  status: "done",
  created_at: "2026-01-29T00:00:00Z",
};

describe("MeetingTimeline", () => {
  beforeEach(() => {
    vi.mocked(listMeetingDecisions).mockReset();
    vi.mocked(listMeetingActionItems).mockReset();
  });

  it("shows a loading state before data arrives", () => {
    vi.mocked(listMeetingDecisions).mockReturnValue(new Promise(() => {}));
    vi.mocked(listMeetingActionItems).mockReturnValue(new Promise(() => {}));

    render(<MeetingTimeline meetingId="m1" />);

    expect(screen.getByText("Loading timeline...")).toBeInTheDocument();
  });

  it("renders decisions and action items merged in chronological order", async () => {
    vi.mocked(listMeetingDecisions).mockResolvedValue([earlyDecision]);
    vi.mocked(listMeetingActionItems).mockResolvedValue([laterActionItem, doneActionItem]);

    render(<MeetingTimeline meetingId="m1" />);

    await waitFor(() => {
      expect(screen.getByText("Freeze the schema.")).toBeInTheDocument();
    });

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(3);
    // start_ts order: earlyDecision (60), doneActionItem (200), laterActionItem (400)
    expect(items[0]).toHaveTextContent("Freeze the schema.");
    expect(items[1]).toHaveTextContent("Already shipped this one.");
    expect(items[2]).toHaveTextContent("Send the source by Friday.");
  });

  it("filters action items by status while keeping decisions visible", async () => {
    vi.mocked(listMeetingDecisions).mockResolvedValue([earlyDecision]);
    vi.mocked(listMeetingActionItems).mockResolvedValue([laterActionItem, doneActionItem]);

    render(<MeetingTimeline meetingId="m1" />);
    await waitFor(() => screen.getByText("Freeze the schema."));

    fireEvent.change(screen.getByLabelText("Filter action items by status"), {
      target: { value: "done" },
    });

    expect(screen.getByText("Freeze the schema.")).toBeInTheDocument();
    expect(screen.getByText("Already shipped this one.")).toBeInTheDocument();
    expect(screen.queryByText("Send the source by Friday.")).not.toBeInTheDocument();
  });

  it("filters action items by owner", async () => {
    vi.mocked(listMeetingDecisions).mockResolvedValue([]);
    vi.mocked(listMeetingActionItems).mockResolvedValue([laterActionItem, doneActionItem]);

    render(<MeetingTimeline meetingId="m1" />);
    await waitFor(() => screen.getByText("Send the source by Friday."));

    fireEvent.change(screen.getByLabelText("Filter action items by owner"), {
      target: { value: "Naomi" },
    });

    expect(screen.queryByText("Send the source by Friday.")).not.toBeInTheDocument();
    expect(screen.getByText("Already shipped this one.")).toBeInTheDocument();
  });

  it("shows an empty state when nothing was extracted", async () => {
    vi.mocked(listMeetingDecisions).mockResolvedValue([]);
    vi.mocked(listMeetingActionItems).mockResolvedValue([]);

    render(<MeetingTimeline meetingId="m1" />);

    await waitFor(() => {
      expect(
        screen.getByText("No decisions or action items were extracted from this meeting."),
      ).toBeInTheDocument();
    });
  });

  it("shows an error state when the fetch fails", async () => {
    vi.mocked(listMeetingDecisions).mockRejectedValue(new Error("boom"));
    vi.mocked(listMeetingActionItems).mockResolvedValue([]);

    render(<MeetingTimeline meetingId="m1" />);

    await waitFor(() => {
      expect(screen.getByText("Something went wrong. Please try again.")).toBeInTheDocument();
    });
  });
});
