"use client";

import { useRef, useState, type ChangeEvent } from "react";

import { Badge } from "@/app/components/ui/Badge";
import { Button } from "@/app/components/ui/Button";
import { Panel } from "@/app/components/ui/Panel";
import { ingestMeeting, toErrorMessage } from "@/app/lib/api/client";
import type { IngestResponse } from "@/app/lib/api/types";

type UploadStatus = "idle" | "uploading" | "success" | "error";

type MeetingIngestUploadProps = {
  /** Called once a transcript has been ingested successfully, so the
   * caller can refresh whatever meetings list it's showing. */
  onIngested?: () => void;
};

export function MeetingIngestUpload({ onIngested }: MeetingIngestUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [fileName, setFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IngestResponse | null>(null);

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    // Clear the input immediately so re-selecting the same file (e.g. after
    // fixing a naming issue and re-uploading) still fires onChange.
    event.target.value = "";
    if (!file) {
      return;
    }

    setFileName(file.name);
    setResult(null);

    if (!file.name.toLowerCase().endsWith(".txt")) {
      setStatus("error");
      setError("Only .txt transcript files are supported.");
      return;
    }

    setStatus("uploading");
    setError(null);

    try {
      const response = await ingestMeeting(file);
      setResult(response);
      setStatus("success");
      onIngested?.();
    } catch (caught: unknown) {
      setError(toErrorMessage(caught));
      setStatus("error");
    }
  }

  return (
    <Panel>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-sm font-medium text-foreground">Ingest a transcript</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Upload a .txt transcript using the seed data naming convention (e.g.
            2026-01-14_discovery-call.txt).
          </p>
        </div>

        <Button
          type="button"
          disabled={status === "uploading"}
          onClick={() => inputRef.current?.click()}
        >
          {status === "uploading" ? "Uploading..." : "Upload transcript"}
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept=".txt,text/plain"
          aria-label="Transcript file"
          className="sr-only"
          disabled={status === "uploading"}
          onChange={handleFileChange}
        />
      </div>

      {status === "uploading" && fileName && (
        <p className="mt-4 text-sm text-muted-foreground">Uploading {fileName}...</p>
      )}

      {status === "success" && result && (
        <div className="mt-4 flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="accent">Ingested</Badge>
            {result.flagged_for_prompt_injection && (
              <Badge tone="danger">Flagged for review</Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground">
            {result.chunk_count} chunks &middot; {result.decision_count} decisions &middot;{" "}
            {result.action_item_count} action items.
          </p>
        </div>
      )}

      {status === "error" && error && <p className="mt-4 text-sm text-danger">{error}</p>}
    </Panel>
  );
}
