import Link from "next/link";

import { Card } from "@/app/components/ui/Card";
import { formatDuration } from "@/app/lib/format";
import type { Trace } from "@/app/lib/api/types";

import { TraceOutcomeBadge } from "./TraceOutcomeBadge";

interface TraceListRowProps {
  trace: Trace;
}

export function TraceListRow({ trace }: TraceListRowProps) {
  return (
    <Link href={`/traces/${trace.id}`}>
      <Card interactive>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="font-mono text-sm text-foreground">{trace.endpoint}</span>
          <TraceOutcomeBadge outcome={trace.outcome} />
        </div>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>{formatDuration(trace.total_duration_ms)}</span>
          <span>{trace.input_tokens + trace.output_tokens} tokens</span>
          <span>{new Date(trace.created_at).toLocaleString()}</span>
        </div>
      </Card>
    </Link>
  );
}
