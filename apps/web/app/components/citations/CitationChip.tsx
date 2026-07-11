"use client";

import { useState } from "react";

import { Card } from "@/app/components/ui/Card";
import { formatTimestamp } from "@/app/lib/format";
import type { Citation } from "@/app/lib/api/types";

interface CitationChipProps {
  citation: Citation;
}

/** A clickable chip naming a citation's speaker and timestamp; expands
 * inline to reveal the source chunk's full text. Shared by the chat view
 * (AskResponse.citations) and the decisions/action-items view
 * (Decision/ActionItem.source_citation) -- both now carry the same
 * CitationRead shape, see docs/adr/0014. */
export function CitationChip({ citation }: CitationChipProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded((previous) => !previous)}
        aria-expanded={expanded}
        className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent-strong transition-colors hover:bg-accent/20"
      >
        <span>{citation.speaker}</span>
        <span aria-hidden="true">&middot;</span>
        <span>{formatTimestamp(citation.start_ts)}</span>
      </button>

      {expanded && (
        <Card className="mt-2 max-w-md text-sm">
          <p className="font-medium text-foreground">
            {citation.speaker}{" "}
            <span className="font-normal text-muted-foreground">
              &middot; {formatTimestamp(citation.start_ts)}
            </span>
          </p>
          <p className="mt-1 text-muted-foreground">{citation.text}</p>
        </Card>
      )}
    </div>
  );
}
