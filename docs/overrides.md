# Overrides — curated corrections

## What overrides are for

Raw seed and source data is treated as immutable and auditable. Overrides
let you apply curated corrections to a build without editing that source, so every fix stays
version-controlled, reviewable, and reproducible on a fresh rebuild.

Use overrides for corrections to already-normalized data:

- Remove a lexeme that should not ship (bad entry, licensing concern, fixture coverage).
- Fix the text of a definition that came out wrong.

Overrides are not for structural changes (new senses, new lexemes, schema changes). Those belong in
the seed records or a future source importer.

## Where overrides sit in the pipeline

```text
load_staging → normalize → apply_overrides → validate_dataset → compile → manifest
```

Overrides are applied **after normalization and before validation and artifact compilation**. The
raw source is never modified; the override is a layer on top of the normalized dataset.

## Selecting the override directory

- Default: `--input`'s parent `/overrides`. For `--input data/seed` that is `data/overrides`.
- Use `--overrides PATH` to point at a different directory.

```bash
uv run lexicon build --input data/seed --output artifacts                # uses data/overrides
uv run lexicon build --input data/seed --overrides overrides/release-1  --output artifacts
```

- If the selected directory does not exist, overrides are a no-op and the build proceeds.
- If the directory **exists**, it must contain **both** files below. A missing file fails the build
  with `error [overrides.invalid_configuration]`.

## File formats

### blocked-lexemes.json

A JSON array of `{ "lexeme_id", "reason" }` entries. `reason` is required (minimum one character)
and exists for humans and audits; the build only uses `lexeme_id`.

```json
[
  { "lexeme_id": "en:record:noun", "reason": "fixture coverage" }
]
```

Blocked lexemes are removed from the dataset before compilation, so they also disappear from the
record counts in the manifest and from both artifacts.

### definition-fixes.json

A JSON array of `{ "definition_id", "text" }` entries. `text` is required (minimum one character)
and is normalized with the same NFKC Unicode and whitespace rules as the rest of the pipeline, so
write it naturally.

```json
[
  { "definition_id": "en:ambiguous:adjective:1:definition:1", "text": "Having several possible meanings." }
]
```

## Behaviour and guarantees

- Override configuration is strict: unknown keys in an entry fail validation
  (`extra="forbid"`), as do malformed JSON or non-array file contents.
- Every referenced ID must exist in the **normalized dataset**. Unknown lexeme or definition IDs
  fail the build — a typo can never silently no-op.
- Definition IDs must not repeat in the file.
- Because IDs are content-derived, a fix stays valid across rebuilds as long as the underlying
  lexeme does not change.
- A definition fix on a lexeme that is also blocked is dropped: the lexeme is removed anyway.
- The manifest `record_counts` reflect the dataset **after** overrides. The `duplicate-report.json`
  is generated from normalization (before overrides), so its `normalized_lexeme_count` may be
  higher than the manifest count when lexemes are blocked.

## Errors

All override failures share the category `overrides.invalid_configuration` and abort the build
with exit code 1. Examples:

```text
error [overrides.invalid_configuration]: override directory must contain /path/definition-fixes.json
error [overrides.invalid_configuration]: blocked lexeme IDs do not exist: ['en:missing:noun']
error [overrides.invalid_configuration]: definition fix IDs do not exist: ['en:missing:1:definition:1']
error [overrides.invalid_configuration]: definition fixes must not repeat a definition ID
error [overrides.invalid_configuration]: invalid override configuration: ...
```

## Verification

After a build with overrides, confirm the results:

```bash
uv run lexicon validate artifacts/lexicon-en-core-0.1.0.jsonl
uv run lexicon inspect artifacts/lexicon-en-core-0.1.0.sqlite
```

The SQLite and JSONL artifacts must reflect the same overridden dataset; both are compiled from the
same normalized-and-overridden `Dataset` object.
