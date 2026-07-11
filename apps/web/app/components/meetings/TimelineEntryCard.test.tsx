import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ActionItem, Decision } from "@/app/lib/api/types";

import { TimelineEntryCard } from "./TimelineEntryCard";

const citation = {
  chunk_id: "c1",
  meeting_id: "m1",
  speaker: "Dr. Vasquez",
  start_ts: 200,
  end_ts: 210,
  text: "We alert when heart rate exceeds baseline by forty percent.",
};

const decision: Decision = {
  id: "d1",
  meeting_id: "m1",
  text: "Move to a baseline-relative alert threshold.",
  source_citation: citation,
  confidence: 0.9,
  created_at: "2026-01-29T00:00:00Z",
};

const actionItem: ActionItem = {
  id: "a1",
  meeting_id: "m1",
  text: "Send Raj the source for the forty percent figure.",
  owner: "Naomi",
  due_date: null,
  source_citation: citation,
  confidence: 0.9,
  status: "open",
  created_at: "2026-01-29T00:00:00Z",
};

describe("TimelineEntryCard", () => {
  it("renders a decision with a Decision badge", () => {
    render(<TimelineEntryCard entry={{ kind: "decision", item: decision }} />);

    expect(screen.getByText("Decision")).toBeInTheDocument();
    expect(screen.getByText(decision.text)).toBeInTheDocument();
  });

  it("renders an action item with its status and owner", () => {
    render(<TimelineEntryCard entry={{ kind: "action_item", item: actionItem }} />);

    expect(screen.getByText("Open")).toBeInTheDocument();
    expect(screen.getByText("Naomi")).toBeInTheDocument();
    expect(screen.getByText(actionItem.text)).toBeInTheDocument();
  });

  it("renders the citation chip for the source chunk", () => {
    render(<TimelineEntryCard entry={{ kind: "decision", item: decision }} />);

    expect(screen.getByRole("button", { name: /Dr. Vasquez/ })).toBeInTheDocument();
  });
});
