import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./Button";

describe("Button", () => {
  it("renders its label", () => {
    render(<Button>Ask</Button>);

    expect(screen.getByRole("button", { name: "Ask" })).toBeInTheDocument();
  });

  it("fires onClick when clicked", () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Ask</Button>);

    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("does not fire onClick when disabled", () => {
    const handleClick = vi.fn();
    render(
      <Button disabled onClick={handleClick}>
        Ask
      </Button>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(handleClick).not.toHaveBeenCalled();
  });

  it("defaults to the primary variant's accent background", () => {
    render(<Button>Ask</Button>);

    expect(screen.getByRole("button", { name: "Ask" })).toHaveClass("bg-accent");
  });

  it("applies the secondary variant's styles when requested", () => {
    render(<Button variant="secondary">Cancel</Button>);

    expect(screen.getByRole("button", { name: "Cancel" })).toHaveClass("bg-surface-solid");
  });
});
