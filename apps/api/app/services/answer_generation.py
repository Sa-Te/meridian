"""Cited answer generation over retrieved chunks. See docs/adr/0007.

The LLM is asked to return a single JSON object naming which chunk_ids it
drew its answer from. A response that isn't valid JSON in that shape, or
that cites a chunk_id outside the retrieved set, is a guardrail failure --
it gets one retry with a stricter instruction before falling back to a
fixed "not well-supported" response. This mirrors the fuller guardrails
module planned for Phase 4 (see ROADMAP.md), kept isolated here so that
module can reuse it rather than rewrite it.
"""

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from app.models.orm import Chunk
from app.providers.llm.base import LLMMessage, LLMProvider

UNSUPPORTED_ANSWER = (
    "I could not find a well-supported answer to this question in the available transcripts."
)

_SYSTEM_PROMPT = (
    "You are Meridian, a meeting-intelligence assistant. Answer the user's "
    "question using ONLY the meeting transcript excerpts provided below. "
    "Respond with a single JSON object and nothing else -- no markdown code "
    "fences, no commentary before or after it. The JSON object must have "
    'exactly these keys: "supported" (boolean), "answer" (string), and '
    '"citations" (an array of objects, each with a single "chunk_id" string '
    "key, copied exactly from the [chunk_id: ...] tag shown next to an "
    "excerpt you actually used). If the excerpts do not contain enough "
    'information to answer the question, set "supported" to false, '
    '"answer" to a short sentence saying so, and "citations" to an empty '
    'array. If "supported" is true, "citations" must be non-empty and every '
    "chunk_id must come from an excerpt shown below -- never invent one."
)

_STRICT_RETRY_SUFFIX = (
    "\n\nIMPORTANT: your previous response was rejected because it was not "
    "valid JSON in the required schema, or it cited a chunk_id that was not "
    "shown below. Return ONLY the JSON object described above, with no other "
    "text, and use only chunk_ids copied exactly from the excerpts shown."
)


@dataclass(frozen=True)
class Citation:
    chunk_id: uuid.UUID


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    supported: bool
    citations: list[Citation]


class _LLMCitation(BaseModel):
    chunk_id: uuid.UUID


class _LLMAnswerPayload(BaseModel):
    supported: bool
    answer: str
    citations: list[_LLMCitation]


def _build_user_prompt(question: str, chunks: Sequence[Chunk]) -> str:
    excerpts = "\n\n".join(
        f"[chunk_id: {chunk.id}] [{chunk.start_ts}s] {chunk.speaker}: {chunk.text}"
        for chunk in chunks
    )
    return f"Transcript excerpts:\n\n{excerpts}\n\nQuestion: {question}"


def _strip_code_fence(text: str) -> str:
    """Some models wrap JSON in a ```json ... ``` fence despite instructions
    not to. Strip one if present; otherwise return the text unchanged."""
    if not text.startswith("```"):
        return text
    lines = text.split("\n")
    lines = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
    return "\n".join(lines).strip()


def _parse_response(raw_text: str, valid_chunk_ids: set[uuid.UUID]) -> AnswerResult | None:
    """Parse and guardrail-check a raw LLM response. Returns None on any
    guardrail failure: malformed JSON, a schema mismatch, a "supported"
    answer with no citations, or a citation to a chunk_id that wasn't
    actually retrieved.
    """
    try:
        payload = _LLMAnswerPayload.model_validate(json.loads(_strip_code_fence(raw_text.strip())))
    except (json.JSONDecodeError, ValidationError):
        return None

    if not payload.supported:
        return AnswerResult(answer=payload.answer, supported=False, citations=[])

    cited_ids = [citation.chunk_id for citation in payload.citations]
    if not cited_ids or not set(cited_ids).issubset(valid_chunk_ids):
        return None

    unique_ids = list(dict.fromkeys(cited_ids))
    return AnswerResult(
        answer=payload.answer,
        supported=True,
        citations=[Citation(chunk_id=chunk_id) for chunk_id in unique_ids],
    )


async def generate_answer(
    *,
    question: str,
    retrieved_chunks: Sequence[Chunk],
    llm_provider: LLMProvider,
) -> AnswerResult:
    """Generate a cited answer from the top-k retrieved chunks.

    Falls back to UNSUPPORTED_ANSWER, without calling the LLM at all, when
    there are no retrieved chunks to reason over. Otherwise calls the LLM,
    retries once with a stricter instruction on a guardrail failure, and
    falls back to UNSUPPORTED_ANSWER if the retry also fails.
    """
    if not retrieved_chunks:
        return AnswerResult(answer=UNSUPPORTED_ANSWER, supported=False, citations=[])

    valid_chunk_ids = {chunk.id for chunk in retrieved_chunks}
    user_prompt = _build_user_prompt(question, retrieved_chunks)

    response = await llm_provider.generate(
        messages=[LLMMessage(role="user", content=user_prompt)], system=_SYSTEM_PROMPT
    )
    result = _parse_response(response.text, valid_chunk_ids)
    if result is not None:
        return result

    retry_response = await llm_provider.generate(
        messages=[LLMMessage(role="user", content=user_prompt)],
        system=_SYSTEM_PROMPT + _STRICT_RETRY_SUFFIX,
    )
    result = _parse_response(retry_response.text, valid_chunk_ids)
    if result is not None:
        return result

    return AnswerResult(answer=UNSUPPORTED_ANSWER, supported=False, citations=[])
