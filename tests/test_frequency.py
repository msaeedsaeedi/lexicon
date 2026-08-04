from pathlib import Path

from lexicon.frequency import rank_lemmas
from lexicon.normalize import normalize_dataset
from lexicon.staging import load_staging


def test_rank_lemmas_is_deterministic_and_shares_a_lemma_rank(monkeypatch) -> None:
    sources, records = load_staging(Path("data/seed"))
    dataset = normalize_dataset(sources, records)
    scores = {"ambiguous": 4.0, "record": 5.0}
    monkeypatch.setattr("lexicon.frequency.zipf_frequency", lambda lemma, language: scores[lemma])

    first = rank_lemmas(dataset, "wordfreq-3.1.1")
    second = rank_lemmas(dataset, "wordfreq-3.1.1")

    assert first == second
    assert [(item.lexeme_id, item.rank, item.zipf) for item in first] == [
        ("en:record:noun", 1, 5.0),
        ("en:record:verb", 1, 5.0),
        ("en:ambiguous:adjective", 2, 4.0),
    ]
