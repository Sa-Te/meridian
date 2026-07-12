import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ingestMeeting } from "@/app/lib/api/client";

import { MeetingIngestUpload } from "./MeetingIngestUpload";

vi.mock("@/app/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/app/lib/api/client")>(
    "@/app/lib/api/client",
  );
  return {
    ...actual,
    ingestMeeting: vi.fn(),
  };
});

function transcriptFile(name = "2026-01-14_discovery-call.txt") {
  return new File(["[00:00:08] Alex: Let's get started."], name, { type: "text/plain" });
}

describe("MeetingIngestUpload", () => {
  beforeEach(() => {
    vi.mocked(ingestMeeting).mockReset();
  });

  it("uploads a transcript and reports success", async () => {
    vi.mocked(ingestMeeting).mockResolvedValue({
      meeting_id: "m1",
      chunk_count: 12,
      decision_count: 2,
      action_item_count: 3,
      flagged_for_prompt_injection: false,
      prompt_injection_findings: [],
    });
    const onIngested = vi.fn();

    render(<MeetingIngestUpload onIngested={onIngested} />);

    fireEvent.change(screen.getByLabelText("Transcript file"), {
      target: { files: [transcriptFile()] },
    });

    await waitFor(() => {
      expect(screen.getByText("Ingested")).toBeInTheDocument();
    });
    expect(
      screen.getByText("12 chunks · 2 decisions · 3 action items."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Flagged for review")).not.toBeInTheDocument();
    expect(onIngested).toHaveBeenCalledTimes(1);
    expect(ingestMeeting).toHaveBeenCalledWith(expect.any(File));
  });

  it("flags the result when the guardrail scan finds prompt injection", async () => {
    vi.mocked(ingestMeeting).mockResolvedValue({
      meeting_id: "m2",
      chunk_count: 5,
      decision_count: 0,
      action_item_count: 0,
      flagged_for_prompt_injection: true,
      prompt_injection_findings: [
        { chunk_index: 1, pattern: "ignore-instructions", matched_text: "ignore all prior instructions" },
      ],
    });

    render(<MeetingIngestUpload />);

    fireEvent.change(screen.getByLabelText("Transcript file"), {
      target: { files: [transcriptFile()] },
    });

    await waitFor(() => {
      expect(screen.getByText("Flagged for review")).toBeInTheDocument();
    });
  });

  it("shows an error message when the upload fails", async () => {
    vi.mocked(ingestMeeting).mockRejectedValue(new Error("boom"));
    const onIngested = vi.fn();

    render(<MeetingIngestUpload onIngested={onIngested} />);

    fireEvent.change(screen.getByLabelText("Transcript file"), {
      target: { files: [transcriptFile()] },
    });

    await waitFor(() => {
      expect(screen.getByText("Something went wrong. Please try again.")).toBeInTheDocument();
    });
    expect(onIngested).not.toHaveBeenCalled();
  });

  it("rejects non-.txt files without calling the API", async () => {
    render(<MeetingIngestUpload />);

    fireEvent.change(screen.getByLabelText("Transcript file"), {
      target: { files: [transcriptFile("2026-01-14_discovery-call.pdf")] },
    });

    await waitFor(() => {
      expect(
        screen.getByText("Only .txt transcript files are supported."),
      ).toBeInTheDocument();
    });
    expect(ingestMeeting).not.toHaveBeenCalled();
  });
});
