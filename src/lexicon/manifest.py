from __future__ import annotations

import json
from pathlib import Path

from .compile import sha256, write_text_atomic
from .model import Dataset
from .version import DATASET_NAME, DATASET_VERSION, PIPELINE_VERSION, SCHEMA_VERSION


def write_manifest(
    dataset: Dataset,
    artifacts: dict[str, Path],
    target: Path,
    import_report: dict[str, object] | None = None,
) -> None:
    counts = {
        "lexemes": len(dataset.lexemes),
        "forms": sum(len(item.forms) for item in dataset.lexemes),
        "senses": sum(len(item.senses) for item in dataset.lexemes),
        "definitions": sum(
            len(sense.definitions) for item in dataset.lexemes for sense in item.senses
        ),
        "examples": sum(len(sense.examples) for item in dataset.lexemes for sense in item.senses),
    }
    payload = {
        "dataset": DATASET_NAME,
        "dataset_version": DATASET_VERSION,
        "schema_version": SCHEMA_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "language": dataset.language.model_dump(mode="json"),
        "record_counts": counts,
        "sources": [source.model_dump(mode="json") for source in dataset.sources],
        "artifacts": [
            {"name": name, "filename": path.name, "sha256": sha256(path)}
            for name, path in sorted(artifacts.items())
        ],
        "compatibility": {"legacy_word_definition_example_export": True},
        "build": {"network_accessed": False, "deterministic": True},
    }
    if import_report is not None:
        payload["import_report"] = import_report
    write_text_atomic(
        target, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def write_attribution(dataset: Dataset, target: Path) -> None:
    lines = ["# Attribution", "", "This dataset contains source material listed below.", ""]
    for source in dataset.sources:
        lines.extend(
            [
                f"## {source.name} {source.version}",
                "",
                f"- Source: {source.source_url}",
                f"- License: {source.license}",
                f"- Retrieved: {source.retrieved_at}",
                "",
            ]
        )
    write_text_atomic(target, "\n".join(lines))
