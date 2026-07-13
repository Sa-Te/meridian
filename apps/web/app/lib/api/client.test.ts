import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  askQuestion,
  getMeeting,
  getTrace,
  ingestMeeting,
  listMeetingActionItems,
  listMeetingDecisions,
  listMeetings,
  listTraces,
  toErrorMessage,
} from "./client";

function jsonResponse(body: unknown, init: { status?: number; statusText?: string } = {}) {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    statusText: init.statusText,
    headers: { "Content-Type": "application/json" },
  });
}

describe("client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe("request-backed calls", () => {
    it("sends a JSON content-type header and returns the parsed body", async () => {
      vi.mocked(fetch).mockResolvedValue(jsonResponse([{ id: "m1" }]));

      const result = await listMeetings();

      expect(result).toEqual([{ id: "m1" }]);
      const [url, init] = vi.mocked(fetch).mock.calls[0];
      expect(url).toBe("http://localhost:8000/meetings");
      expect((init?.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    });

    it("throws an ApiError carrying the FastAPI detail message on failure", async () => {
      vi.mocked(fetch).mockResolvedValue(
        jsonResponse({ detail: "Meeting not found." }, { status: 404 }),
      );

      await expect(getMeeting("missing-id")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
        message: "Meeting not found.",
      });
    });

    it("falls back to statusText when the failed response has no JSON detail", async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response("not json", { status: 500, statusText: "Internal Server Error" }),
      );

      await expect(listMeetings()).rejects.toMatchObject({
        status: 500,
        message: "Internal Server Error",
      });
    });

    it("falls back to statusText when the error body is JSON but has no string detail", async () => {
      vi.mocked(fetch).mockResolvedValue(
        jsonResponse({ oops: true }, { status: 400, statusText: "Bad Request" }),
      );

      await expect(listMeetings()).rejects.toMatchObject({
        status: 400,
        message: "Bad Request",
      });
    });
  });

  describe("askQuestion", () => {
    it("posts to the global /ask endpoint when no meeting is scoped", async () => {
      vi.mocked(fetch).mockResolvedValue(
        jsonResponse({ answer: "ok", supported: true, citations: [] }),
      );

      await askQuestion("What was decided?");

      const [url, init] = vi.mocked(fetch).mock.calls[0];
      expect(url).toBe("http://localhost:8000/ask");
      expect(JSON.parse(init?.body as string)).toEqual({ question: "What was decided?" });
    });

    it("posts to the meeting-scoped ask endpoint when a meetingId is given", async () => {
      vi.mocked(fetch).mockResolvedValue(
        jsonResponse({ answer: "ok", supported: true, citations: [] }),
      );

      await askQuestion("What was decided?", "m1");

      const [url] = vi.mocked(fetch).mock.calls[0];
      expect(url).toBe("http://localhost:8000/meetings/m1/ask");
    });
  });

  describe("ingestMeeting", () => {
    it("uploads the file as multipart form data without a manual Content-Type", async () => {
      vi.mocked(fetch).mockResolvedValue(
        jsonResponse({
          meeting_id: "m1",
          chunk_count: 1,
          decision_count: 0,
          action_item_count: 0,
          flagged_for_prompt_injection: false,
          prompt_injection_findings: [],
        }),
      );
      const file = new File(["hello"], "2026-01-14_call.txt", { type: "text/plain" });

      await ingestMeeting(file);

      const [url, init] = vi.mocked(fetch).mock.calls[0];
      expect(url).toBe("http://localhost:8000/meetings/ingest");
      expect(init?.body).toBeInstanceOf(FormData);
      expect((init?.headers as Record<string, string> | undefined)?.["Content-Type"]).toBeUndefined();
    });

    it("throws an ApiError with the detail message on a failed upload", async () => {
      vi.mocked(fetch).mockResolvedValue(
        jsonResponse({ detail: "Transcript file must be UTF-8 text." }, { status: 422 }),
      );
      const file = new File(["hello"], "2026-01-14_call.txt", { type: "text/plain" });

      await expect(ingestMeeting(file)).rejects.toMatchObject({
        status: 422,
        message: "Transcript file must be UTF-8 text.",
      });
    });
  });

  describe("listTraces query-string building", () => {
    it("requests /traces with no query string when no params are given", async () => {
      vi.mocked(fetch).mockResolvedValue(jsonResponse({ items: [], total: 0, limit: 20, offset: 0 }));

      await listTraces();

      const [url] = vi.mocked(fetch).mock.calls[0];
      expect(url).toBe("http://localhost:8000/traces");
    });

    it("includes only the params that were actually provided", async () => {
      vi.mocked(fetch).mockResolvedValue(jsonResponse({ items: [], total: 0, limit: 20, offset: 0 }));

      await listTraces({ endpoint: "POST /ask", offset: 20 });

      const [url] = vi.mocked(fetch).mock.calls[0];
      expect(url).toBe("http://localhost:8000/traces?endpoint=POST+%2Fask&offset=20");
    });

    it("includes every param when all are provided", async () => {
      vi.mocked(fetch).mockResolvedValue(jsonResponse({ items: [], total: 0, limit: 20, offset: 0 }));

      await listTraces({
        endpoint: "POST /ask",
        outcome: "answered",
        date: "2026-01-29",
        limit: 10,
        offset: 0,
      });

      const [url] = vi.mocked(fetch).mock.calls[0];
      const parsed = new URL(url as string);
      expect(parsed.pathname).toBe("/traces");
      expect(parsed.searchParams.get("endpoint")).toBe("POST /ask");
      expect(parsed.searchParams.get("outcome")).toBe("answered");
      expect(parsed.searchParams.get("date")).toBe("2026-01-29");
      expect(parsed.searchParams.get("limit")).toBe("10");
      expect(parsed.searchParams.get("offset")).toBe("0");
    });
  });

  describe("other thin wrappers", () => {
    it("getTrace requests /traces/{id}", async () => {
      vi.mocked(fetch).mockResolvedValue(jsonResponse({ id: "t1" }));

      await getTrace("t1");

      expect(vi.mocked(fetch).mock.calls[0][0]).toBe("http://localhost:8000/traces/t1");
    });

    it("listMeetingDecisions and listMeetingActionItems request the right sub-resources", async () => {
      // A fresh Response per call -- mockResolvedValue would reuse one
      // Response instance across both calls, and a body can only be read once.
      vi.mocked(fetch).mockImplementation(async () => jsonResponse([]));

      await listMeetingDecisions("m1");
      await listMeetingActionItems("m1");

      expect(vi.mocked(fetch).mock.calls[0][0]).toBe("http://localhost:8000/meetings/m1/decisions");
      expect(vi.mocked(fetch).mock.calls[1][0]).toBe(
        "http://localhost:8000/meetings/m1/action-items",
      );
    });
  });

  describe("toErrorMessage", () => {
    it("returns the ApiError's own message", () => {
      expect(toErrorMessage(new ApiError(404, "Meeting not found."))).toBe("Meeting not found.");
    });

    it("returns a generic message for any non-ApiError value", () => {
      expect(toErrorMessage(new Error("network down"))).toBe(
        "Something went wrong. Please try again.",
      );
      expect(toErrorMessage("a plain string")).toBe("Something went wrong. Please try again.");
    });
  });
});
