import fs from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

/** The primary happy path (ROADMAP.md Phase 7, item 5): ingest a
 * transcript, ask a question, see a cited answer, view the decisions/
 * action items for that meeting, view its trace. Ingestion happens via a
 * direct API call rather than a UI upload flow -- there is no "ingest a
 * transcript" screen in this phase's scope (see docs/adr/0014), and the
 * ROADMAP explicitly allows "or use seeded data" for this step.
 */

const API_URL = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";
const TRANSCRIPT_PATH = path.resolve(
  __dirname,
  "../../../data/transcripts/2026-01-29_clinical-advisory-alert-thresholds.txt",
);

test("ingest, ask, review decisions/action items, and view the trace", async ({
  page,
  request,
}) => {
  const ingestResponse = await request.post(`${API_URL}/meetings/ingest`, {
    multipart: {
      file: {
        name: path.basename(TRANSCRIPT_PATH),
        mimeType: "text/plain",
        buffer: fs.readFileSync(TRANSCRIPT_PATH),
      },
    },
  });
  expect(ingestResponse.ok()).toBe(true);
  const ingestBody = (await ingestResponse.json()) as { meeting_id: string };
  const meetingId = ingestBody.meeting_id;

  await page.goto("/");
  await page
    .getByLabel("Your question")
    .fill(
      "How many logged workouts with heart rate data are needed before a personal baseline is trusted?",
    );
  await page.getByRole("button", { name: "Ask" }).click();

  const answerPanel = page.getByTestId("chat-answer");
  await expect(answerPanel).toBeVisible({ timeout: 30_000 });
  await expect(answerPanel).toContainText(/five to seven/i);

  const citationChip = answerPanel.getByRole("button").first();
  await citationChip.click();
  await expect(citationChip).toHaveAttribute("aria-expanded", "true");

  await page.goto(`/meetings/${meetingId}`);
  await expect(
    page.getByRole("heading", { name: "Clinical Advisory Alert Thresholds" }),
  ).toBeVisible();
  await expect(page.getByText("Decision").first()).toBeVisible();

  await page.goto("/traces");
  // Scoped to links (the clickable trace rows) rather than a bare text
  // match, which would also match the "POST /ask" <option> in the
  // endpoint filter dropdown above the list.
  const askTraceRow = page.getByRole("link").filter({ hasText: "POST /ask" }).first();
  await expect(askTraceRow).toBeVisible();
  await askTraceRow.click();

  await expect(page).toHaveURL(/\/traces\/.+/);
  await expect(page.getByText("hybrid_search")).toBeVisible();
  await expect(page.getByText("generate_answer")).toBeVisible();
});
