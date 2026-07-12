import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Trace } from "@/app/lib/api/types";

import { TraceListRow } from "./TraceListRow";

const trace: Trace = {
  id: "t1",
  endpoint: "POST /ask",
  stages: [],
  total_duration_ms: 641.49,
  input_tokens: 900,
  output_tokens: 95,
  models_used: ["gemini-3.1-flash-lite"],
  outcome: "answered",
  created_at: "2026-07-11T16:54:16.726462Z",
};

describe("TraceListRow", () => {
  it("renders the endpoint, outcome, latency, and token count", () => {
    render(<TraceListRow trace={trace} />);

    expect(screen.getByText("POST /ask")).toBeInTheDocument();
    expect(screen.getByText("Answered")).toBeInTheDocument();
    expect(screen.getByText("641 ms")).toBeInTheDocument();
    expect(screen.getByText("995 tokens")).toBeInTheDocument();
  });

  it("links to the trace's detail page", () => {
    render(<TraceListRow trace={trace} />);

    expect(screen.getByRole("link")).toHaveAttribute("href", "/traces/t1");
  });
});
