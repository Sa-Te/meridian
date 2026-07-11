import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Input } from "./Input";

describe("Input", () => {
  it("renders with a placeholder", () => {
    render(<Input placeholder="Ask a question..." />);

    expect(screen.getByPlaceholderText("Ask a question...")).toBeInTheDocument();
  });

  it("fires onChange with the typed value", () => {
    const handleChange = vi.fn();
    render(<Input placeholder="Ask" onChange={handleChange} />);

    fireEvent.change(screen.getByPlaceholderText("Ask"), {
      target: { value: "What was decided?" },
    });

    expect(handleChange).toHaveBeenCalledTimes(1);
    expect(screen.getByPlaceholderText("Ask")).toHaveValue("What was decided?");
  });

  it("respects the disabled attribute", () => {
    render(<Input placeholder="Ask" disabled />);

    expect(screen.getByPlaceholderText("Ask")).toBeDisabled();
  });
});
