import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import Home from "./page";

describe("Home", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows ok when the API health check succeeds", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: "ok" }),
      }),
    );

    render(<Home />);

    expect(screen.getByTestId("health-status")).toHaveTextContent("Checking...");

    await waitFor(() => {
      expect(screen.getByTestId("health-status")).toHaveTextContent("ok");
    });
  });
});
