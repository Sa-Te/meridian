import type { TraceOutcome } from "@/app/lib/api/types";

const ENDPOINT_OPTIONS = [
  { value: "", label: "All endpoints" },
  { value: "POST /ask", label: "POST /ask" },
  { value: "POST /meetings/{meeting_id}/ask", label: "POST /meetings/{id}/ask" },
  { value: "POST /meetings/ingest", label: "POST /meetings/ingest" },
];

const OUTCOME_OPTIONS: Array<{ value: TraceOutcome | ""; label: string }> = [
  { value: "", label: "All outcomes" },
  { value: "answered", label: "Answered" },
  { value: "declined", label: "Declined" },
  { value: "error", label: "Error" },
];

interface TraceFiltersProps {
  endpoint: string;
  outcome: TraceOutcome | "";
  date: string;
  onEndpointChange: (endpoint: string) => void;
  onOutcomeChange: (outcome: TraceOutcome | "") => void;
  onDateChange: (date: string) => void;
}

const controlClassName =
  "rounded-full border border-border bg-surface-solid/80 px-3 py-1.5 text-xs text-foreground outline-none focus:border-accent/50 focus:ring-2 focus:ring-accent/30";

export function TraceFilters({
  endpoint,
  outcome,
  date,
  onEndpointChange,
  onOutcomeChange,
  onDateChange,
}: TraceFiltersProps) {
  return (
    <div className="flex flex-wrap gap-2">
      <select
        aria-label="Filter traces by endpoint"
        value={endpoint}
        onChange={(event) => onEndpointChange(event.target.value)}
        className={controlClassName}
      >
        {ENDPOINT_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <select
        aria-label="Filter traces by outcome"
        value={outcome}
        onChange={(event) => onOutcomeChange(event.target.value as TraceOutcome | "")}
        className={controlClassName}
      >
        {OUTCOME_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <input
        aria-label="Filter traces by date"
        type="date"
        value={date}
        onChange={(event) => onDateChange(event.target.value)}
        className={controlClassName}
      />
    </div>
  );
}
