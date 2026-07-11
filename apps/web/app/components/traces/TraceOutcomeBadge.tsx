import { Badge } from "@/app/components/ui/Badge";
import type { TraceOutcome } from "@/app/lib/api/types";

const OUTCOME_LABEL: Record<TraceOutcome, string> = {
  answered: "Answered",
  declined: "Declined",
  error: "Error",
};

const OUTCOME_TONE: Record<TraceOutcome, "accent" | "neutral" | "danger"> = {
  answered: "accent",
  declined: "neutral",
  error: "danger",
};

export function TraceOutcomeBadge({ outcome }: { outcome: TraceOutcome }) {
  return <Badge tone={OUTCOME_TONE[outcome]}>{OUTCOME_LABEL[outcome]}</Badge>;
}
