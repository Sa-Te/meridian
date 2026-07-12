import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TraceOutcomeBadge } from "./TraceOutcomeBadge";

describe("TraceOutcomeBadge", () => {
  it("renders 'Answered' with the accent tone", () => {
    render(<TraceOutcomeBadge outcome="answered" />);

    expect(screen.getByText("Answered")).toHaveClass("text-accent-strong");
  });

  it("renders 'Declined' with the neutral tone", () => {
    render(<TraceOutcomeBadge outcome="declined" />);

    expect(screen.getByText("Declined")).toHaveClass("text-muted-foreground");
  });

  it("renders 'Error' with the danger tone", () => {
    render(<TraceOutcomeBadge outcome="error" />);

    expect(screen.getByText("Error")).toHaveClass("text-danger");
  });
});
