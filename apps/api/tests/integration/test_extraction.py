"""Integration test for structured extraction (docs/adr/0008) against a
real Gemini API call -- the one integration test in this suite that spends
a real LLM call, since GeminiLLMProvider.generate_structured is the part of
this phase that can't be meaningfully verified against a fake (does Gemini's
response_schema mode actually return our Pydantic shape from a real
transcript?). Skipped automatically if no real GEMINI_API_KEY is configured.
Requires a real Postgres database migrated to head.
"""

from pathlib import Path

import pytest
from sqlalchemy import delete

from app.config import get_settings
from app.db import async_session_factory, engine
from app.models.orm import Meeting
from app.providers.llm.gemini_provider import GeminiLLMProvider
from app.services.extraction import extract_records
from app.services.ingestion import ingest_transcript
from tests.fakes import FakeEmbeddingProvider

_ALERT_THRESHOLDS_TRANSCRIPT = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "transcripts"
    / "2026-01-29_clinical-advisory-alert-thresholds.txt"
)

pytestmark = pytest.mark.skipif(
    not get_settings().gemini_api_key, reason="requires a real GEMINI_API_KEY (see .env)"
)


@pytest.fixture(autouse=True)
async def _clean_meetings_table() -> None:
    yield
    async with engine.begin() as connection:
        await connection.execute(delete(Meeting))


async def test_extraction_finds_the_alert_threshold_decision_and_an_action_item() -> None:
    settings = get_settings()
    assert settings.gemini_api_key is not None
    llm_provider = GeminiLLMProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)

    async with async_session_factory() as session:
        meeting = await ingest_transcript(
            filename=_ALERT_THRESHOLDS_TRANSCRIPT.name,
            raw_text=_ALERT_THRESHOLDS_TRANSCRIPT.read_text(),
            embedding_provider=FakeEmbeddingProvider(),
            session=session,
        )

    result = await extract_records(
        meeting_chunks=meeting.chunks,
        llm_provider=llm_provider,
        confidence_threshold=settings.extraction_confidence_threshold,
    )

    chunk_by_id = {chunk.id: chunk for chunk in meeting.chunks}

    # The known decision: the alert logic moves from a flat 160bpm threshold
    # to patient-baseline-plus-40%, sustained three minutes.
    assert len(result.decisions) >= 1
    threshold_decision = next(
        (
            decision
            for decision in result.decisions
            if "forty" in decision.text.lower() or "40" in decision.text
        ),
        None,
    )
    assert threshold_decision is not None, f"No threshold decision found in {result.decisions}"
    assert threshold_decision.source_chunk_id in chunk_by_id
    cited_text = chunk_by_id[threshold_decision.source_chunk_id].text.lower()
    assert "forty percent" in cited_text or "40" in cited_text

    # The known action items: Dr. Vasquez sending the source for the 40%
    # figure, Naomi prototyping the baseline calculation, and Dr. Mehta
    # defining the arrhythmia policy -- every extracted item must at least
    # cite a real chunk from this meeting.
    assert len(result.action_items) >= 1
    for item in result.action_items:
        assert item.source_chunk_id in chunk_by_id

    named_owners = {item.owner.lower() for item in result.action_items if item.owner}
    assert any(
        "vasquez" in owner or "naomi" in owner or "mehta" in owner for owner in named_owners
    ), f"No known owner found among extracted action items: {named_owners}"
