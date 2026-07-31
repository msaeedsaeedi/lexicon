from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from .errors import PipelineError
from .model import Source, StagedLexeme


class StagingError(PipelineError):
    code = "staging.invalid_input"


def load_staging(input_dir: Path) -> tuple[tuple[Source, ...], tuple[StagedLexeme, ...]]:
    sources_path = input_dir / "sources.json"
    records_path = input_dir / "records.jsonl"
    try:
        sources_data = json.loads(sources_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StagingError(f"cannot read source metadata: {sources_path}: {error}") from error

    try:
        sources = tuple(Source.model_validate(item) for item in sources_data)
    except ValidationError as error:
        raise StagingError(f"invalid source metadata: {error}") from error

    records: list[StagedLexeme] = []
    try:
        lines = records_path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise StagingError(f"cannot read staging records: {records_path}: {error}") from error
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            records.append(StagedLexeme.model_validate_json(line))
        except ValidationError as error:
            raise StagingError(f"invalid staging record at line {number}: {error}") from error
    if not records:
        raise StagingError("staging records are empty")
    return sources, tuple(records)
