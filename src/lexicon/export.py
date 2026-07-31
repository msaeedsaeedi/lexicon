from __future__ import annotations

import json
from pathlib import Path

from .compile import write_text_atomic
from .model import Lexeme


def export_legacy(input_path: Path, output_path: Path) -> int:
    entries: list[dict[str, str]] = []
    for line in input_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        lexeme = Lexeme.model_validate_json(line)
        first_sense = lexeme.senses[0]
        entries.append(
            {
                "word": lexeme.lemma,
                "definition": first_sense.definitions[0].text,
                "example": first_sense.examples[0].text if first_sense.examples else "",
            }
        )
    write_text_atomic(
        output_path, json.dumps(entries, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return len(entries)
