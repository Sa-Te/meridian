import { describe, expect, it } from "vitest";

import { formatDuration, formatTimestamp } from "./format";

describe("formatTimestamp", () => {
  it("formats seconds under a minute", () => {
    expect(formatTimestamp(7)).toBe("0:07");
  });

  it("formats minutes and seconds", () => {
    expect(formatTimestamp(155)).toBe("2:35");
  });

  it("formats hours, minutes, and seconds once past an hour", () => {
    expect(formatTimestamp(3725)).toBe("1:02:05");
  });
});

describe("formatDuration", () => {
  it("formats sub-second durations in milliseconds", () => {
    expect(formatDuration(42)).toBe("42 ms");
  });

  it("formats durations of a second or more in seconds", () => {
    expect(formatDuration(1240)).toBe("1.24 s");
  });
});
