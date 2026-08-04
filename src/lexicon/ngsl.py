"""Checksum-locked NGSL parsing and OEWN lemma mapping."""

from __future__ import annotations

import csv
import hashlib
import os
import shutil
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from .errors import PipelineError
from .model import CuratedList, Dataset, ListMember, Source
from .normalize import normalized_key
from .version import PIPELINE_VERSION


class NGSLError(PipelineError):
    code = "ngsl.invalid_input"


class NGSLSourceLock(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    version: str
    source_url: str
    filename: str
    sha256: str
    license: str
    attribution: str
    released_at: str


@dataclass(frozen=True)
class NGSLImport:
    source: Source
    curated_list: CuratedList
    members: tuple[ListMember, ...]


def load_lock(path: Path) -> NGSLSourceLock:
    try:
        return NGSLSourceLock.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as error:
        raise NGSLError(f"cannot read NGSL source lock: {path}") from error


def acquire(lock: NGSLSourceLock, cache_dir: Path) -> Path:
    target = cache_dir / lock.filename
    if target.is_file() and _sha256(target) == lock.sha256:
        return target
    cache_dir.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{lock.filename}.", dir=cache_dir)
    os.close(descriptor)
    temporary = Path(name)
    try:
        with urllib.request.urlopen(lock.source_url) as response, temporary.open("wb") as handle:
            shutil.copyfileobj(response, handle)
        if _sha256(temporary) != lock.sha256:
            raise NGSLError("downloaded NGSL CSV does not match the pinned checksum")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def import_csv(path: Path, lock: NGSLSourceLock) -> NGSLImport:
    if _sha256(path) != lock.sha256:
        raise NGSLError("NGSL CSV does not match the pinned checksum")
    members: list[ListMember] = []
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                lemma = normalized_key(row.get("Lemma", ""))
                rank = int(row.get("SFI Rank", ""))
                if not lemma or not 1 <= rank <= 2801:
                    continue
                members.append(
                    ListMember(
                        list_id=lock.id,
                        lemma=lemma,
                        rank=rank,
                        band=_band(rank),
                        source_id=lock.id,
                    )
                )
    except (OSError, ValueError, csv.Error) as error:
        raise NGSLError(f"cannot parse NGSL CSV: {path}") from error
    if len({member.lemma for member in members}) != len(members):
        raise NGSLError("NGSL CSV contains duplicate normalized lemmas")
    source = Source(
        id=lock.id,
        name=lock.name,
        version=lock.version,
        source_url=lock.source_url,
        license=lock.license,
        retrieved_at=lock.released_at,
        checksum=lock.sha256,
    )
    return NGSLImport(
        source=source,
        curated_list=CuratedList(
            id=lock.id,
            title=lock.name,
            source_id=lock.id,
            version=lock.version,
            pipeline_version=PIPELINE_VERSION,
        ),
        members=tuple(sorted(members, key=lambda item: item.rank)),
    )


def coverage(
    dataset: Dataset, members: tuple[ListMember, ...], graded_ids: set[str]
) -> dict[str, int]:
    by_lemma: dict[str, set[str]] = {}
    for lexeme in dataset.lexemes:
        by_lemma.setdefault(lexeme.normalized_lemma, set()).add(lexeme.id)
    matched = [member for member in members if member.lemma in by_lemma]
    return {
        "ngsl_words": len(members),
        "matched_to_oewn": len(matched),
        "matched_and_passing_pool": sum(
            bool(by_lemma[member.lemma] & graded_ids) for member in matched
        ),
        "missing_from_oewn": len(members) - len(matched),
    }


def _band(rank: int) -> int:
    if rank <= 560:
        return 1
    if rank <= 1120:
        return 2
    if rank <= 1680:
        return 3
    if rank <= 2240:
        return 4
    return 5


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
