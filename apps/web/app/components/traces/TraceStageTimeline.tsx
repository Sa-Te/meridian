import { Card } from "@/app/components/ui/Card";
import { formatDuration } from "@/app/lib/format";
import { LIST_ENTER_CLASSES, staggerDelayStyle } from "@/app/lib/motion";
import type { TraceStage } from "@/app/lib/api/types";

interface TraceStageTimelineProps {
  stages: TraceStage[];
}

/** The stage-by-stage breakdown of one traced request -- the observability
 * story from Phase 6 (docs/adr/0010) made visible. Rendered in the order
 * stages were recorded, which (per ADR-0010) already reads as a natural
 * nesting: a stage that triggered nested provider calls appears after
 * them, since the outer span only closes once they're done. */
export function TraceStageTimeline({ stages }: TraceStageTimelineProps) {
  if (stages.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No stages were recorded for this trace.</p>
    );
  }

  return (
    <ol className="flex flex-col gap-3">
      {stages.map((stage, index) => (
        <li
          key={`${stage.name}-${index}`}
          className={LIST_ENTER_CLASSES}
          style={staggerDelayStyle(index)}
        >
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-mono text-sm text-foreground">{stage.name}</span>
              <span className="text-xs text-muted-foreground">
                {formatDuration(stage.duration_ms)}
              </span>
            </div>
            {Object.keys(stage.metadata).length > 0 && (
              <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                {Object.entries(stage.metadata).map(([key, value]) => (
                  <div key={key} className="flex gap-1">
                    <dt className="font-medium">{key}:</dt>
                    <dd>{String(value)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </Card>
        </li>
      ))}
    </ol>
  );
}
