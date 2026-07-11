"""LLM-as-judge: scores a generated answer's faithfulness and relevance.
See docs/adr/0009.

This is a separate, clearly-labelled LLM call from the one that produced
the answer being judged (app/services/answer_generation.py) -- its own
system prompt, its own schema, and it never sees how the answer was
produced, only the question, the evidence that was available, and the
answer itself. Uses LLMProvider.generate_structured (native structured
output, same mechanism as app/services/extraction.py) rather than a
plain-JSON prompt, since the judge's own output is exactly the kind of
small structured shape that fits it.
"""

from collections.abc import Sequence
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.orm import Chunk
from app.providers.llm.base import LLMProvider

JUDGE_SYSTEM_PROMPT = (
    "You are an independent evaluator for Meridian, a meeting-intelligence "
    "RAG system. You are judging a system-generated answer for quality -- "
    "you are not generating an answer yourself, and you must not let your "
    "own opinion of the 'right' answer substitute for what the evidence "
    "shown actually supports.\n\n"
    "You will be shown: the user's question, the transcript excerpts that "
    "were available to the system (each tagged CITED if the system's answer "
    "drew on it, UNCITED if it was available but not used), and the "
    "system's final answer. Score two dimensions from 1 (worst) to 5 "
    "(best):\n\n"
    "faithfulness: does every factual claim in the answer trace directly "
    "back to the CITED excerpts, without adding, embellishing, or "
    "contradicting anything not actually present in them? An honest "
    "decline to answer -- the system stating it could not find a "
    "well-supported answer -- is fully faithful (5) as long as it does not "
    "also assert some unsupported claim alongside the decline.\n\n"
    "relevance: does the answer actually address what was asked, given "
    "what was available in the excerpts? If the excerpts genuinely do not "
    "contain an answer to the question, a clear decline is the correct and "
    "fully relevant (5) response. If the excerpts do contain a real answer "
    "but the system declined anyway, or answered something other than what "
    "was asked, score relevance low.\n\n"
    "Give a one-sentence justification for each score."
)


class JudgeVerdict(BaseModel):
    faithfulness: int = Field(ge=1, le=5)
    faithfulness_reasoning: str
    relevance: int = Field(ge=1, le=5)
    relevance_reasoning: str


def _format_excerpts(retrieved_chunks: Sequence[Chunk], cited_chunk_ids: set[UUID]) -> str:
    if not retrieved_chunks:
        return "(No excerpts were retrieved for this question.)"
    return "\n\n".join(
        f"[{'CITED' if chunk.id in cited_chunk_ids else 'UNCITED'}] "
        f"[{chunk.start_ts}s] {chunk.speaker}: {chunk.text}"
        for chunk in retrieved_chunks
    )


def build_judge_prompt(
    *,
    question: str,
    answer: str,
    retrieved_chunks: Sequence[Chunk],
    cited_chunk_ids: set[UUID],
) -> str:
    excerpts = _format_excerpts(retrieved_chunks, cited_chunk_ids)
    return (
        f"Question: {question}\n\n"
        f"Excerpts available to the system:\n\n{excerpts}\n\n"
        f"System's answer: {answer}"
    )


async def judge_answer(
    *,
    question: str,
    answer: str,
    retrieved_chunks: Sequence[Chunk],
    cited_chunk_ids: set[UUID],
    llm_provider: LLMProvider,
) -> JudgeVerdict:
    prompt = build_judge_prompt(
        question=question,
        answer=answer,
        retrieved_chunks=retrieved_chunks,
        cited_chunk_ids=cited_chunk_ids,
    )
    return await llm_provider.generate_structured(
        prompt,
        JudgeVerdict,
        system=JUDGE_SYSTEM_PROMPT,
        max_tokens=512,
        temperature=0.0,
    )
