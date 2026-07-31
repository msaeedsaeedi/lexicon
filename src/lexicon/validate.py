from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from pydantic import ValidationError

from .errors import PipelineError
from .model import Dataset, Lexeme


class ArtifactValidationError(PipelineError):
    code = "validation.invalid_artifact"


class DatasetValidationError(PipelineError):
    code = "validation.invalid_dataset"


def validate_dataset(dataset: Dataset) -> dict[str, int]:
    source_ids = {source.id for source in dataset.sources}
    if not source_ids:
        raise DatasetValidationError("dataset must declare at least one source")
    for source in dataset.sources:
        if not source.name or not source.version or not source.license:
            raise DatasetValidationError(
                f"source {source.id} is missing name, version, or license metadata"
            )
        if not urlparse(source.source_url).scheme:
            raise DatasetValidationError(f"source {source.id} has an invalid source URL")
    lexeme_ids = [lexeme.id for lexeme in dataset.lexemes]
    if len(lexeme_ids) != len(set(lexeme_ids)):
        raise DatasetValidationError("dataset contains duplicate lexeme IDs")
    for lexeme in dataset.lexemes:
        if lexeme.source_id not in source_ids:
            raise DatasetValidationError(
                f"lexeme {lexeme.id} references unknown source {lexeme.source_id}"
            )
        if not any(form.is_canonical for form in lexeme.forms):
            raise DatasetValidationError(f"lexeme {lexeme.id} has no canonical form")
        for sense in lexeme.senses:
            for definition in sense.definitions:
                if definition.source_id not in source_ids:
                    raise DatasetValidationError(
                        f"definition {definition.id} references an unknown source"
                    )
            for example in sense.examples:
                if example.source_id not in source_ids:
                    raise DatasetValidationError(
                        f"example {example.id} references an unknown source"
                    )
    return {
        "lexemes": len(dataset.lexemes),
        "forms": sum(len(item.forms) for item in dataset.lexemes),
        "senses": sum(len(item.senses) for item in dataset.lexemes),
        "definitions": sum(
            len(sense.definitions) for item in dataset.lexemes for sense in item.senses
        ),
        "examples": sum(len(sense.examples) for item in dataset.lexemes for sense in item.senses),
    }


def validate_jsonl(path: Path) -> dict[str, int]:
    lexemes: list[Lexeme] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            lexemes.append(Lexeme.model_validate_json(line))
        except ValidationError as error:
            raise ArtifactValidationError(
                f"invalid JSONL record at line {number}: {error}"
            ) from error
    if not lexemes:
        raise ArtifactValidationError("JSONL artifact contains no lexemes")
    ids = [lexeme.id for lexeme in lexemes]
    if len(ids) != len(set(ids)):
        raise ArtifactValidationError("JSONL artifact contains duplicate lexeme IDs")
    return {
        "lexemes": len(lexemes),
        "forms": sum(len(item.forms) for item in lexemes),
        "senses": sum(len(item.senses) for item in lexemes),
        "definitions": sum(len(sense.definitions) for item in lexemes for sense in item.senses),
        "examples": sum(len(sense.examples) for item in lexemes for sense in item.senses),
    }


def validate_sqlite(path: Path) -> dict[str, int]:
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise ArtifactValidationError(f"SQLite foreign-key violations: {violations}")
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        required = {
            "metadata",
            "sources",
            "languages",
            "lexemes",
            "forms",
            "senses",
            "definitions",
            "examples",
        }
        if missing := required - tables:
            raise ArtifactValidationError(f"SQLite artifact missing tables: {sorted(missing)}")
        metadata = dict(connection.execute("SELECT key, value FROM metadata"))
        for key in ("dataset_name", "dataset_version", "schema_version", "pipeline_version"):
            if not metadata.get(key):
                raise ArtifactValidationError(f"SQLite artifact is missing metadata value {key}")
        source_count = connection.execute(
            "SELECT COUNT(*) FROM sources WHERE license = '' OR source_url = ''"
        ).fetchone()[0]
        if source_count:
            raise ArtifactValidationError(
                "SQLite artifact contains sources without license or URL metadata"
            )
        return {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("lexemes", "forms", "senses", "definitions", "examples")
        }
    finally:
        connection.close()


def validate_artifact(path: Path) -> dict[str, int]:
    if path.suffix == ".sqlite":
        return validate_sqlite(path)
    if path.suffix == ".jsonl":
        return validate_jsonl(path)
    raise ArtifactValidationError("artifact must have a .sqlite or .jsonl extension")
