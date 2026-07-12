"use client";

import { useEffect, useState } from "react";

import { Panel } from "@/app/components/ui/Panel";
import { getTrace, toErrorMessage } from "@/app/lib/api/client";
import { formatDuration } from "@/app/lib/format";
import type { Trace } from "@/app/lib/api/types";

import { TraceOutcomeBadge } from "./TraceOutcomeBadge";
import { TraceStageTimeline } from "./TraceStageTimeline";

interface TraceDetailViewProps {
  traceId: string;
}

export function TraceDetailView({ traceId }: TraceDetailViewProps) {
  const [trace, setTrace] = useState<Trace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    // See the meetings views' identical comment: this reset is React's own
    // documented data-fetching pattern, not the case
    // react-hooks/set-state-in-effect targets. See docs/adr/0014.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);

    getTrace(traceId)
      .then((data) => {
        if (!cancelled) {
          setTrace(data);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(toErrorMessage(caught));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [traceId]);

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <Panel>
        {loading && <p className="text-sm text-muted-foreground">Loading trace...</p>}
        {error && <p className="text-sm text-danger">{error}</p>}
        {trace && (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h1 className="font-mono text-lg font-medium text-foreground">{trace.endpoint}</h1>
              <TraceOutcomeBadge outcome={trace.outcome} />
            </div>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span>Total: {formatDuration(trace.total_duration_ms)}</span>
              <span>
                {trace.input_tokens} input / {trace.output_tokens} output tokens
              </span>
              <span>{trace.models_used.join(", ") || "no model invoked"}</span>
              <span>{new Date(trace.created_at).toLocaleString()}</span>
            </div>
          </>
        )}
      </Panel>

      {trace && <TraceStageTimeline stages={trace.stages} />}
    </div>
  );
}
