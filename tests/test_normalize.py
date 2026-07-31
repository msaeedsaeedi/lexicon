from pathlib import Path

from lexicon.normalize import normalize_dataset
from lexicon.staging import load_staging

SEED = Path("data/seed")


def test_seed_normalizes_duplicates_but_keeps_homographs_separate() -> None:
    sources, records = load_staging(SEED)
    dataset = normalize_dataset(sources, records)

    assert [lexeme.id for lexeme in dataset.lexemes] == [
        "en:ambiguous:adjective",
        "en:record:noun",
        "en:record:verb",
    ]
    ambiguous = dataset.lexemes[0]
    assert ambiguous.lemma == "ambiguous"
    assert len(ambiguous.senses) == 2
    assert ambiguous.forms[0].is_canonical is True


def test_normalization_generates_deterministic_nested_identifiers() -> None:
    sources, records = load_staging(SEED)
    dataset = normalize_dataset(sources, records)

    verb = next(item for item in dataset.lexemes if item.id == "en:record:verb")
    assert [form.id for form in verb.forms] == [
        "en:record:verb:form:record",
        "en:record:verb:form:recorded",
        "en:record:verb:form:recording",
    ]
    assert verb.senses[0].definitions[0].id == "en:record:verb:1:definition:1"
