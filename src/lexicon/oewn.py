from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import urllib.request
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from .compile import write_text_atomic
from .errors import PipelineError
from .model import Source, StagedDefinition, StagedExample, StagedLexeme, StagedSense


class OEWNError(PipelineError):
    code = "oewn.invalid_input"


class OEWNLock(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    version: str
    distribution_url: str
    filename: str
    sha256: str
    license: str
    attribution_url: str
    released_at: str
    scope: str


@dataclass(frozen=True)
class OEWNImportResult:
    source: Source
    records: tuple[StagedLexeme, ...]
    synset_count: int
    example_count: int


def load_lock(path: Path) -> OEWNLock:
    try:
        return OEWNLock.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as error:
        raise OEWNError(f"cannot read OEWN source lock: {path}") from error


def acquire(lock: OEWNLock, cache_dir: Path) -> Path:
    target = cache_dir / lock.filename
    if target.is_file() and _sha256(target) == lock.sha256:
        return target
    cache_dir.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{lock.filename}.", dir=cache_dir)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with (
            urllib.request.urlopen(lock.distribution_url) as response,
            temporary.open("wb") as handle,
        ):
            shutil.copyfileobj(response, handle)
        if _sha256(temporary) != lock.sha256:
            raise OEWNError("downloaded OEWN archive does not match the pinned checksum")
        temporary.replace(target)
    except OSError as error:
        raise OEWNError(f"could not acquire OEWN archive: {error}") from error
    finally:
        temporary.unlink(missing_ok=True)
    return target


def import_archive(archive: Path, lock: OEWNLock) -> OEWNImportResult:
    if _sha256(archive) != lock.sha256:
        raise OEWNError("OEWN archive does not match the pinned checksum")
    grouped: dict[tuple[str, str], dict[str, StagedSense]] = defaultdict(dict)
    synset_count = 0
    example_count = 0
    try:
        with zipfile.ZipFile(archive) as package:
            names = set(package.namelist())
            for filename, pos in (
                ("data.noun", "noun"),
                ("data.verb", "verb"),
                ("data.adj", "adjective"),
                ("data.adv", "adverb"),
            ):
                member = next((name for name in names if name.endswith(f"/{filename}")), None)
                if member is None:
                    raise OEWNError(f"OEWN archive is missing {filename}")
                for raw_line in package.read(member).decode("utf-8").splitlines():
                    parsed = _parse_data_line(raw_line, pos, lock)
                    if parsed is None:
                        continue
                    synset_key, lemmas, sense = parsed
                    synset_count += 1
                    example_count += len(sense.examples)
                    for lemma in lemmas:
                        grouped[(lemma.casefold(), pos)][sense.source_sense_key or ""] = sense
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile) as error:
        raise OEWNError(f"cannot parse OEWN archive: {error}") from error

    records = tuple(
        StagedLexeme(
            source_id=lock.id,
            language="en",
            lemma=lemma,
            part_of_speech=pos,
            senses=[sense for _, sense in sorted(senses.items())],
        )
        for (lemma, pos), senses in sorted(grouped.items())
    )
    source = Source(
        id=lock.id,
        name=lock.name,
        version=lock.version,
        source_url=lock.distribution_url,
        license=lock.license,
        retrieved_at=lock.released_at,
        checksum=lock.sha256,
        requires_source_sense_key=True,
    )
    return OEWNImportResult(source, records, synset_count, example_count)


def write_staging(result: OEWNImportResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_text_atomic(
        output_dir / "sources.json",
        json.dumps([result.source.model_dump(mode="json")], ensure_ascii=False, indent=2) + "\n",
    )
    records = "".join(
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n"
        for record in result.records
    )
    write_text_atomic(output_dir / "records.jsonl", records)
    report = {
        "source": result.source.id,
        "synsets": result.synset_count,
        "lexemes": len(result.records),
        "senses": sum(len(record.senses) for record in result.records),
        "synset_examples": result.example_count,
        "skipped_records": 0,
    }
    write_text_atomic(
        output_dir / "import-report.json",
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _parse_data_line(
    line: str, part_of_speech: str, lock: OEWNLock
) -> tuple[str, tuple[str, ...], StagedSense] | None:
    if " | " not in line or not line[:8].isdigit():
        return None
    payload, gloss = line.split(" | ", maxsplit=1)
    fields = payload.split()
    if len(fields) < 4:
        raise OEWNError(f"malformed OEWN data line: {line[:80]}")
    offset, source_pos, word_count = fields[0], fields[2], int(fields[3], 16)
    if source_pos not in {"n", "v", "a", "s", "r"}:
        raise OEWNError(f"unsupported OEWN part of speech: {source_pos}")
    lemma_positions = range(4, 4 + word_count * 2, 2)
    if len(fields) <= max(lemma_positions, default=0):
        raise OEWNError(f"malformed OEWN lemma section: {line[:80]}")
    lemmas = tuple(fields[position].replace("_", " ") for position in lemma_positions)
    definition = gloss.split(";", maxsplit=1)[0].strip()
    if not definition:
        raise OEWNError(f"OEWN synset {offset} has no definition")
    examples = tuple(
        StagedExample(text=match[0] or match[1])
        for match in re.findall(r'"([^"]+)"|“([^”]+)”', gloss)
    )
    source_sense_key = f"{lock.id}:{offset}-{source_pos}"
    return (
        source_sense_key,
        lemmas,
        StagedSense(
            source_sense_key=source_sense_key,
            definitions=[StagedDefinition(text=definition, definition_type="canonical")],
            examples=list(examples),
        ),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
