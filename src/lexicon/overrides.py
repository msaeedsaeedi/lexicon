from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .errors import PipelineError
from .model import Dataset, Lexeme, Sense
from .normalize import normalize_text


class OverrideError(PipelineError):
    code = "overrides.invalid_configuration"


class StrictOverride(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BlockedLexeme(StrictOverride):
    lexeme_id: str
    reason: str = Field(min_length=1)


class DefinitionFix(StrictOverride):
    definition_id: str
    text: str = Field(min_length=1)


class Overrides(StrictOverride):
    blocked_lexemes: tuple[BlockedLexeme, ...] = ()
    definition_fixes: tuple[DefinitionFix, ...] = ()


def load_overrides(directory: Path | None) -> Overrides:
    if directory is None or not directory.exists():
        return Overrides()
    try:
        blocked = json.loads((directory / "blocked-lexemes.json").read_text(encoding="utf-8"))
        fixes = json.loads((directory / "definition-fixes.json").read_text(encoding="utf-8"))
        return Overrides(blocked_lexemes=blocked, definition_fixes=fixes)
    except FileNotFoundError as error:
        raise OverrideError(f"override directory must contain {error.filename}") from error
    except (json.JSONDecodeError, ValidationError) as error:
        raise OverrideError(f"invalid override configuration: {error}") from error


def apply_overrides(dataset: Dataset, overrides: Overrides) -> Dataset:
    blocked = {item.lexeme_id for item in overrides.blocked_lexemes}
    lexeme_ids = {item.id for item in dataset.lexemes}
    unknown_blocks = blocked - lexeme_ids
    if unknown_blocks:
        raise OverrideError(f"blocked lexeme IDs do not exist: {sorted(unknown_blocks)}")

    fixes = {item.definition_id: normalize_text(item.text) for item in overrides.definition_fixes}
    if len(fixes) != len(overrides.definition_fixes):
        raise OverrideError("definition fixes must not repeat a definition ID")
    available_definitions = {
        definition.id
        for lexeme in dataset.lexemes
        for sense in lexeme.senses
        for definition in sense.definitions
    }
    unknown_fixes = set(fixes) - available_definitions
    if unknown_fixes:
        raise OverrideError(f"definition fix IDs do not exist: {sorted(unknown_fixes)}")

    lexemes = tuple(
        _apply_lexeme_fixes(lexeme, fixes) for lexeme in dataset.lexemes if lexeme.id not in blocked
    )
    return dataset.model_copy(update={"lexemes": lexemes})


def _apply_lexeme_fixes(lexeme: Lexeme, fixes: dict[str, str]) -> Lexeme:
    senses = tuple(_apply_sense_fixes(sense, fixes) for sense in lexeme.senses)
    return lexeme.model_copy(update={"senses": senses})


def _apply_sense_fixes(sense: Sense, fixes: dict[str, str]) -> Sense:
    definitions = tuple(
        definition.model_copy(update={"text": fixes.get(definition.id, definition.text)})
        for definition in sense.definitions
    )
    return sense.model_copy(update={"definitions": definitions})
