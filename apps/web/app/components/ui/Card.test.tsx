import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Card } from "./Card";

describe("Card", () => {
  it("renders its children", () => {
    render(<Card>A decision</Card>);

    expect(screen.getByText("A decision")).toBeInTheDocument();
  });

  it("applies interactive hover styles only when interactive", () => {
    const { rerender } = render(<Card>Item</Card>);
    expect(screen.getByText("Item")).not.toHaveClass("cursor-pointer");

    rerender(<Card interactive>Item</Card>);
    expect(screen.getByText("Item")).toHaveClass("cursor-pointer");
  });

  it("fires onClick when clicked", () => {
    const handleClick = vi.fn();
    render(
      <Card interactive onClick={handleClick}>
        Click me
      </Card>,
    );

    fireEvent.click(screen.getByText("Click me"));

    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});
