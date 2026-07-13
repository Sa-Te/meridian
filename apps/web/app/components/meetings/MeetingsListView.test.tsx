import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ingestMeeting, listMeetings } from "@/app/lib/api/client";

import { MeetingsListView } from "./MeetingsListView";

vi.mock("@/app/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/app/lib/api/client")>(
    "@/app/lib/api/client",
  );
  return {
    ...actual,
    listMeetings: vi.fn(),
    ingestMeeting: vi.fn(),
  };
});

describe("MeetingsListView", () => {
  beforeEach(() => {
    vi.mocked(listMeetings).mockReset();
    vi.mocked(ingestMeeting).mockReset();
  });

  it("shows a loading state before meetings arrive", () => {
    vi.mocked(listMeetings).mockReturnValue(new Promise(() => {}));

    render(<MeetingsListView />);

    expect(screen.getByText("Loading meetings...")).toBeInTheDocument();
  });

  it("renders each meeting as a link to its detail page", async () => {
    vi.mocked(listMeetings).mockResolvedValue([
      {
        id: "m1",
        title: "Alert Thresholds Review",
        date: "2026-01-29",
        participants: ["Naomi", "Dr. Vasquez"],
        created_at: "2026-01-29T00:00:00Z",
      },
    ]);

    render(<MeetingsListView />);

    await waitFor(() => {
      expect(screen.getByText("Alert Thresholds Review")).toBeInTheDocument();
    });
    const link = screen.getByRole("link", { name: /Alert Thresholds Review/ });
    expect(link).toHaveAttribute("href", "/meetings/m1");
    expect(screen.getByText(/Naomi, Dr. Vasquez/)).toBeInTheDocument();
  });

  it("shows an empty state when there are no meetings", async () => {
    vi.mocked(listMeetings).mockResolvedValue([]);

    render(<MeetingsListView />);

    await waitFor(() => {
      expect(screen.getByText("No meetings have been ingested yet.")).toBeInTheDocument();
    });
  });

  it("shows an error message if the fetch fails", async () => {
    vi.mocked(listMeetings).mockRejectedValue(new Error("boom"));

    render(<MeetingsListView />);

    await waitFor(() => {
      expect(screen.getByText("Something went wrong. Please try again.")).toBeInTheDocument();
    });
  });

  it("refetches the meetings list after a successful ingest", async () => {
    vi.mocked(listMeetings).mockResolvedValue([]);
    vi.mocked(ingestMeeting).mockResolvedValue({
      meeting_id: "m1",
      chunk_count: 1,
      decision_count: 0,
      action_item_count: 0,
      flagged_for_prompt_injection: false,
      prompt_injection_findings: [],
    });

    render(<MeetingsListView />);
    await waitFor(() => expect(listMeetings).toHaveBeenCalledTimes(1));

    const file = new File(["hello"], "2026-01-14_call.txt", { type: "text/plain" });
    fireEvent.change(screen.getByLabelText("Transcript file"), { target: { files: [file] } });

    await waitFor(() => expect(listMeetings).toHaveBeenCalledTimes(2));
  });
});
