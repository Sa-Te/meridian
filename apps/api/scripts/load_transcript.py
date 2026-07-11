"""CLI to ingest one transcript file into the database end to end: parse,
chunk, embed, and store (see app/services/ingestion.py).

Usage (from apps/api, with DATABASE_URL pointing at a migrated database):

    python scripts/load_transcript.py \
        ../../data/transcripts/2026-02-19_leadership-sync-roadmap-prioritization.txt

See ROADMAP.md Phase 2.
"""

import argparse
import asyncio
from pathlib import Path

from app.config import get_settings
from app.db import async_session_factory
from app.providers.embedding.factory import get_embedding_provider
from app.services.ingestion import ingest_transcript


async def load_transcript_file(path: Path) -> None:
    embedding_provider = get_embedding_provider(get_settings())
    raw_text = path.read_text()

    async with async_session_factory() as session:
        meeting = await ingest_transcript(
            filename=path.name,
            raw_text=raw_text,
            embedding_provider=embedding_provider,
            session=session,
        )
        print(f"Loaded '{meeting.title}' ({meeting.id}) - {len(meeting.chunks)} chunks")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to a transcript .txt file")
    args = parser.parse_args()
    asyncio.run(load_transcript_file(args.path))


if __name__ == "__main__":
    main()
