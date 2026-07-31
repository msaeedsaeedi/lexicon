from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Source(StrictModel):
    id: str
    name: str
    version: str
    source_url: str
    license: str
    retrieved_at: str
    checksum: str | None = None
    requires_source_sense_key: bool = False


class StagedDefinition(StrictModel):
    text: str = Field(min_length=1)
    definition_type: Literal[
        "canonical", "learner", "simple", "child", "technical", "generated"
    ] = "learner"
    audience: str = "general"


class StagedExample(StrictModel):
    text: str = Field(min_length=1)


class StagedSense(StrictModel):
    gloss: str | None = None
    source_sense_key: str | None = None
    definitions: list[StagedDefinition] = Field(min_length=1)
    examples: list[StagedExample] = Field(default_factory=list)


class StagedForm(StrictModel):
    text: str = Field(min_length=1)
    form_type: str = "lemma"
    is_canonical: bool = False


class StagedLexeme(StrictModel):
    source_id: str
    language: str
    lemma: str = Field(min_length=1)
    part_of_speech: str = Field(min_length=1)
    forms: list[StagedForm] = Field(default_factory=list)
    senses: list[StagedSense] = Field(min_length=1)


class Language(StrictModel):
    id: str
    iso_639_1: str
    name: str


class Form(StrictModel):
    id: str
    lexeme_id: str
    text: str
    normalized_text: str
    form_type: str
    is_canonical: bool


class Definition(StrictModel):
    id: str
    sense_id: str
    text: str
    definition_type: str
    audience: str
    source_id: str


class Example(StrictModel):
    id: str
    sense_id: str
    text: str
    source_id: str


class Sense(StrictModel):
    id: str
    lexeme_id: str
    sense_key: str
    source_sense_key: str | None
    gloss: str | None
    definitions: tuple[Definition, ...]
    examples: tuple[Example, ...]


class Lexeme(StrictModel):
    id: str
    language_id: str
    lemma: str
    normalized_lemma: str
    part_of_speech: str
    source_id: str
    forms: tuple[Form, ...]
    senses: tuple[Sense, ...]


class Dataset(StrictModel):
    language: Language
    sources: tuple[Source, ...]
    lexemes: tuple[Lexeme, ...]
