import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listMeetings } from "@/app/lib/api/client";

import { MeetingScopeSelect } from "./MeetingScopeSelect";

vi.mock("@/app/lib/api/client", () => ({
  listMeetings: vi.fn(),
}));

describe("MeetingScopeSelect", () => {
  beforeEach(() => {
    vi.mocked(listMeetings).mockReset();
  });

  it("always offers 'All meetings'", async () => {
    vi.mocked(listMeetings).mockResolvedValue([]);

    render(<MeetingScopeSelect value="" onChange={vi.fn()} />);

    expect(await screen.findByRole("option", { name: "All meetings" })).toBeInTheDocument();
  });

  it("lists fetched meetings as options", async () => {
    vi.mocked(listMeetings).mockResolvedValue([
      {
        id: "m1",
        title: "Alert Thresholds Review",
        date: "2026-01-29",
        participants: ["Naomi"],
        created_at: "2026-01-29T00:00:00Z",
      },
    ]);

    render(<MeetingScopeSelect value="" onChange={vi.fn()} />);

    expect(
      await screen.findByRole("option", { name: "Alert Thresholds Review" }),
    ).toBeInTheDocument();
  });

  it("calls onChange with the selected meeting id", async () => {
    vi.mocked(listMeetings).mockResolvedValue([
      {
        id: "m1",
        title: "Alert Thresholds Review",
        date: "2026-01-29",
        participants: ["Naomi"],
        created_at: "2026-01-29T00:00:00Z",
      },
    ]);
    const handleChange = vi.fn();
    render(<MeetingScopeSelect value="" onChange={handleChange} />);
    await waitFor(() => screen.getByRole("option", { name: "Alert Thresholds Review" }));

    fireEvent.change(screen.getByLabelText("Scope this question to a meeting"), {
      target: { value: "m1" },
    });

    expect(handleChange).toHaveBeenCalledWith("m1");
  });

  it("still renders 'All meetings' if the fetch fails", async () => {
    vi.mocked(listMeetings).mockRejectedValue(new Error("network down"));

    render(<MeetingScopeSelect value="" onChange={vi.fn()} />);

    expect(await screen.findByRole("option", { name: "All meetings" })).toBeInTheDocument();
  });
});
