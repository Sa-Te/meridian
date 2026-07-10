# ADR-0001: Assignment option and product framing

Status: Accepted
Date: 2026-07-10

## Context

The take-home offers four options: document Q&A (RAG classic), a code
documentation assistant, a meeting intelligence system, or a resume/JD
fit assistant. The brief explicitly weights "creativity in UI/UX and
product innovation" and "your approach and thought process" as highly as
raw functionality, and this submission is also the primary artifact the
Newpage FDE technical interview will be built around.

Separately, the target role's job description repeatedly emphasises
business immersion, stakeholder management, shadowing operations to
understand context, and translating between technical and business
language — behaviours specific to a forward-deployed, client-embedded
engineering model, not just RAG competence in the abstract.

## Decision

Build Option 3, Meeting Intelligence System, and frame the demo dataset as
transcripts from a health-tech consulting engagement (client discovery
calls, sprint reviews, clinical-advisory-style stakeholder meetings) rather
than generic corporate meetings. The system answers questions about
discussions, and additionally extracts structured decisions and action
items (owner, due date, confidence, linked source citation) rather than
doing plain retrieval-and-answer only.

Voice-to-transcript is treated as an explicit stretch goal (see
`ROADMAP.md` Phase 10), time-boxed and cuttable without weakening the
core submission.

## Alternatives considered

- **Option 1 (Chat With Your Docs).** The safest choice and the one every
  other candidate is most likely to submit by default, since it's the
  "classic RAG use-case" named explicitly in the brief. Rejected because it
  offers the least room to differentiate on the creativity and product-thinking
  criteria the brief calls out, and it does not naturally require structured
  extraction, which is a meaningfully harder and more interesting RAG problem.
- **Option 2 (Code Documentation Assistant).** Strong technical fit, but
  weaker narrative fit for an FDE role, which is explicitly about
  business-facing, stakeholder-embedded work rather than internal codebase
  tooling. Would have under-used the JD's "Business Immersion" and
  "Stakeholder Management" skill lines.
- **Option 4 (Career Intelligence Assistant).** Closest to work TJ has
  already done informally (resume tailoring, JD-fit analysis). Rejected
  specifically because of that overlap — it risks reading as a repackaged
  personal tool rather than new range, and gives less opportunity to
  demonstrate multi-document, multi-speaker retrieval and structured
  extraction, which is what the JD's "Generative AI" and "Documentation"
  skill lines actually test for.

## Consequences

- Requires building a small synthetic transcript dataset (10-15 meetings)
  rather than being able to reuse an off-the-shelf public corpus, which
  costs setup time but is fully controllable for demo quality.
- Structured extraction adds a second LLM call pattern (tool-calling /
  structured output) on top of plain RAG QA, which is more schema and test
  surface, but directly answers the brief's "your approach... to Prompt
  Engineering, Context Management" criteria with something more substantial
  than a single QA loop.
- The consulting/health-tech framing gives the README a natural, honest
  reason to discuss guardrails around sensitive business/health-adjacent
  content, which strengthens the "Guardrails" and "Quality Controls"
  sections the brief asks for.

## Links

- `ROADMAP.md` Phase 1 (domain modelling), Phase 4 (structured extraction)
- ADR-0002 (core tech stack)
