# Lexicon pipeline

`lexicon` builds deterministic, versioned lexical dataset artifacts for Vocab. It contains
language knowledge only: it does not contain learner progress, scheduling, or application state.

## Quick start

```bash
uv sync
uv run lexicon build --input data/seed --output artifacts
uv run lexicon validate artifacts/lexicon-en-core-0.1.0.sqlite
uv run lexicon inspect artifacts/lexicon-en-core-0.1.0.jsonl
uv run lexicon export-legacy --input artifacts/lexicon-en-core-0.1.0.jsonl --output artifacts/vocab-compat-0.1.0.json
```

The checked-in seed is deliberately small and curated. Builds automatically apply the checked-in
`data/overrides/` corrections; pass `--overrides PATH` to use another override directory. See
`docs/overrides.md` for how overrides behave. Each build writes `duplicate-report.json`, and
conflicting normalized duplicates stop the build.

Expected input and validation errors are printed with a stable category, for example
`error [overrides.invalid_configuration]: ...`.

External source acquisition and AI enrichment are outside v0.1.x.
