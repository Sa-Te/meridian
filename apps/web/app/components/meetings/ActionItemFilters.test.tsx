import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ActionItemFilters } from "./ActionItemFilters";

describe("ActionItemFilters", () => {
  it("lists the given owners plus 'All owners'", () => {
    render(
      <ActionItemFilters
        owners={["Naomi", "Dr. Vasquez"]}
        status=""
        owner=""
        onStatusChange={vi.fn()}
        onOwnerChange={vi.fn()}
      />,
    );

    expect(screen.getByRole("option", { name: "All owners" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Naomi" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Dr. Vasquez" })).toBeInTheDocument();
  });

  it("calls onStatusChange when the status filter changes", () => {
    const onStatusChange = vi.fn();
    render(
      <ActionItemFilters
        owners={[]}
        status=""
        owner=""
        onStatusChange={onStatusChange}
        onOwnerChange={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Filter action items by status"), {
      target: { value: "done" },
    });

    expect(onStatusChange).toHaveBeenCalledWith("done");
  });

  it("calls onOwnerChange when the owner filter changes", () => {
    const onOwnerChange = vi.fn();
    render(
      <ActionItemFilters
        owners={["Naomi"]}
        status=""
        owner=""
        onStatusChange={vi.fn()}
        onOwnerChange={onOwnerChange}
      />,
    );

    fireEvent.change(screen.getByLabelText("Filter action items by owner"), {
      target: { value: "Naomi" },
    });

    expect(onOwnerChange).toHaveBeenCalledWith("Naomi");
  });
});
