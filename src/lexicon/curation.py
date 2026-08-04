"""Deterministic quality grading for canonical lexemes."""

from __future__ import annotations

from collections import Counter

from .model import Curation, Dataset, Lexeme
from .version import PIPELINE_VERSION


def curate(
    dataset: Dataset,
    allowlist: set[str] | None = None,
    force_exclude: set[str] | None = None,
) -> tuple[Curation, ...]:
    """Partition every lexeme into graded, excluded junk, or explicit allowlist."""
    allowlist = allowlist or set()
    force_exclude = force_exclude or set()
    return tuple(
        Curation(
            lexeme_id=lexeme.id,
            grade=(
                "curated_allowlist"
                if lexeme.id in allowlist
                else "excluded_junk"
                if lexeme.id in force_exclude or _reason(lexeme) is not None
                else "graded"
            ),
            reason=(
                "curated_allowlist"
                if lexeme.id in allowlist
                else "force_exclude"
                if lexeme.id in force_exclude
                else _reason(lexeme) or "clean"
            ),
            pipeline_version=PIPELINE_VERSION,
        )
        for lexeme in dataset.lexemes
    )


def curation_counts(curation: tuple[Curation, ...]) -> dict[str, int]:
    return dict(sorted(Counter(item.reason for item in curation).items()))


def _reason(lexeme: Lexeme) -> str | None:
    lemma = lexeme.lemma
    if "(" in lemma:
        return "satellite_paren"
    if lemma.isnumeric():
        return "pure_numeric"
    if lemma[:1].isdigit():
        return "digit_leading"
    if any(character.isdigit() for character in lemma):
        return "digit_containing"
    if any(character.isspace() for character in lemma):
        return "multiword"
    if len(lemma) > 30:
        return "overlong"
    if not any(sense.definitions for sense in lexeme.senses):
        return "no_definition"
    if not any(sense.examples for sense in lexeme.senses):
        return "no_example"
    if not any(form.is_canonical for form in lexeme.forms):
        return "no_canonical_form"
    return None
