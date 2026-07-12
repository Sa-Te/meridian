import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TraceFilters } from "./TraceFilters";

describe("TraceFilters", () => {
  it("calls onEndpointChange when the endpoint filter changes", () => {
    const onEndpointChange = vi.fn();
    render(
      <TraceFilters
        endpoint=""
        outcome=""
        date=""
        onEndpointChange={onEndpointChange}
        onOutcomeChange={vi.fn()}
        onDateChange={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Filter traces by endpoint"), {
      target: { value: "POST /ask" },
    });

    expect(onEndpointChange).toHaveBeenCalledWith("POST /ask");
  });

  it("calls onOutcomeChange when the outcome filter changes", () => {
    const onOutcomeChange = vi.fn();
    render(
      <TraceFilters
        endpoint=""
        outcome=""
        date=""
        onEndpointChange={vi.fn()}
        onOutcomeChange={onOutcomeChange}
        onDateChange={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Filter traces by outcome"), {
      target: { value: "error" },
    });

    expect(onOutcomeChange).toHaveBeenCalledWith("error");
  });

  it("calls onDateChange when the date filter changes", () => {
    const onDateChange = vi.fn();
    render(
      <TraceFilters
        endpoint=""
        outcome=""
        date=""
        onEndpointChange={vi.fn()}
        onOutcomeChange={vi.fn()}
        onDateChange={onDateChange}
      />,
    );

    fireEvent.change(screen.getByLabelText("Filter traces by date"), {
      target: { value: "2026-01-29" },
    });

    expect(onDateChange).toHaveBeenCalledWith("2026-01-29");
  });
});
