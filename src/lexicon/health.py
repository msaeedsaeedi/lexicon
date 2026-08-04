from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .compile import write_text_atomic
from .errors import PipelineError
from .model import Curation, Dataset
from .normalize import NormalizationResult


class QualityRegressionError(PipelineError):
    code = "quality.regression"


def dataset_health(
    dataset: Dataset,
    normalized: NormalizationResult,
    curation: tuple[Curation, ...] = (),
) -> dict[str, Any]:
    source_ids = {source.id for source in dataset.sources}
    required_source_sense_keys = {
        source.id for source in dataset.sources if source.requires_source_sense_key
    }
    part_of_speech = Counter(lexeme.part_of_speech for lexeme in dataset.lexemes)
    senses = [sense for lexeme in dataset.lexemes for sense in lexeme.senses]
    definitions = [definition for sense in senses for definition in sense.definitions]
    examples = [example for sense in senses for example in sense.examples]
    multiword = sum(
        any(character.isspace() for character in lexeme.lemma) for lexeme in dataset.lexemes
    )
    numeric = sum(lexeme.lemma.isnumeric() for lexeme in dataset.lexemes)
    long = sum(len(lexeme.lemma) > 30 for lexeme in dataset.lexemes)
    eligible = sum(
        not any(character.isspace() for character in lexeme.lemma)
        and not lexeme.lemma.isnumeric()
        and len(lexeme.lemma) <= 30
        and any(sense.examples for sense in lexeme.senses)
        and any(form.is_canonical for form in lexeme.forms)
        for lexeme in dataset.lexemes
    )

    return {
        "source": [
            {"id": source.id, "version": source.version, "checksum": source.checksum}
            for source in dataset.sources
        ],
        "record_counts": {
            "lexemes": len(dataset.lexemes),
            "forms": sum(len(lexeme.forms) for lexeme in dataset.lexemes),
            "senses": len(senses),
            "definitions": len(definitions),
            "examples": len(examples),
        },
        "part_of_speech": dict(sorted(part_of_speech.items())),
        "coverage": {
            "senses_with_examples": sum(bool(sense.examples) for sense in senses),
            "senses_without_examples": sum(not sense.examples for sense in senses),
            # OEWN stores synset glosses as definitions, so this metric is pinned at the total sense count for OEWN builds.
            "senses_without_gloss": sum(sense.gloss is None for sense in senses),
            "senses_without_definitions": sum(not sense.definitions for sense in senses),
            "lexemes_without_canonical_form": sum(
                not any(form.is_canonical for form in lexeme.forms) for lexeme in dataset.lexemes
            ),
            "senses_missing_required_source_sense_key": sum(
                lexeme.source_id in required_source_sense_keys and not sense.source_sense_key
                for lexeme in dataset.lexemes
                for sense in lexeme.senses
            ),
        },
        "missing_source_provenance": {
            "lexemes": sum(lexeme.source_id not in source_ids for lexeme in dataset.lexemes),
            "definitions": sum(item.source_id not in source_ids for item in definitions),
            "examples": sum(item.source_id not in source_ids for item in examples),
        },
        "duplicates": {
            "input_records": normalized.input_record_count,
            "exact_duplicate_input_records": len(normalized.exact_duplicate_lexeme_ids),
        },
        "collection_readiness": {
            "eligible_for_initial_pool": eligible,
            "multiword_exclusions": multiword,
            "numeric_exclusions": numeric,
            "long_exclusions": long,
            "curation": dict(sorted(Counter(item.reason for item in curation).items())),
        },
    }


def write_health_report(report: dict[str, Any], target: Path) -> None:
    write_text_atomic(
        target, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def check_baseline(report: dict[str, Any], baseline_path: Path) -> None:
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise QualityRegressionError(f"cannot read quality baseline: {baseline_path}") from error
    if not isinstance(baseline, dict):
        raise QualityRegressionError("quality baseline must be a JSON object")
    if baseline != report:
        differences = _differences(baseline, report)
        raise QualityRegressionError(
            "dataset health differs from baseline: " + "; ".join(differences[:8])
        )


def _differences(expected: object, actual: object, prefix: str = "") -> list[str]:
    if isinstance(expected, dict) and isinstance(actual, dict):
        keys = sorted(set(expected) | set(actual))
        return [
            difference
            for key in keys
            for difference in _differences(expected.get(key), actual.get(key), f"{prefix}{key}.")
        ]
    if expected != actual:
        return [f"{prefix.rstrip('.')}: expected {expected!r}, got {actual!r}"]
    return []
