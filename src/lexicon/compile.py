from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path

from .model import Dataset

SQL_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE languages (
  id TEXT PRIMARY KEY,
  iso_639_1 TEXT NOT NULL,
  name TEXT NOT NULL
);
CREATE TABLE sources (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  source_url TEXT NOT NULL,
  license TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  checksum TEXT,
  requires_source_sense_key INTEGER NOT NULL CHECK (requires_source_sense_key IN (0, 1))
);
CREATE TABLE lexemes (
  id TEXT PRIMARY KEY,
  language_id TEXT NOT NULL REFERENCES languages(id),
  lemma TEXT NOT NULL,
  normalized_lemma TEXT NOT NULL,
  part_of_speech TEXT NOT NULL,
  source_id TEXT NOT NULL REFERENCES sources(id)
);
CREATE TABLE forms (
  id TEXT PRIMARY KEY,
  lexeme_id TEXT NOT NULL REFERENCES lexemes(id),
  text TEXT NOT NULL,
  normalized_text TEXT NOT NULL,
  form_type TEXT NOT NULL,
  is_canonical INTEGER NOT NULL CHECK (is_canonical IN (0, 1))
);
CREATE TABLE senses (
  id TEXT PRIMARY KEY,
  lexeme_id TEXT NOT NULL REFERENCES lexemes(id),
  sense_key TEXT NOT NULL,
  source_sense_key TEXT,
  gloss TEXT
);
CREATE TABLE definitions (
  id TEXT PRIMARY KEY,
  sense_id TEXT NOT NULL REFERENCES senses(id),
  text TEXT NOT NULL,
  definition_type TEXT NOT NULL,
  audience TEXT NOT NULL,
  source_id TEXT NOT NULL REFERENCES sources(id)
);
CREATE TABLE examples (
  id TEXT PRIMARY KEY,
  sense_id TEXT NOT NULL REFERENCES senses(id),
  text TEXT NOT NULL,
  source_id TEXT NOT NULL REFERENCES sources(id)
);
CREATE INDEX forms_lexeme_id ON forms(lexeme_id);
CREATE INDEX senses_lexeme_id ON senses(lexeme_id);
CREATE INDEX senses_source_sense_key ON senses(source_sense_key);
CREATE INDEX definitions_sense_id ON definitions(sense_id);
CREATE INDEX examples_sense_id ON examples(sense_id);
"""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_path(target: Path) -> tuple[Path, int]:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    return Path(name), descriptor


def write_text_atomic(target: Path, content: str) -> None:
    temporary, descriptor = _atomic_path(target)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        temporary.replace(target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def write_jsonl(dataset: Dataset, target: Path) -> None:
    temporary, descriptor = _atomic_path(target)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            for lexeme in dataset.lexemes:
                handle.write(
                    json.dumps(lexeme.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
                )
                handle.write("\n")
        temporary.replace(target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def write_sqlite(dataset: Dataset, target: Path, metadata: dict[str, str]) -> None:
    temporary, descriptor = _atomic_path(target)
    os.close(descriptor)
    try:
        connection = sqlite3.connect(temporary)
        try:
            connection.executescript(SQL_SCHEMA)
            connection.executemany(
                "INSERT INTO metadata(key, value) VALUES (?, ?)", sorted(metadata.items())
            )
            connection.execute(
                "INSERT INTO languages(id, iso_639_1, name) VALUES (?, ?, ?)",
                (dataset.language.id, dataset.language.iso_639_1, dataset.language.name),
            )
            connection.executemany(
                "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        source.id,
                        source.name,
                        source.version,
                        source.source_url,
                        source.license,
                        source.retrieved_at,
                        source.checksum,
                        int(source.requires_source_sense_key),
                    )
                    for source in dataset.sources
                ],
            )
            for lexeme in dataset.lexemes:
                connection.execute(
                    "INSERT INTO lexemes VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        lexeme.id,
                        lexeme.language_id,
                        lexeme.lemma,
                        lexeme.normalized_lemma,
                        lexeme.part_of_speech,
                        lexeme.source_id,
                    ),
                )
                connection.executemany(
                    "INSERT INTO forms VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        (
                            form.id,
                            form.lexeme_id,
                            form.text,
                            form.normalized_text,
                            form.form_type,
                            int(form.is_canonical),
                        )
                        for form in lexeme.forms
                    ],
                )
                for sense in lexeme.senses:
                    connection.execute(
                        "INSERT INTO senses VALUES (?, ?, ?, ?, ?)",
                        (
                            sense.id,
                            sense.lexeme_id,
                            sense.sense_key,
                            sense.source_sense_key,
                            sense.gloss,
                        ),
                    )
                    connection.executemany(
                        "INSERT INTO definitions VALUES (?, ?, ?, ?, ?, ?)",
                        [
                            (
                                item.id,
                                item.sense_id,
                                item.text,
                                item.definition_type,
                                item.audience,
                                item.source_id,
                            )
                            for item in sense.definitions
                        ],
                    )
                    connection.executemany(
                        "INSERT INTO examples VALUES (?, ?, ?, ?)",
                        [
                            (item.id, item.sense_id, item.text, item.source_id)
                            for item in sense.examples
                        ],
                    )
            connection.commit()
            connection.execute("VACUUM")
        finally:
            connection.close()
        temporary.replace(target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
