"use client";

import { useState } from "react";
import type { FormEvent } from "react";

import { CitationChip } from "@/app/components/citations/CitationChip";
import { Badge } from "@/app/components/ui/Badge";
import { Button } from "@/app/components/ui/Button";
import { Input } from "@/app/components/ui/Input";
import { Panel } from "@/app/components/ui/Panel";
import { askQuestion, toErrorMessage } from "@/app/lib/api/client";
import { ENTER_TRANSITION_CLASSES } from "@/app/lib/motion";
import type { AskResponse } from "@/app/lib/api/types";

import { MeetingScopeSelect } from "./MeetingScopeSelect";

/** POST /ask returns one complete JSON response -- there is no token
 * stream to render. The citation-enforcement guardrail (ADR-0007) needs
 * the full response before it can even be validated, so a "loading"
 * state stands in for what the ROADMAP calls "streamed": pending, then
 * arrived, not token-by-token. See docs/adr/0014. */
export function ChatView() {
  const [question, setQuestion] = useState("");
  const [meetingId, setMeetingId] = useState("");
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || loading) {
      return;
    }

    setLoading(true);
    setError(null);
    setAnswer(null);

    try {
      const result = await askQuestion(trimmed, meetingId || undefined);
      setAnswer(result);
    } catch (caught) {
      setError(toErrorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <Panel>
        <h1 className="text-lg font-medium text-foreground">Ask Meridian</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Ask a question about what was discussed, decided, or assigned across your ingested
          meetings.
        </p>

        <form onSubmit={handleSubmit} className="mt-5 flex flex-col gap-3">
          <MeetingScopeSelect value={meetingId} onChange={setMeetingId} disabled={loading} />
          <div className="flex gap-2">
            <Input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="What was decided about the alert threshold?"
              disabled={loading}
              aria-label="Your question"
            />
            <Button type="submit" disabled={loading || !question.trim()}>
              {loading ? "Asking..." : "Ask"}
            </Button>
          </div>
        </form>
      </Panel>

      {loading && (
        <Panel data-testid="chat-loading" className={ENTER_TRANSITION_CLASSES}>
          <p className="text-sm text-muted-foreground">Thinking...</p>
        </Panel>
      )}

      {error && (
        <Panel data-testid="chat-error" className={ENTER_TRANSITION_CLASSES}>
          <Badge tone="danger">Error</Badge>
          <p className="mt-2 text-sm text-foreground">{error}</p>
        </Panel>
      )}

      {answer && !loading && answer.supported && (
        <Panel data-testid="chat-answer" className={ENTER_TRANSITION_CLASSES}>
          <p className="text-sm leading-relaxed text-foreground">{answer.answer}</p>
          {answer.citations.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {answer.citations.map((citation) => (
                <CitationChip key={citation.chunk_id} citation={citation} />
              ))}
            </div>
          )}
        </Panel>
      )}

      {answer && !loading && !answer.supported && (
        <Panel data-testid="chat-declined" className={ENTER_TRANSITION_CLASSES}>
          <Badge tone="neutral">Not well-supported</Badge>
          <p className="mt-2 text-sm text-muted-foreground">{answer.answer}</p>
        </Panel>
      )}
    </div>
  );
}
