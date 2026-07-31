import pytest

from lexicon.model import Source, StagedLexeme
from lexicon.normalize import NormalizationError, normalize_dataset


def test_unknown_source_is_rejected() -> None:
    record = StagedLexeme.model_validate(
        {
            "source_id": "missing",
            "language": "en",
            "lemma": "test",
            "part_of_speech": "noun",
            "senses": [{"definitions": [{"text": "A test."}], "examples": [{"text": "This is a test."}]}],
        }
    )
    with pytest.raises(NormalizationError, match="unknown source"):
        normalize_dataset((), (record,))


def test_conflicting_normalized_duplicates_are_rejected() -> None:
    source = Source(id="seed", name="Seed", version="1", source_url="https://example.invalid", license="CC0-1.0", retrieved_at="2026-07-31")
    first = StagedLexeme.model_validate({"source_id": "seed", "language": "en", "lemma": "test", "part_of_speech": "noun", "senses": [{"definitions": [{"text": "First."}], "examples": [{"text": "A test."}]}]})
    second = StagedLexeme.model_validate({"source_id": "seed", "language": "en", "lemma": " Test ", "part_of_speech": "noun", "senses": [{"definitions": [{"text": "Second."}], "examples": [{"text": "A test."}]}]})
    with pytest.raises(NormalizationError, match="conflicting"):
        normalize_dataset((source,), (first, second))
