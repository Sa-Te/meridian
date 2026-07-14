# Manual QA walkthrough

A click-by-click script for testing the running app end to end in a browser,
covering every user-facing feature: text and audio meeting ingest, asking a
question (both a known-answer question and a deliberately out-of-scope one),
the decisions/action-items timeline, the traces dashboard, and the MCP
server tools.

No code-reading required to follow this — every step says exactly what to
click, type, or upload, and exactly what you should see back. Every step
below, including the MCP section, was verified against a live stack while
writing this document.

## Before you start

1. From a clean checkout, run `cp .env.example .env` and fill in
   `GEMINI_API_KEY` (required for every step below) and `HF_TOKEN` (required
   only for Step 25, audio ingest). See the root `README.md`'s "Quick setup"
   section for where to get each one.
2. Run `docker compose up` and wait for all four services to report healthy.
3. Open two browser tabs:
   - **Web app**: `http://localhost:3000`
   - **API docs** (FastAPI's Swagger UI — you'll need this once, for audio
     ingest in Step 25, since there is no web UI for it): `http://localhost:8000/docs`
4. If this is not a freshly-seeded database, some steps below (particularly
   "expect the Meetings list to be empty") will instead show whatever was
   ingested previously. That's fine — the rest of each step's expected
   result still holds, it just won't be the *only* thing on the page.

---

## Part 1 — Ingest a text transcript

1. In the web app, click **Meetings** in the top nav.
   **Expect:** the page header "Meetings", a subtitle, an "Ingest a
   transcript" panel with an "Upload transcript" button, and (on a clean
   database) the text "No meetings have been ingested yet." below it.
2. Click **Upload transcript**. In the file picker, navigate to
   `data/transcripts/` in this repo and select
   `2026-01-29_clinical-advisory-alert-thresholds.txt`.
   **Expect:** the button briefly reads "Uploading..." and a line appears:
   "Uploading 2026-01-29_clinical-advisory-alert-thresholds.txt...".
3. Wait a few seconds for ingestion to finish.
   **Expect:** a green-toned "Ingested" badge appears, followed by a line
   reading **"40 chunks · 2 decisions · 4 action items."** (these exact
   numbers are what this specific transcript produces — if you see
   materially different counts, something about extraction has changed).
   No "Flagged for review" badge should appear next to it.
4. Look below the upload panel.
   **Expect:** a new card titled **"Clinical Advisory Alert Thresholds"**,
   subtitled "2026-01-29 · Dhruvisha, Dr. Mehta, Dr. Vasquez, Naomi".
5. Click that card.
   **Expect:** you land on a meeting detail page showing the same title and
   date/participants line at the top, and a timeline below it (Part 3
   covers what's in that timeline).

## Part 2 — Ask a question

6. Click **Chat** in the top nav.
   **Expect:** the page header "Ask Meridian", a meeting-scope dropdown
   (defaulted to "All meetings"), a text input placeholder "What was
   decided about the alert threshold?", and an "Ask" button (disabled while
   the input is empty).
7. Click the meeting-scope dropdown and select **"Clinical Advisory Alert
   Thresholds"** (the meeting you just ingested). This scopes the question
   to only that meeting's transcript, so your result matches this script
   exactly instead of also pulling from anything else you've ingested.
8. Click the text input and type exactly:
   **How many logged workouts with heart rate data are needed before a
   personal baseline is trusted?**
9. Click **Ask**.
   **Expect:** the button reads "Asking...", then a panel appears reading
   "Thinking...", then that's replaced by an answer panel. The answer text
   should state that **at least five to seven logged workouts with heart
   rate data** are needed before a personal baseline is trusted (the exact
   wording may vary slightly since this is LLM-generated, but that number
   and claim must be present). Below the answer, one citation chip should
   read **"Naomi · 2:35"**.
10. Click that citation chip.
    **Expect:** it expands in place to show "Naomi · 2:35" again as a
    heading, followed by the source excerpt: "I'd want at least five to
    seven logged workouts with heart rate data before we trust a personal
    baseline. Before that, we'd have to fall back to something
    conservative."
11. Click the same chip again.
    **Expect:** the excerpt collapses and disappears immediately.

## Part 3 — Ask an out-of-scope question (the decline path)

12. Still on the Chat page, with the same meeting still selected in the
    scope dropdown, clear the input and type exactly:
    **What is the capital of France?**
13. Click **Ask**.
    **Expect:** after "Thinking...", a *visually distinct* panel appears —
    a neutral-toned "Not well-supported" badge, followed by text stating
    the provided transcript excerpts don't contain information about the
    capital of France (or equivalent wording). **No citations should
    appear**, and this panel must look different from Step 9's answer panel
    (no citation chips, different badge), not just contain different text.
    This is the confidence guardrail declining to answer rather than
    guessing — see `docs/adr/0007`.

## Part 4 — Decisions and action items timeline

14. Click **Meetings** in the nav, then click into the **"Clinical Advisory
    Alert Thresholds"** meeting again (or use the browser back button twice
    from Step 11).
15. Scroll the timeline below the meeting header.
    **Expect:** a mix of entries in chronological order (by when they were
    said in the meeting, not extraction order):
    - Two entries tagged with an accent **"Decision"** badge. One should be
      the alert-threshold logic decision ("moves from a flat 160 threshold
      to a patient-specific baseline plus 40 percent, sustained for three
      minutes..."); the other should be the sign-off rule ("No patient-
      facing alert changes will be released without final sign-off...").
    - Four entries tagged **"Open"** (action items), each with an owner
      name shown next to the badge (Dr. Mehta, Dr. Vasquez, Dr. Mehta,
      Naomi across the four).
16. Click any entry's citation chip.
    **Expect:** same expand behavior as Steps 10-11 — it reveals the
    speaker, timestamp, and exact excerpt that entry was extracted from.

## Part 5 — Filter action items

17. On the same meeting detail page, find the two filter dropdowns above
    the timeline: "Filter action items by status" and "Filter action items
    by owner".
18. Set the status filter to **"Open"**.
    **Expect:** all four action items remain visible (they're all "Open"
    today) and the two decisions remain visible too — decisions are never
    filtered, only action items.
19. Set the status filter to **"In progress"**, then to **"Done"**.
    **Expect, for both:** all four action items disappear, and the text "No
    action items match the selected filters." appears. The two decisions
    stay visible (decisions are never filtered). **This is expected, not a
    bug**, and it will look the same for *every* meeting you test, not just
    this one: nothing anywhere in the current system can ever set an action
    item's status to anything but "open" — there's no status-change control
    in the UI and no API endpoint for it (confirmed by grep across the
    whole backend). So "In progress" and "Done" will always show zero
    action items today, no matter which meeting or how much data you
    ingest. The filter logic itself is correct; the gap is that nothing can
    ever produce data the other two options would match.
20. Reset the status filter to **"All statuses"**, then set the owner
    filter to **"Dr. Mehta"**.
    **Expect:** only the two action items owned by Dr. Mehta remain (the
    ACSM sanity-check item and the arrhythmia policy item); the other two
    owners' items disappear, decisions stay visible.
21. Reset the owner filter to **"All owners"** before moving on.

## Part 6 — Audio ingest (via the API docs page, not the web app)

There is currently no upload-audio control anywhere in the web app — only
`.txt` files are accepted on the Meetings page (see the "Upload transcript"
button's file picker, which only allows `.txt`). Testing audio ingestion
means using the FastAPI-generated docs page directly, which is still a
normal clickable browser UI.

22. Before uploading, make a renamed copy of the test fixture so its
    filename matches the same `YYYY-MM-DD_slug` convention the text
    transcripts use — the API rejects any filename that doesn't match this
    pattern, before it does any (slow) transcription work. Copy
    `data/audio/test_multi_speaker_sample.wav` to a new file in the same
    folder named, for example, `2026-04-01_audio-test-fixture.wav`.
23. In the second browser tab (`http://localhost:8000/docs`), find the
    **meetings** section and expand **POST /meetings/ingest-audio**.
24. Click **Try it out**. Click "Choose File" next to the `file` field and
    select the renamed copy from Step 22. Leave `min_speakers`/
    `max_speakers` blank (auto-detected).
25. Click **Execute**.
    **Expect:** this takes roughly **1-2 minutes** — real transcription and
    diarization are running, this is not a hang. The response body should
    be a 200 with a JSON object containing a `meeting_id`, `"chunk_count":
    10`, `"decision_count": 1`, `"action_item_count": 0`.
26. Switch to the web app tab, click **Meetings**.
    **Expect:** a new card titled **"Audio Test Fixture"**, dated
    "2026-04-01", with participants **"Speaker 1, Speaker 2"** (generic
    labels — real diarization was run, but this short two-person test clip
    has no named-speaker information to attach, so it falls back to
    speaker-index labels rather than guessing names). Click into it and
    confirm one decision is present: "Move forward with the plan.", cited
    to Speaker 2 at timestamp 0:17.

## Part 7 — Traces dashboard

27. Click **Traces** in the top nav.
    **Expect:** the page header "Traces", a subtitle, three filter controls
    (endpoint, outcome, date), and a list of rows below — by now you should
    see at least the four requests from Parts 1-3 and 6 (one `POST
    /meetings/ingest`, two `POST /ask`, one `POST /meetings/ingest-audio`),
    most recent first. Each row shows the endpoint in monospace, an outcome
    badge, duration, token count, and a timestamp.
28. Confirm the outcome badges read correctly: the transcript-ingest and
    audio-ingest rows should show an accent **"Answered"** badge, the known-
    answer question row should show **"Answered"**, and the out-of-scope
    question row should show a neutral **"Declined"** badge.
29. Click the endpoint filter dropdown and select **"POST /ask"**.
    **Expect:** only the two ask requests remain in the list.
30. Click the outcome filter dropdown and select **"Declined"** (with the
    endpoint filter still set to "POST /ask" from Step 29).
    **Expect:** only the out-of-scope question's row remains.
31. Reset both filters back to "All endpoints" / "All outcomes".
32. Click the date filter and pick today's date.
    **Expect:** all of today's traces remain visible (or the list empties
    if you're testing this on a later day than you ran the earlier steps —
    that's correct, not a bug).
33. If you have more than 20 traces total, confirm pagination: the
    "Previous"/"Next" buttons and an "X-Y of Z" count appear below the
    list; "Previous" should be disabled on the first page.

## Part 8 — Trace detail

34. Click the row for one of the two `POST /ask` requests (either the
    known-answer or the declined one).
    **Expect:** you land on a detail page showing the endpoint name as a
    heading, an outcome badge, then a line with total duration, input/
    output token counts, and the model used (`gemini-3.1-flash-lite`),
    followed by a timestamp.
35. Scroll down to the stage timeline.
    **Expect:** an ordered list of stage cards. For a `POST /ask` request
    you should see stages named **`hybrid_search`** and
    **`guardrail_confidence_check`**; the known-answer request should also
    show **`generate_answer`**, while the declined request should stop
    after the guardrail stage (no `generate_answer` stage — the guardrail
    declined before an LLM call was made). Each card shows the stage's
    duration and, where applicable, metadata like `retrieved_count` or
    `passed`.
36. Go back to Traces and click the row for the audio-ingest request from
    Part 6.
    **Expect:** its stage list includes **`transcribe`** and **`diarize`**
    (each taking tens of seconds — this is where Step 25's 1-2 minutes
    went), then `embed`, `ingest_audio`, `prompt_injection_scan`,
    `llm_generate_structured`, `extract_records`, and
    `persist_extractions`, in that order.

---

## Part 9 — MCP server tools

The MCP server is a separate, optional local process — a thin stdio-to-HTTP
client of the same `api` service, not part of `docker compose up`. One-time
setup, from the repo root:

37. `cd apps/mcp_server && python3 -m venv .venv && .venv/bin/pip install -e .`
38. Confirm it worked: `ls apps/mcp_server/.venv/bin/python` should exist.
39. Restart Claude Code (or whichever MCP host you're using) in this repo so
    it picks up the repo's `.mcp.json`, which already points at the venv
    from Step 37.
    **Expect:** a `meridian` MCP server listed as connected, exposing three
    tools: `search_meetings`, `ask_meetings`, `get_action_items`.
40. Ask your MCP host to call `search_meetings` with query "alert
    threshold" and `top_k` 5.
    **Expect:** a JSON object with a `results` array of ranked chunks, each
    with a `citation` (speaker, timestamps, text, meeting ID) and a
    `fused_score` — no generated answer, just retrieval. The top result
    should be Dhruvisha's line about a fixed threshold over/under-alerting
    depending on patient fitness.
41. Ask it to call `ask_meetings` with question "How many logged workouts
    with heart rate data are needed before a personal baseline is
    trusted?".
    **Expect:** the same cited answer as Step 9 — "at least five to seven
    logged workouts with heart rate data," cited to Naomi at 2:35 — since
    this tool is a thin HTTP wrapper around the same `/ask` endpoint.
42. Ask it to call `get_action_items` with no filters, then again with
    `status` "open".
    **Expect:** both calls return the same list — every action item ever
    extracted, across every meeting you've ingested (there is currently no
    way for an action item to have any status other than "open" — see the
    note on this in Part 5).
