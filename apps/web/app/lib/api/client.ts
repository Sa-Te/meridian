import type {
  ActionItem,
  AskResponse,
  Decision,
  IngestResponse,
  MeetingSummary,
  Trace,
  TraceListResponse,
  TraceOutcome,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Converts anything a failed fetch might throw into a display-ready
 * message, for the `fail()` branch of useAsyncState's catch handlers. */
export function toErrorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
}

/** Reads the FastAPI `{"detail": "..."}` shape off a failed response, for
 * both request() and any caller (like ingestMeeting) that can't use
 * request() because it forces a JSON Content-Type. */
async function extractErrorDetail(response: Response): Promise<string> {
  const body: unknown = await response.json().catch(() => null);
  return body !== null && typeof body === "object" && "detail" in body && typeof body.detail === "string"
    ? body.detail
    : response.statusText;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    throw new ApiError(response.status, await extractErrorDetail(response));
  }

  return response.json() as Promise<T>;
}

export function askQuestion(question: string, meetingId?: string): Promise<AskResponse> {
  const path = meetingId ? `/meetings/${meetingId}/ask` : "/ask";
  return request<AskResponse>(path, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

export function listMeetings(): Promise<MeetingSummary[]> {
  return request<MeetingSummary[]>("/meetings");
}

/** Multipart upload, so this can't go through request(): that helper always
 * sends Content-Type: application/json, but a browser-built FormData needs
 * its own multipart boundary set by fetch itself. */
export async function ingestMeeting(file: File): Promise<IngestResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_URL}/meetings/ingest`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new ApiError(response.status, await extractErrorDetail(response));
  }

  return response.json() as Promise<IngestResponse>;
}

export function getMeeting(meetingId: string): Promise<MeetingSummary> {
  return request<MeetingSummary>(`/meetings/${meetingId}`);
}

export function listMeetingDecisions(meetingId: string): Promise<Decision[]> {
  return request<Decision[]>(`/meetings/${meetingId}/decisions`);
}

export function listMeetingActionItems(meetingId: string): Promise<ActionItem[]> {
  return request<ActionItem[]>(`/meetings/${meetingId}/action-items`);
}

export interface ListTracesParams {
  endpoint?: string;
  outcome?: TraceOutcome;
  date?: string;
  limit?: number;
  offset?: number;
}

export function listTraces(params: ListTracesParams = {}): Promise<TraceListResponse> {
  const query = new URLSearchParams();
  if (params.endpoint) query.set("endpoint", params.endpoint);
  if (params.outcome) query.set("outcome", params.outcome);
  if (params.date) query.set("date", params.date);
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.offset !== undefined) query.set("offset", String(params.offset));
  const queryString = query.toString();
  return request<TraceListResponse>(`/traces${queryString ? `?${queryString}` : ""}`);
}

export function getTrace(traceId: string): Promise<Trace> {
  return request<Trace>(`/traces/${traceId}`);
}
