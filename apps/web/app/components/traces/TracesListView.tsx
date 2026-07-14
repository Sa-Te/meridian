"use client";

import { useEffect, useState } from "react";

import { Button } from "@/app/components/ui/Button";
import { Panel } from "@/app/components/ui/Panel";
import { listTraces, toErrorMessage } from "@/app/lib/api/client";
import { cn } from "@/app/lib/cn";
import { LIST_ENTER_CLASSES, staggerDelayStyle } from "@/app/lib/motion";
import type { Trace, TraceOutcome } from "@/app/lib/api/types";

import { TraceFilters } from "./TraceFilters";
import { TraceListRow } from "./TraceListRow";

const PAGE_SIZE = 20;

export function TracesListView() {
  const [endpoint, setEndpoint] = useState("");
  const [outcome, setOutcome] = useState<TraceOutcome | "">("");
  const [date, setDate] = useState("");
  const [offset, setOffset] = useState(0);

  const [traces, setTraces] = useState<Trace[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    // See docs/adr/0014 on the meetings views for why this synchronous
    // reset is intentional, not the pattern react-hooks/set-state-in-effect
    // targets.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);

    listTraces({
      endpoint: endpoint || undefined,
      outcome: outcome || undefined,
      date: date || undefined,
      limit: PAGE_SIZE,
      offset,
    })
      .then((result) => {
        if (!cancelled) {
          setTraces(result.items);
          setTotal(result.total);
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
  }, [endpoint, outcome, date, offset]);

  function resetToFirstPage<T>(setFilter: (value: T) => void) {
    return (value: T) => {
      setFilter(value);
      setOffset(0);
    };
  }

  const hasPrevious = offset > 0;
  const hasNext = offset + PAGE_SIZE < total;

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <Panel>
        <h1 className="text-lg font-medium text-foreground">Traces</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Every ask and ingest request Meridian has processed, stage by stage.
        </p>
        <div className="mt-4">
          <TraceFilters
            endpoint={endpoint}
            outcome={outcome}
            date={date}
            onEndpointChange={resetToFirstPage(setEndpoint)}
            onOutcomeChange={resetToFirstPage(setOutcome)}
            onDateChange={resetToFirstPage(setDate)}
          />
        </div>
      </Panel>

      {loading && <p className="text-sm text-muted-foreground">Loading traces...</p>}
      {error && <p className="text-sm text-danger">{error}</p>}
      {!loading && !error && traces.length === 0 && (
        <p className="text-sm text-muted-foreground">No traces match the selected filters.</p>
      )}

      <div
        className={cn(
          "flex flex-col gap-3 transition-opacity duration-[var(--duration-base)] ease-[var(--ease-out)]",
          loading && "opacity-40",
        )}
      >
        {traces.map((trace, index) => (
          <div key={trace.id} className={LIST_ENTER_CLASSES} style={staggerDelayStyle(index)}>
            <TraceListRow trace={trace} />
          </div>
        ))}
      </div>

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between">
          <Button
            type="button"
            variant="secondary"
            disabled={!hasPrevious}
            onClick={() => setOffset((previous) => Math.max(0, previous - PAGE_SIZE))}
          >
            Previous
          </Button>
          <span className="text-xs text-muted-foreground">
            {offset + 1}-{Math.min(offset + PAGE_SIZE, total)} of {total}
          </span>
          <Button
            type="button"
            variant="secondary"
            disabled={!hasNext}
            onClick={() => setOffset((previous) => previous + PAGE_SIZE)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
