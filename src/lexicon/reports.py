from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .compile import write_text_atomic
from .normalize import NormalizationResult


def write_duplicate_report(result: NormalizationResult, target: Path) -> None:
    duplicates = Counter(result.exact_duplicate_lexeme_ids)
    payload = {
        "input_record_count": result.input_record_count,
        "normalized_lexeme_count": len(result.dataset.lexemes),
        "exact_duplicate_lexemes": [
            {"lexeme_id": lexeme_id, "discarded_record_count": count}
            for lexeme_id, count in sorted(duplicates.items())
        ],
        "conflicting_duplicates": "build failure",
    }
    write_text_atomic(
        target, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
