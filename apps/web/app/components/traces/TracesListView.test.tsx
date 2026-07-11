import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listTraces } from "@/app/lib/api/client";
import type { Trace } from "@/app/lib/api/types";

import { TracesListView } from "./TracesListView";

vi.mock("@/app/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/app/lib/api/client")>(
    "@/app/lib/api/client",
  );
  return {
    ...actual,
    listTraces: vi.fn(),
  };
});

function makeTrace(id: string, endpoint = "POST /ask"): Trace {
  return {
    id,
    endpoint,
    stages: [],
    total_duration_ms: 100,
    input_tokens: 10,
    output_tokens: 5,
    models_used: ["gemini-3.1-flash-lite"],
    outcome: "answered",
    created_at: "2026-07-11T00:00:00Z",
  };
}

describe("TracesListView", () => {
  beforeEach(() => {
    vi.mocked(listTraces).mockReset();
  });

  it("shows a loading state before traces arrive", () => {
    vi.mocked(listTraces).mockReturnValue(new Promise(() => {}));

    render(<TracesListView />);

    expect(screen.getByText("Loading traces...")).toBeInTheDocument();
  });

  it("renders fetched traces", async () => {
    vi.mocked(listTraces).mockResolvedValue({
      items: [makeTrace("t1")],
      total: 1,
      limit: 20,
      offset: 0,
    });

    render(<TracesListView />);

    await waitFor(() => {
      expect(screen.getByText("POST /ask")).toBeInTheDocument();
    });
  });

  it("re-fetches with the endpoint filter and resets to the first page", async () => {
    vi.mocked(listTraces).mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
    render(<TracesListView />);
    await waitFor(() => expect(listTraces).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText("Filter traces by endpoint"), {
      target: { value: "POST /meetings/ingest" },
    });

    await waitFor(() => {
      expect(listTraces).toHaveBeenLastCalledWith(
        expect.objectContaining({ endpoint: "POST /meetings/ingest", offset: 0 }),
      );
    });
  });

  it("shows pagination controls and pages forward", async () => {
    vi.mocked(listTraces).mockResolvedValue({
      items: [makeTrace("t1")],
      total: 25,
      limit: 20,
      offset: 0,
    });

    render(<TracesListView />);
    await waitFor(() => screen.getByText("Next"));

    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      expect(listTraces).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 20 }));
    });
  });

  it("shows an empty state when no traces match the filters", async () => {
    vi.mocked(listTraces).mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });

    render(<TracesListView />);

    await waitFor(() => {
      expect(screen.getByText("No traces match the selected filters.")).toBeInTheDocument();
    });
  });
});
