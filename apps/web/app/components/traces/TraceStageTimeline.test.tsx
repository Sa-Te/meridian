import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { TraceStage } from "@/app/lib/api/types";

import { TraceStageTimeline } from "./TraceStageTimeline";

describe("TraceStageTimeline", () => {
  it("shows a message when there are no stages", () => {
    render(<TraceStageTimeline stages={[]} />);

    expect(screen.getByText("No stages were recorded for this trace.")).toBeInTheDocument();
  });

  it("renders each stage's name, duration, and metadata", () => {
    const stages: TraceStage[] = [
      {
        name: "hybrid_search",
        started_at: "2026-07-11T16:54:16.724048Z",
        duration_ms: 11.19,
        metadata: { top_k: 8, retrieved_count: 3 },
      },
      {
        name: "llm_generate",
        started_at: "2026-07-11T16:54:16.735Z",
        duration_ms: 577.4,
        metadata: { model: "gemini-3.1-flash-lite" },
      },
    ];

    render(<TraceStageTimeline stages={stages} />);

    expect(screen.getByText("hybrid_search")).toBeInTheDocument();
    expect(screen.getByText("11 ms")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("llm_generate")).toBeInTheDocument();
    expect(screen.getByText("gemini-3.1-flash-lite")).toBeInTheDocument();
  });

  it("renders stages in the given order", () => {
    const stages: TraceStage[] = [
      { name: "first", started_at: "t", duration_ms: 1, metadata: {} },
      { name: "second", started_at: "t", duration_ms: 2, metadata: {} },
    ];

    render(<TraceStageTimeline stages={stages} />);

    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("first");
    expect(items[1]).toHaveTextContent("second");
  });
});
