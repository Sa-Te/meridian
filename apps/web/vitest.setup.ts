import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// @testing-library/react's automatic cleanup only registers itself when it
// detects a global test framework; this project imports afterEach from
// "vitest" explicitly rather than relying on vitest's `globals` option, so
// it never detects one. Without this, the DOM from one test in a file
// leaks into the next.
afterEach(() => {
  cleanup();
});
