from __future__ import annotations

import sqlite3
from pathlib import Path

from pydantic import ValidationError

from .model import Lexeme


class ArtifactValidationError(ValueError):
    pass


def validate_jsonl(path: Path) -> dict[str, int]:
    lexemes: list[Lexeme] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            lexemes.append(Lexeme.model_validate_json(line))
        except ValidationError as error:
            raise ArtifactValidationError(f"invalid JSONL record at line {number}: {error}") from error
    if not lexemes:
        raise ArtifactValidationError("JSONL artifact contains no lexemes")
    ids = [lexeme.id for lexeme in lexemes]
    if len(ids) != len(set(ids)):
        raise ArtifactValidationError("JSONL artifact contains duplicate lexeme IDs")
    return {"lexemes": len(lexemes), "forms": sum(len(item.forms) for item in lexemes), "senses": sum(len(item.senses) for item in lexemes)}


def validate_sqlite(path: Path) -> dict[str, int]:
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise ArtifactValidationError(f"SQLite foreign-key violations: {violations}")
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {"metadata", "sources", "languages", "lexemes", "forms", "senses", "definitions", "examples"}
        if missing := required - tables:
            raise ArtifactValidationError(f"SQLite artifact missing tables: {sorted(missing)}")
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
