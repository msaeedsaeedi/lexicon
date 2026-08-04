"""Deterministic editorial collections built from canonical lexemes and rankings."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import Field

from .compile import write_text_atomic
from .errors import PipelineError
from .model import (
    Collection,
    CollectionMember,
    Curation,
    Dataset,
    Lexeme,
    ListMember,
    Ranking,
    StrictModel,
)
from .version import PIPELINE_VERSION


class CollectionError(PipelineError):
    code = "collections.invalid_input"


class CollectionDefinition(StrictModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    selection_basis: str = Field(min_length=1)
    version: str = Field(min_length=1)
    exclusions: tuple[str, ...] = ()


def load_definition(path: Path, dataset: Dataset) -> CollectionDefinition:
    try:
        definition = CollectionDefinition.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CollectionError(f"cannot read collection definition: {path}") from error
    lexeme_ids = {lexeme.id for lexeme in dataset.lexemes}
    unknown = sorted(set(definition.exclusions) - lexeme_ids)
    if unknown:
        raise CollectionError(f"collection {definition.id} excludes unknown lexeme IDs: {unknown}")
    return definition


def build_starter_collection(
    dataset: Dataset,
    rankings: tuple[Ranking, ...],
    curation: tuple[Curation, ...],
    ngsl_members: tuple[ListMember, ...],
    definition: CollectionDefinition,
) -> tuple[Collection, tuple[CollectionMember, ...], dict[str, Any]]:
    ranking_by_lexeme = {ranking.lexeme_id: ranking for ranking in rankings}
    curation_by_lexeme = {item.lexeme_id: item for item in curation}
    ngsl_by_lemma = {item.lemma: item for item in ngsl_members}
    excluded = Counter[str]()
    rarity_gate_count = 0
    eligible: list[tuple[Lexeme, ListMember, str]] = []
    for lexeme in dataset.lexemes:
        grade = curation_by_lexeme[lexeme.id]
        ngsl = ngsl_by_lemma.get(lexeme.normalized_lemma)
        if grade.grade == "excluded_junk":
            excluded[grade.reason] += 1
            continue
        if ngsl is None:
            continue
        ranking = ranking_by_lexeme.get(lexeme.id)
        if grade.grade != "curated_allowlist" and (ranking is None or ranking.zipf < 2):
            rarity_gate_count += 1
            continue
        eligible.append(
            (
                lexeme,
                ngsl,
                "curated_allowlist"
                if grade.grade == "curated_allowlist"
                else f"ngsl_band_{ngsl.band}",
            )
        )
    eligible.sort(key=lambda item: (item[1].rank, item[0].part_of_speech, item[0].id))
    collection = Collection(
        id=definition.id,
        title=definition.title,
        selection_basis=definition.selection_basis,
        version=definition.version,
        pipeline_version=PIPELINE_VERSION,
    )
    members = tuple(
        CollectionMember(
            collection_id=collection.id,
            lexeme_id=lexeme.id,
            rank=number,
            inclusion_reason=reason,
        )
        for number, (lexeme, _, reason) in enumerate(eligible, start=1)
    )
    report = {
        "collection_id": collection.id,
        "member_count": len(members),
        "junk_counts": dict(sorted(excluded.items())),
        "members_per_band": {
            str(band): sum(member.inclusion_reason == f"ngsl_band_{band}" for member in members)
            for band in range(1, 6)
        },
        "rarity_gate_count": rarity_gate_count,
    }
    return collection, members, report


def write_collection_report(report: dict[str, Any], target: Path) -> None:
    write_text_atomic(
        target, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def collection_member_digest(members: tuple[CollectionMember, ...]) -> str:
    """Return a stable checksum for the complete ordered collection membership."""
    import hashlib

    payload = [member.model_dump(mode="json") for member in members]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def write_collection_jsonl(
    dataset: Dataset,
    collection: Collection,
    members: tuple[CollectionMember, ...],
    rankings: tuple[Ranking, ...],
    curation: tuple[Curation, ...],
    ngsl_members: tuple[ListMember, ...],
    target: Path,
) -> None:
    """Write the filtered collection projection, with its selection facts per lexeme."""
    lexemes = {lexeme.id: lexeme for lexeme in dataset.lexemes}
    ranking_by_lexeme = {item.lexeme_id: item for item in rankings}
    curation_by_lexeme = {item.lexeme_id: item for item in curation}
    ngsl_by_lemma = {item.lemma: item for item in ngsl_members}
    lines = []
    for member in members:
        lexeme = lexemes[member.lexeme_id]
        ranking = ranking_by_lexeme.get(lexeme.id)
        lines.append(
            json.dumps(
                {
                    "collection": collection.model_dump(mode="json"),
                    "curation": curation_by_lexeme[lexeme.id].model_dump(mode="json"),
                    "lexeme": lexeme.model_dump(mode="json"),
                    "member": member.model_dump(mode="json"),
                    "ngsl": ngsl_by_lemma[lexeme.normalized_lemma].model_dump(mode="json"),
                    "ranking": ranking.model_dump(mode="json") if ranking is not None else None,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    write_text_atomic(target, "\n".join(lines) + ("\n" if lines else ""))
