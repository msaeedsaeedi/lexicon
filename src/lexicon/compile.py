from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path

from .model import Collection, CollectionMember, CuratedList, Curation, Dataset, ListMember, Ranking

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
CREATE TABLE rankings (
  lexeme_id TEXT PRIMARY KEY REFERENCES lexemes(id),
  rank INTEGER NOT NULL CHECK (rank >= 1),
  zipf REAL NOT NULL CHECK (zipf >= 0),
  source_id TEXT NOT NULL REFERENCES sources(id)
);
CREATE TABLE collections (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  selection_basis TEXT NOT NULL,
  version TEXT NOT NULL,
  pipeline_version TEXT NOT NULL
);
CREATE TABLE collection_members (
  collection_id TEXT NOT NULL REFERENCES collections(id),
  lexeme_id TEXT NOT NULL REFERENCES lexemes(id),
  sense_id TEXT REFERENCES senses(id),
  rank INTEGER NOT NULL CHECK (rank >= 1),
  inclusion_reason TEXT NOT NULL,
  UNIQUE(collection_id, lexeme_id)
);
CREATE TABLE curated_lists (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  source_id TEXT NOT NULL REFERENCES sources(id),
  version TEXT NOT NULL,
  pipeline_version TEXT NOT NULL
);
CREATE TABLE list_members (
  list_id TEXT NOT NULL REFERENCES curated_lists(id),
  lemma TEXT NOT NULL,
  rank INTEGER NOT NULL CHECK (rank >= 1),
  band INTEGER NOT NULL CHECK (band BETWEEN 1 AND 5),
  part_of_speech TEXT,
  source_id TEXT NOT NULL REFERENCES sources(id),
  UNIQUE(list_id, lemma)
);
CREATE TABLE curation (
  lexeme_id TEXT PRIMARY KEY REFERENCES lexemes(id),
  grade TEXT NOT NULL,
  reason TEXT NOT NULL,
  pipeline_version TEXT NOT NULL
);
CREATE INDEX forms_lexeme_id ON forms(lexeme_id);
CREATE INDEX senses_lexeme_id ON senses(lexeme_id);
CREATE INDEX senses_source_sense_key ON senses(source_sense_key);
CREATE INDEX definitions_sense_id ON definitions(sense_id);
CREATE INDEX examples_sense_id ON examples(sense_id);
CREATE INDEX collection_members_collection_id_rank ON collection_members(collection_id, rank);
CREATE INDEX list_members_list_id_rank ON list_members(list_id, rank);
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


def write_bytes_atomic(target: Path, content: bytes) -> None:
    temporary, descriptor = _atomic_path(target)
    try:
        with os.fdopen(descriptor, "wb") as handle:
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


def write_sqlite(
    dataset: Dataset,
    target: Path,
    metadata: dict[str, str],
    rankings: tuple[Ranking, ...] = (),
    collections: tuple[Collection, ...] = (),
    collection_members: tuple[CollectionMember, ...] = (),
    curated_lists: tuple[CuratedList, ...] = (),
    list_members: tuple[ListMember, ...] = (),
    curation: tuple[Curation, ...] = (),
) -> None:
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
            connection.executemany(
                "INSERT INTO curated_lists VALUES (?, ?, ?, ?, ?)",
                [
                    (item.id, item.title, item.source_id, item.version, item.pipeline_version)
                    for item in curated_lists
                ],
            )
            connection.executemany(
                "INSERT INTO list_members VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        item.list_id,
                        item.lemma,
                        item.rank,
                        item.band,
                        item.part_of_speech,
                        item.source_id,
                    )
                    for item in list_members
                ],
            )
            connection.executemany(
                "INSERT INTO curation VALUES (?, ?, ?, ?)",
                [
                    (item.lexeme_id, item.grade, item.reason, item.pipeline_version)
                    for item in curation
                ],
            )
            connection.executemany(
                "INSERT INTO rankings VALUES (?, ?, ?, ?)",
                [
                    (ranking.lexeme_id, ranking.rank, ranking.zipf, ranking.source_id)
                    for ranking in rankings
                ],
            )
            connection.executemany(
                "INSERT INTO collections VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        collection.id,
                        collection.title,
                        collection.selection_basis,
                        collection.version,
                        collection.pipeline_version,
                    )
                    for collection in collections
                ],
            )
            connection.executemany(
                "INSERT INTO collection_members VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        member.collection_id,
                        member.lexeme_id,
                        member.sense_id,
                        member.rank,
                        member.inclusion_reason,
                    )
                    for member in collection_members
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
