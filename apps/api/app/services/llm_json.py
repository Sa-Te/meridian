"""Shared helper for parsing plain-JSON-prompted LLM responses. Used by
app/services/answer_generation.py (Phase 3's citation-enforced answers,
which stay on the plain-JSON pattern per ADR-0007). Extraction moved to
native structured output instead (see docs/adr/0008) and does not need this.
"""


def strip_code_fence(text: str) -> str:
    """Some models wrap JSON in a ```json ... ``` fence despite instructions
    not to. Strip one if present; otherwise return the text unchanged."""
    if not text.startswith("```"):
        return text
    lines = text.split("\n")
    lines = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
    return "\n".join(lines).strip()
