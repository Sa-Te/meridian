import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Badge } from "./Badge";

describe("Badge", () => {
  it("renders its text", () => {
    render(<Badge>open</Badge>);

    expect(screen.getByText("open")).toBeInTheDocument();
  });

  it("defaults to the neutral tone", () => {
    render(<Badge>open</Badge>);

    expect(screen.getByText("open")).toHaveClass("text-muted-foreground");
  });

  it("applies the danger tone when requested", () => {
    render(<Badge tone="danger">error</Badge>);

    expect(screen.getByText("error")).toHaveClass("text-danger");
  });

  it("applies the accent tone when requested", () => {
    render(<Badge tone="accent">answered</Badge>);

    expect(screen.getByText("answered")).toHaveClass("text-accent-strong");
  });
});
