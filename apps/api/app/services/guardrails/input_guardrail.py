"""Input guardrail: scan uploaded transcript text for prompt-injection-style
content -- instructions addressed to an AI model, embedded in the transcript
itself -- before that text is ever included in an extraction or answer
prompt. See docs/adr/0008.

This is detection, not sanitization: a match is surfaced as a flag on the
ingest response (ROADMAP.md Phase 4), not silently stripped from the
transcript. The transcript is still chunked, embedded, and passed to
extraction/generation as usual -- flagging lets a human reviewer decide
whether the content is a real attack or just a meeting participant reading
a prompt out loud, which a machine can't reliably tell apart on its own.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.models.orm import Chunk

# Deliberately heuristic, not exhaustive: each pattern targets a known,
# common prompt-injection phrasing (instructions addressed to an AI,
# attempts to override prior instructions, requests to reveal the system
# prompt). A determined adversary can phrase around any fixed pattern list
# -- see docs/adr/0008's "Alternatives considered" for why a fuller
# classifier was out of scope for this submission.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore_instructions",
        re.compile(
            r"\b(ignore|disregard)\s+(all\s+|any\s+)?(previous|prior|the\s+above)\s+"
            r"(instructions?|prompts?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "new_instructions",
        re.compile(r"\bnew\s+instructions?\s*:", re.IGNORECASE),
    ),
    (
        "addressed_to_ai",
        re.compile(
            r"\b(you\s+are|you're)\s+(now\s+)?(an?\s+)?(ai|chatgpt|claude|gemini|"
            r"a\s+language\s+model|an?\s+assistant)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "reveal_system_prompt",
        re.compile(
            r"\b(reveal|print|show|repeat)\s+(your\s+|the\s+)?(system\s+prompt|"
            r"instructions?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "act_as",
        re.compile(r"\bact\s+as\s+(if\s+you\s+(were|are)\s+)?an?\b", re.IGNORECASE),
    ),
    (
        "forget_everything",
        re.compile(
            r"\bforget\s+(everything|all)\s+(you\s+(were\s+told|know)|previous)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "do_not_follow_rules",
        re.compile(
            r"\bdo\s+not\s+(follow|obey)\s+(your|the)\s+(rules|guidelines|instructions?)\b",
            re.IGNORECASE,
        ),
    ),
]


@dataclass(frozen=True)
class PromptInjectionMatch:
    """A single pattern match within one piece of text."""

    pattern_name: str
    matched_text: str


@dataclass(frozen=True)
class ChunkPromptInjectionFinding:
    """A PromptInjectionMatch located within a specific chunk, by index."""

    chunk_index: int
    pattern_name: str
    matched_text: str


def scan_for_prompt_injection(text: str) -> list[PromptInjectionMatch]:
    """Scan a single piece of text against every known injection pattern.

    Returns one match per pattern that fires (never more than one per
    pattern, even if it appears multiple times in the text) -- this is a
    flag that the text needs review, not an exhaustive occurrence count.
    """
    matches = []
    for pattern_name, pattern in _PATTERNS:
        found = pattern.search(text)
        if found is not None:
            matches.append(
                PromptInjectionMatch(pattern_name=pattern_name, matched_text=found.group(0))
            )
    return matches


def scan_chunks_for_prompt_injection(chunks: Sequence[Chunk]) -> list[ChunkPromptInjectionFinding]:
    """Scan each chunk's text independently, tagging findings with the
    chunk_index they came from so the ingest response can point a reviewer
    at the right part of the transcript.
    """
    findings = []
    for chunk in chunks:
        for match in scan_for_prompt_injection(chunk.text):
            findings.append(
                ChunkPromptInjectionFinding(
                    chunk_index=chunk.chunk_index,
                    pattern_name=match.pattern_name,
                    matched_text=match.matched_text,
                )
            )
    return findings
