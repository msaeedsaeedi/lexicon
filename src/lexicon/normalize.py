from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .errors import PipelineError
from .model import (
    Dataset,
    Definition,
    Example,
    Form,
    Language,
    Lexeme,
    Sense,
    Source,
    StagedForm,
    StagedLexeme,
)

POS_ALIASES = {"adj": "adjective", "adv": "adverb", "n": "noun", "v": "verb"}
LANGUAGE_NAMES = {"en": "English"}


class NormalizationError(PipelineError):
    code = "normalization.invalid_record"


@dataclass(frozen=True)
class NormalizationResult:
    dataset: Dataset
    input_record_count: int
    exact_duplicate_lexeme_ids: tuple[str, ...]


def normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def normalized_key(value: str) -> str:
    return normalize_text(value).casefold()


def identifier_fragment(value: str) -> str:
    collapsed = re.sub(r"[^a-z0-9]+", "-", normalized_key(value))
    return collapsed.strip("-")


def normalize_dataset(sources: tuple[Source, ...], records: tuple[StagedLexeme, ...]) -> Dataset:
    return normalize_dataset_with_report(sources, records).dataset


def normalize_dataset_with_report(
    sources: tuple[Source, ...], records: tuple[StagedLexeme, ...]
) -> NormalizationResult:
    source_ids = {source.id for source in sources}
    if len(source_ids) != len(sources):
        raise NormalizationError("source IDs must be unique")

    normalized: dict[str, Lexeme] = {}
    exact_duplicate_lexeme_ids: list[str] = []
    language_ids: set[str] = set()
    for record in records:
        if record.source_id not in source_ids:
            raise NormalizationError(f"unknown source ID: {record.source_id}")
        lexeme = normalize_lexeme(record)
        language_ids.add(lexeme.language_id)
        existing = normalized.get(lexeme.id)
        if existing is None:
            normalized[lexeme.id] = lexeme
        elif existing != lexeme:
            raise NormalizationError(f"conflicting records resolve to lexeme ID {lexeme.id}")
        else:
            exact_duplicate_lexeme_ids.append(lexeme.id)

    if language_ids != {"en"}:
        raise NormalizationError("v0.1.0 supports only the en language dataset")
    dataset = Dataset(
        language=Language(id="en", iso_639_1="en", name=LANGUAGE_NAMES["en"]),
        sources=tuple(sorted(sources, key=lambda source: source.id)),
        lexemes=tuple(sorted(normalized.values(), key=lambda lexeme: lexeme.id)),
    )
    return NormalizationResult(
        dataset=dataset,
        input_record_count=len(records),
        exact_duplicate_lexeme_ids=tuple(sorted(exact_duplicate_lexeme_ids)),
    )


def normalize_lexeme(record: StagedLexeme) -> Lexeme:
    language = normalized_key(record.language)
    if language != "en":
        raise NormalizationError(f"unsupported language: {record.language}")
    normalized_lemma = normalized_key(record.lemma)
    lemma = normalized_lemma
    pos = POS_ALIASES.get(normalized_key(record.part_of_speech), normalized_key(record.part_of_speech))
    allowed_pos = {"noun", "verb", "adjective", "adverb"}
    if pos not in allowed_pos:
        raise NormalizationError(f"unsupported part of speech: {record.part_of_speech}")
    lexeme_id = f"{language}:{identifier_fragment(lemma)}:{pos}"

    staged_forms = list(record.forms)
    staged_forms.append(StagedForm(text=lemma, form_type="lemma", is_canonical=True))
    forms_by_text: dict[str, Form] = {}
    for staged_form in staged_forms:
        text = normalize_text(staged_form.text)
        form_type = normalize_text(staged_form.form_type)
        is_canonical = staged_form.is_canonical
        key = normalized_key(text)
        if key == normalized_lemma:
            text = lemma
        form = Form(
            id=f"{lexeme_id}:form:{identifier_fragment(text)}",
            lexeme_id=lexeme_id,
            text=text,
            normalized_text=key,
            form_type=form_type,
            is_canonical=is_canonical or key == normalized_lemma,
        )
        forms_by_text[key] = form

    senses: list[Sense] = []
    for sense_number, staged_sense in enumerate(record.senses, start=1):
        sense_id = f"{lexeme_id}:{sense_number}"
        definitions = tuple(
            Definition(
                id=f"{sense_id}:definition:{number}",
                sense_id=sense_id,
                text=normalize_text(definition.text),
                definition_type=definition.definition_type,
                audience=normalize_text(definition.audience),
                source_id=record.source_id,
            )
            for number, definition in enumerate(staged_sense.definitions, start=1)
        )
        examples = tuple(
            Example(
                id=f"{sense_id}:example:{number}",
                sense_id=sense_id,
                text=normalize_text(example.text),
                source_id=record.source_id,
            )
            for number, example in enumerate(staged_sense.examples, start=1)
        )
        senses.append(
            Sense(
                id=sense_id,
                lexeme_id=lexeme_id,
                sense_key=str(sense_number),
                gloss=normalize_text(staged_sense.gloss) if staged_sense.gloss else None,
                definitions=definitions,
                examples=examples,
            )
        )
    return Lexeme(
        id=lexeme_id,
        language_id=language,
        lemma=lemma,
        normalized_lemma=normalized_lemma,
        part_of_speech=pos,
        source_id=record.source_id,
        forms=tuple(sorted(forms_by_text.values(), key=lambda form: form.id)),
        senses=tuple(senses),
    )
