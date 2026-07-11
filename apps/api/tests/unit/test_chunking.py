from app.services.chunking import ChunkData, chunk_turns, count_words
from app.services.transcript_parser import SpeakerTurn

MAX_TOKENS = 10


def _turn(speaker: str, start_ts: int, end_ts: int, text: str) -> SpeakerTurn:
    return SpeakerTurn(speaker=speaker, start_ts=start_ts, end_ts=end_ts, text=text)


def test_turn_just_under_the_limit_is_not_split() -> None:
    text = "one two three four five six seven eight nine"  # 9 words
    assert count_words(text) == MAX_TOKENS - 1
    turns = [_turn("Alice", 0, 10, text)]

    chunks = chunk_turns(turns, max_tokens=MAX_TOKENS)

    assert chunks == [ChunkData(speaker="Alice", start_ts=0, end_ts=10, text=text)]


def test_turn_exactly_at_the_limit_is_not_split() -> None:
    text = "one two three four five six seven eight nine ten"  # 10 words
    assert count_words(text) == MAX_TOKENS
    turns = [_turn("Alice", 0, 10, text)]

    chunks = chunk_turns(turns, max_tokens=MAX_TOKENS)

    assert chunks == [ChunkData(speaker="Alice", start_ts=0, end_ts=10, text=text)]


def test_turn_just_over_the_limit_is_split_on_sentence_boundaries() -> None:
    text = "one two three four five six. seven eight nine ten eleven."  # 11 words
    assert count_words(text) == MAX_TOKENS + 1
    turns = [_turn("Alice", 0, 10, text)]

    chunks = chunk_turns(turns, max_tokens=MAX_TOKENS)

    assert len(chunks) == 2
    assert chunks[0].text == "one two three four five six."
    assert chunks[1].text == "seven eight nine ten eleven."
    assert all(count_words(chunk.text) <= MAX_TOKENS for chunk in chunks)
    # No finer-grained timing exists within a turn -- both pieces share it.
    assert chunks[0].speaker == chunks[1].speaker == "Alice"
    assert chunks[0].start_ts == chunks[1].start_ts == 0
    assert chunks[0].end_ts == chunks[1].end_ts == 10


def test_a_single_sentence_that_alone_exceeds_the_limit_is_kept_whole() -> None:
    text = (
        "one two three four five six seven eight nine ten eleven twelve"  # 12 words, one sentence
    )
    turns = [_turn("Alice", 0, 10, text)]

    chunks = chunk_turns(turns, max_tokens=MAX_TOKENS)

    assert len(chunks) == 1
    assert chunks[0].text == text


def test_consecutive_same_speaker_turns_are_merged_into_one_chunk() -> None:
    turns = [
        _turn("Alice", 0, 5, "one two"),
        _turn("Alice", 5, 10, "three four"),
    ]

    chunks = chunk_turns(turns, max_tokens=MAX_TOKENS)

    assert chunks == [ChunkData(speaker="Alice", start_ts=0, end_ts=10, text="one two three four")]


def test_consecutive_different_speaker_turns_are_never_merged() -> None:
    turns = [
        _turn("Alice", 0, 5, "one two"),
        _turn("Bob", 5, 10, "three four"),
    ]

    chunks = chunk_turns(turns, max_tokens=MAX_TOKENS)

    assert chunks == [
        ChunkData(speaker="Alice", start_ts=0, end_ts=5, text="one two"),
        ChunkData(speaker="Bob", start_ts=5, end_ts=10, text="three four"),
    ]


def test_same_speaker_turns_are_not_merged_past_the_token_budget() -> None:
    first_text = "one two three four five six seven"  # 7 words
    second_text = "eight nine ten"  # 3 words, 7 + 3 = 10 == MAX_TOKENS exactly
    third_text = "eleven"  # 1 more word would push a merge past budget

    turns = [
        _turn("Alice", 0, 5, first_text),
        _turn("Alice", 5, 10, second_text),
        _turn("Alice", 10, 15, third_text),
    ]

    chunks = chunk_turns(turns, max_tokens=MAX_TOKENS)

    assert len(chunks) == 2
    assert chunks[0].text == f"{first_text} {second_text}"
    assert chunks[1].text == third_text


def test_empty_turn_list_produces_no_chunks() -> None:
    assert chunk_turns([], max_tokens=MAX_TOKENS) == []
