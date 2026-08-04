"""Deterministic wordfreq ranking import and lemma-to-lexeme mapping."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from wordfreq import zipf_frequency

from .compile import write_text_atomic
from .errors import PipelineError
from .model import Dataset, Ranking, Source


class FrequencyError(PipelineError):
    code = "frequency.invalid_input"


def load_source(lock_path: Path) -> Source:
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FrequencyError(f"cannot read frequency lock: {lock_path}") from error
    if not isinstance(payload, dict):
        raise FrequencyError("frequency lock must be a JSON object")
    required = ("id", "license", "source_url", "attribution")
    if any(not isinstance(payload.get(key), str) or not payload[key] for key in required):
        raise FrequencyError("frequency lock requires id, license, source_url, and attribution")
    return Source(
        id=payload["id"],
        name="wordfreq",
        version="3.1.1",
        source_url=payload["source_url"],
        license=payload["license"],
        # The lock is checked in with the pipeline; this date is provenance, not a download time.
        retrieved_at=str(payload.get("retrieved_at", date.today().isoformat())),
        checksum=payload.get("checksum"),
    )


def rank_lemmas(dataset: Dataset, source_id: str) -> tuple[Ranking, ...]:
    """Rank normalized English lemmas once, then share that rank across POS lexemes.

    A zero Zipf value denotes a lemma absent from wordfreq and intentionally receives no
    ranking row. Collections append those lexemes after all ranked members.
    """
    grouped: dict[str, list[str]] = {}
    for lexeme in dataset.lexemes:
        if lexeme.language_id != "en":
            continue
        grouped.setdefault(lexeme.normalized_lemma, []).append(lexeme.id)
    scored = [(lemma, float(zipf_frequency(lemma, "en"))) for lemma in sorted(grouped)]
    ranked = sorted(
        ((lemma, score) for lemma, score in scored if score > 0),
        key=lambda item: (-item[1], item[0]),
    )
    lemma_rank = {lemma: number for number, (lemma, _) in enumerate(ranked, start=1)}
    lemma_zipf = dict(ranked)
    return tuple(
        Ranking(
            lexeme_id=lexeme_id,
            rank=lemma_rank[lemma],
            zipf=lemma_zipf[lemma],
            source_id=source_id,
        )
        for lemma in sorted(lemma_rank, key=lambda item: (lemma_rank[item], item))
        for lexeme_id in sorted(grouped[lemma])
    )


def write_rankings(rankings: tuple[Ranking, ...], source: Source, target: Path) -> None:
    payload: dict[str, Any] = {
        "source": source.model_dump(mode="json"),
        "rankings": [ranking.model_dump(mode="json") for ranking in rankings],
    }
    write_text_atomic(
        target, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def load_rankings(path: Path) -> tuple[Source, tuple[Ranking, ...]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("not an object")
        source = Source.model_validate(payload["source"])
        rankings = tuple(Ranking.model_validate(item) for item in payload["rankings"])
    except (OSError, ValueError, KeyError) as error:
        raise FrequencyError(f"cannot read frequency rankings: {path}") from error
    return source, rankings
