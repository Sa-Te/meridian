import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Citation } from "@/app/lib/api/types";

import { CitationChip } from "./CitationChip";

const citation: Citation = {
  chunk_id: "11111111-1111-1111-1111-111111111111",
  meeting_id: "22222222-2222-2222-2222-222222222222",
  speaker: "Naomi",
  start_ts: 155,
  end_ts: 170,
  text: "I'd want at least five to seven logged workouts with heart rate data.",
};

describe("CitationChip", () => {
  it("renders the speaker and formatted timestamp, collapsed by default", () => {
    render(<CitationChip citation={citation} />);

    expect(screen.getByText("Naomi")).toBeInTheDocument();
    expect(screen.getByText("2:35")).toBeInTheDocument();
    expect(screen.queryByText(citation.text)).not.toBeInTheDocument();
  });

  it("reveals the source chunk text when clicked", () => {
    render(<CitationChip citation={citation} />);

    fireEvent.click(screen.getByRole("button"));

    expect(screen.getByText(citation.text)).toBeInTheDocument();
  });

  it("collapses again on a second click", () => {
    render(<CitationChip citation={citation} />);

    const button = screen.getByRole("button");
    fireEvent.click(button);
    expect(screen.getByText(citation.text)).toBeInTheDocument();

    fireEvent.click(button);
    expect(screen.queryByText(citation.text)).not.toBeInTheDocument();
  });
});
