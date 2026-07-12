/** Types mirroring apps/api/app/models/schemas.py. Kept in one file, hand
 * -written rather than generated -- see docs/adr/0014 for why. */

export interface Citation {
  chunk_id: string;
  meeting_id: string;
  speaker: string;
  start_ts: number;
  end_ts: number;
  text: string;
}

export interface AskResponse {
  answer: string;
  supported: boolean;
  citations: Citation[];
}

export interface MeetingSummary {
  id: string;
  title: string;
  date: string;
  participants: string[];
  created_at: string;
}

export interface Decision {
  id: string;
  meeting_id: string;
  text: string;
  source_citation: Citation;
  confidence: number;
  created_at: string;
}

export type ActionItemStatus = "open" | "in_progress" | "done";

export interface ActionItem {
  id: string;
  meeting_id: string;
  text: string;
  owner: string | null;
  due_date: string | null;
  source_citation: Citation;
  confidence: number;
  status: ActionItemStatus;
  created_at: string;
}

export interface TraceStage {
  name: string;
  started_at: string;
  duration_ms: number;
  metadata: Record<string, unknown>;
}

export type TraceOutcome = "answered" | "declined" | "error";

export interface Trace {
  id: string;
  endpoint: string;
  stages: TraceStage[];
  total_duration_ms: number;
  input_tokens: number;
  output_tokens: number;
  models_used: string[];
  outcome: TraceOutcome;
  created_at: string;
}

export interface TraceListResponse {
  items: Trace[];
  total: number;
  limit: number;
  offset: number;
}

export interface PromptInjectionFinding {
  chunk_index: number;
  pattern: string;
  matched_text: string;
}

export interface IngestResponse {
  meeting_id: string;
  chunk_count: number;
  decision_count: number;
  action_item_count: number;
  flagged_for_prompt_injection: boolean;
  prompt_injection_findings: PromptInjectionFinding[];
}
