import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { updateActionItemStatus } from "@/app/lib/api/client";
import type { ActionItem, Decision } from "@/app/lib/api/types";

import { TimelineEntryCard } from "./TimelineEntryCard";

vi.mock("@/app/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/app/lib/api/client")>(
    "@/app/lib/api/client",
  );
  return {
    ...actual,
    updateActionItemStatus: vi.fn(),
  };
});

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
  severity: "medium",
  created_at: "2026-01-29T00:00:00Z",
};

const actionItem: ActionItem = {
  id: "a1",
  meeting_id: "m1",
  text: "Send Raj the source for the forty percent figure.",
  owner: "Naomi",
  due_date: null,
  completed_at: null,
  source_citation: citation,
  confidence: 0.9,
  status: "open",
  created_at: "2026-01-29T00:00:00Z",
};

describe("TimelineEntryCard", () => {
  beforeEach(() => {
    vi.mocked(updateActionItemStatus).mockReset();
  });

  it("renders a decision with a Decision badge", () => {
    render(
      <TimelineEntryCard
        entry={{ kind: "decision", item: decision }}
        onActionItemStatusChange={() => {}}
      />,
    );

    expect(screen.getByText("Decision")).toBeInTheDocument();
    expect(screen.getByText(decision.text)).toBeInTheDocument();
  });

  it("renders an action item with its status and owner", () => {
    render(
      <TimelineEntryCard
        entry={{ kind: "action_item", item: actionItem }}
        onActionItemStatusChange={() => {}}
      />,
    );

    expect(screen.getByText("Open")).toBeInTheDocument();
    expect(screen.getByText("Naomi")).toBeInTheDocument();
    expect(screen.getByText(actionItem.text)).toBeInTheDocument();
  });

  it("renders the citation chip for the source chunk", () => {
    render(
      <TimelineEntryCard
        entry={{ kind: "decision", item: decision }}
        onActionItemStatusChange={() => {}}
      />,
    );

    expect(
      screen.getByRole("button", { name: /Dr. Vasquez/ }),
    ).toBeInTheDocument();
  });

  it("does not render a Mark Done button for an already-done action item", () => {
    render(
      <TimelineEntryCard
        entry={{ kind: "action_item", item: { ...actionItem, status: "done" } }}
        onActionItemStatusChange={() => {}}
      />,
    );

    expect(screen.queryByRole("button", { name: "Mark Done" })).not.toBeInTheDocument();
  });

  it("marks an action item done and reports the new status back to the parent", async () => {
    vi.mocked(updateActionItemStatus).mockResolvedValue({ ...actionItem, status: "done" });
    const onActionItemStatusChange = vi.fn();

    render(
      <TimelineEntryCard
        entry={{ kind: "action_item", item: actionItem }}
        onActionItemStatusChange={onActionItemStatusChange}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Mark Done" }));

    await waitFor(() => {
      expect(onActionItemStatusChange).toHaveBeenCalledWith(actionItem.id, "done");
    });
    expect(updateActionItemStatus).toHaveBeenCalledWith(
      actionItem.meeting_id,
      actionItem.id,
      "done",
    );
  });

  it("shows an error message if marking an action item done fails", async () => {
    vi.mocked(updateActionItemStatus).mockRejectedValue(new Error("network down"));

    render(
      <TimelineEntryCard
        entry={{ kind: "action_item", item: actionItem }}
        onActionItemStatusChange={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Mark Done" }));

    await waitFor(() => {
      expect(screen.getByText("Something went wrong. Please try again.")).toBeInTheDocument();
    });
  });
});
