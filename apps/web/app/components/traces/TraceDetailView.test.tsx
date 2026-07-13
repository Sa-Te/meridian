import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getTrace } from "@/app/lib/api/client";

import { TraceDetailView } from "./TraceDetailView";

vi.mock("@/app/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/app/lib/api/client")>(
    "@/app/lib/api/client",
  );
  return {
    ...actual,
    getTrace: vi.fn(),
  };
});

describe("TraceDetailView", () => {
  beforeEach(() => {
    vi.mocked(getTrace).mockReset();
  });

  it("shows a loading state before the trace arrives", () => {
    vi.mocked(getTrace).mockReturnValue(new Promise(() => {}));

    render(<TraceDetailView traceId="t1" />);

    expect(screen.getByText("Loading trace...")).toBeInTheDocument();
  });

  it("renders the trace summary and its stage timeline", async () => {
    vi.mocked(getTrace).mockResolvedValue({
      id: "t1",
      endpoint: "POST /ask",
      stages: [
        {
          name: "hybrid_search",
          started_at: "2026-07-11T00:00:00Z",
          duration_ms: 11.2,
          metadata: {},
        },
      ],
      total_duration_ms: 641.5,
      input_tokens: 900,
      output_tokens: 95,
      models_used: ["gemini-3.1-flash-lite"],
      outcome: "answered",
      created_at: "2026-07-11T16:54:16.726462Z",
    });

    render(<TraceDetailView traceId="t1" />);

    await waitFor(() => {
      expect(screen.getByText("POST /ask")).toBeInTheDocument();
    });
    expect(screen.getByText("Answered")).toBeInTheDocument();
    expect(screen.getByText(/Total: 642 ms/)).toBeInTheDocument();
    expect(screen.getByText("hybrid_search")).toBeInTheDocument();
    expect(screen.getByText("gemini-3.1-flash-lite")).toBeInTheDocument();
  });

  it("shows a fallback label when no model was invoked", async () => {
    vi.mocked(getTrace).mockResolvedValue({
      id: "t2",
      endpoint: "POST /ask",
      stages: [],
      total_duration_ms: 12,
      input_tokens: 0,
      output_tokens: 0,
      models_used: [],
      outcome: "declined",
      created_at: "2026-07-11T16:54:16.726462Z",
    });

    render(<TraceDetailView traceId="t2" />);

    await waitFor(() => {
      expect(screen.getByText("no model invoked")).toBeInTheDocument();
    });
  });

  it("shows an error message if the trace fetch fails", async () => {
    vi.mocked(getTrace).mockRejectedValue(new Error("not found"));

    render(<TraceDetailView traceId="t1" />);

    await waitFor(() => {
      expect(screen.getByText("Something went wrong. Please try again.")).toBeInTheDocument();
    });
  });
});
