import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getMeeting,
  listMeetingActionItems,
  listMeetingDecisions,
} from "@/app/lib/api/client";

import { MeetingDetailView } from "./MeetingDetailView";

vi.mock("@/app/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/app/lib/api/client")>(
    "@/app/lib/api/client",
  );
  return {
    ...actual,
    getMeeting: vi.fn(),
    listMeetingDecisions: vi.fn(),
    listMeetingActionItems: vi.fn(),
  };
});

describe("MeetingDetailView", () => {
  beforeEach(() => {
    vi.mocked(getMeeting).mockReset();
    vi.mocked(listMeetingDecisions).mockReset().mockResolvedValue([]);
    vi.mocked(listMeetingActionItems).mockReset().mockResolvedValue([]);
  });

  it("shows a loading state before the meeting arrives", () => {
    vi.mocked(getMeeting).mockReturnValue(new Promise(() => {}));

    render(<MeetingDetailView meetingId="m1" />);

    expect(screen.getByText("Loading meeting...")).toBeInTheDocument();
  });

  it("renders the meeting header and its timeline once loaded", async () => {
    vi.mocked(getMeeting).mockResolvedValue({
      id: "m1",
      title: "Alert Thresholds Review",
      date: "2026-01-29",
      participants: ["Naomi"],
      created_at: "2026-01-29T00:00:00Z",
    });

    render(<MeetingDetailView meetingId="m1" />);

    await waitFor(() => {
      expect(screen.getByText("Alert Thresholds Review")).toBeInTheDocument();
    });
    expect(screen.getByText(/2026-01-29/)).toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.getByText("No decisions or action items were extracted from this meeting."),
      ).toBeInTheDocument();
    });
  });

  it("shows an error message if the meeting fetch fails", async () => {
    vi.mocked(getMeeting).mockRejectedValue(new Error("not found"));

    render(<MeetingDetailView meetingId="m1" />);

    await waitFor(() => {
      expect(screen.getByText("Something went wrong. Please try again.")).toBeInTheDocument();
    });
  });
});
