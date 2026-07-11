import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Nav } from "./Nav";

const { usePathname } = vi.hoisted(() => ({ usePathname: vi.fn() }));

vi.mock("next/navigation", () => ({ usePathname }));

describe("Nav", () => {
  it("renders links to Chat, Meetings, and Traces", () => {
    usePathname.mockReturnValue("/");
    render(<Nav />);

    expect(screen.getByRole("link", { name: "Chat" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Meetings" })).toHaveAttribute("href", "/meetings");
    expect(screen.getByRole("link", { name: "Traces" })).toHaveAttribute("href", "/traces");
  });

  it("marks the current section as active via aria-current", () => {
    usePathname.mockReturnValue("/meetings");
    render(<Nav />);

    expect(screen.getByRole("link", { name: "Meetings" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Chat" })).not.toHaveAttribute("aria-current");
  });

  it("treats a nested meeting detail route as within the Meetings section", () => {
    usePathname.mockReturnValue("/meetings/abc-123");
    render(<Nav />);

    expect(screen.getByRole("link", { name: "Meetings" })).toHaveAttribute("aria-current", "page");
  });
});
