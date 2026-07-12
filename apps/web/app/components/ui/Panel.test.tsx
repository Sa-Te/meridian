import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Panel } from "./Panel";

describe("Panel", () => {
  it("renders its children", () => {
    render(<Panel>Content goes here</Panel>);

    expect(screen.getByText("Content goes here")).toBeInTheDocument();
  });

  it("merges a custom className with its base styles", () => {
    render(<Panel className="custom-class">Content</Panel>);

    const panel = screen.getByText("Content");
    expect(panel).toHaveClass("custom-class");
    expect(panel).toHaveClass("backdrop-blur-xl");
  });
});
