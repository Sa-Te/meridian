"""CLI to load one transcript file into the database end to end.

Usage (from apps/api, with DATABASE_URL pointing at a migrated database):

    python scripts/load_transcript.py \
        ../../data/transcripts/2026-02-19_leadership-sync-roadmap-prioritization.txt

Proves the domain schema round-trips a real transcript (Meeting + Chunks,
no embeddings yet -- that's Phase 2). See ROADMAP.md Phase 1.
"""

import argparse
import asyncio
from pathlib import Path

from app.db import async_session_factory
from app.repositories.meeting_repository import MeetingRepository
from app.services.transcript_loader import load_meeting_from_file


async def load_transcript_file(path: Path) -> None:
    meeting = load_meeting_from_file(path)

    async with async_session_factory() as session:
        repository = MeetingRepository(session)
        saved = await repository.create(meeting)
        print(f"Loaded '{saved.title}' ({saved.id}) - {len(saved.chunks)} chunks")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to a transcript .txt file")
    args = parser.parse_args()
    asyncio.run(load_transcript_file(args.path))


if __name__ == "__main__":
    main()
