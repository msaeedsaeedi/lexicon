from lexicon.curation import curate
from lexicon.model import Source, StagedDefinition, StagedExample, StagedLexeme, StagedSense
from lexicon.normalize import normalize_dataset


def test_curation_partitions_junk_and_honors_allowlist() -> None:
    source = Source(
        id="fixture",
        name="Fixture",
        version="1",
        source_url="https://example.invalid/fixture",
        license="CC0-1.0",
        retrieved_at="2026-08-03",
        checksum="0" * 64,
    )
    dataset = normalize_dataset(
        (source,),
        tuple(
            StagedLexeme(
                source_id="fixture",
                language="en",
                lemma=lemma,
                part_of_speech="noun",
                senses=[
                    StagedSense(
                        definitions=[StagedDefinition(text="Definition.")],
                        examples=[StagedExample(text="Example.")],
                    )
                ],
            )
            for lemma in ("in(a)", "3-d", "x2", "123", "two words", "good")
        ),
    )
    ids = {lexeme.lemma: lexeme.id for lexeme in dataset.lexemes}
    grades = {item.lexeme_id: item for item in curate(dataset, {ids["two words"]})}

    assert grades[ids["in(a)"]].reason == "satellite_paren"
    assert grades[ids["3-d"]].reason == "digit_leading"
    assert grades[ids["x2"]].reason == "digit_containing"
    assert grades[ids["123"]].reason == "pure_numeric"
    assert grades[ids["two words"]].grade == "curated_allowlist"
    assert grades[ids["good"]].grade == "graded"
