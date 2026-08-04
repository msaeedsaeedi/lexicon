import json
from pathlib import Path

import pytest

from lexicon.collections import CollectionError, build_starter_collection, load_definition
from lexicon.curation import curate
from lexicon.model import (
    ListMember,
    Ranking,
    Source,
    StagedDefinition,
    StagedExample,
    StagedLexeme,
    StagedSense,
)
from lexicon.normalize import normalize_dataset
from lexicon.staging import load_staging


def test_starter_collection_appends_missing_frequency_with_reason() -> None:
    sources, records = load_staging(Path("data/seed"))
    dataset = normalize_dataset(sources, records)
    definition = load_definition(Path("data/collections/en-general-starter.json"), dataset)
    rankings = (
        Ranking(lexeme_id="en:record:noun", rank=1, zipf=5.0, source_id="wordfreq-3.1.1"),
        Ranking(lexeme_id="en:record:verb", rank=1, zipf=5.0, source_id="wordfreq-3.1.1"),
    )

    ngsl = tuple(
        ListMember(list_id="ngsl-1.2", lemma=lemma, rank=rank, band=1, source_id="ngsl-1.2")
        for lemma, rank in (("record", 1), ("ambiguous", 2))
    )
    _, members, report = build_starter_collection(
        dataset, rankings, curate(dataset), ngsl, definition
    )

    assert [(item.lexeme_id, item.rank, item.inclusion_reason) for item in members] == [
        ("en:record:noun", 1, "ngsl_band_1"),
        ("en:record:verb", 2, "ngsl_band_1"),
    ]
    assert report["rarity_gate_count"] == 1


def test_collection_definition_rejects_unknown_excluded_lexeme(tmp_path: Path) -> None:
    sources, records = load_staging(Path("data/seed"))
    dataset = normalize_dataset(sources, records)
    definition = json.loads(Path("data/collections/en-general-starter.json").read_text())
    definition["exclusions"] = ["en:missing:noun"]
    path = tmp_path / "invalid-collection.json"
    path.write_text(json.dumps(definition))

    with pytest.raises(CollectionError, match="unknown lexeme IDs"):
        load_definition(path, dataset)


def test_starter_collection_reports_eligibility_exclusions(tmp_path: Path) -> None:
    source = Source(
        id="fixture",
        name="Fixture",
        version="1",
        source_url="https://example.invalid/fixture",
        license="CC0-1.0",
        retrieved_at="2026-08-03",
        checksum="0" * 64,
    )
    records = tuple(
        StagedLexeme(
            source_id="fixture",
            language="en",
            lemma=lemma,
            part_of_speech="noun",
            senses=[
                StagedSense(
                    definitions=[StagedDefinition(text="A fixture definition.")],
                    examples=[StagedExample(text="A fixture example.")] if has_example else [],
                ),
            ],
        )
        for lemma, has_example in (
            ("good", True),
            ("two words", True),
            ("123", True),
            ("x" * 31, True),
            ("noexample", False),
        )
    )
    dataset = normalize_dataset((source,), records)
    definition_path = tmp_path / "collection.json"
    definition_path.write_text(
        json.dumps(
            {
                "id": "test-starter",
                "title": "Test starter",
                "selection_basis": "test",
                "version": "1",
                "exclusions": [],
            }
        )
    )

    ngsl = (ListMember(list_id="ngsl-1.2", lemma="good", rank=1, band=1, source_id="ngsl-1.2"),)
    _, members, report = build_starter_collection(
        dataset,
        (Ranking(lexeme_id="en:good:noun", rank=1, zipf=5.0, source_id="wordfreq-3.1.1"),),
        curate(dataset),
        ngsl,
        load_definition(definition_path, dataset),
    )

    assert [member.lexeme_id for member in members] == ["en:good:noun"]
    assert report["junk_counts"] == {
        "overlong": 1,
        "multiword": 1,
        "no_example": 1,
        "pure_numeric": 1,
    }
