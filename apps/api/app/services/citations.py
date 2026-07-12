"""Builds a CitationRead from a Chunk. Shared by app/routers/meetings.py
(Decision/ActionItem source citations) and app/routers/action_items.py
(the global action-items list) so both build the same shape the same way,
rather than each re-deriving it inline.
"""

from app.models.orm import Chunk
from app.models.schemas import CitationRead


def build_citation(chunk: Chunk) -> CitationRead:
    return CitationRead(
        chunk_id=chunk.id,
        meeting_id=chunk.meeting_id,
        speaker=chunk.speaker,
        start_ts=chunk.start_ts,
        end_ts=chunk.end_ts,
        text=chunk.text,
    )
