# Lexicon pipeline

`lexicon` builds deterministic, versioned lexical dataset artifacts for Vocab. It contains
language knowledge only: it does not contain learner progress, scheduling, or application state.

## Quick start

```bash
uv sync
uv run lexicon build --input data/seed --output artifacts
uv run lexicon validate artifacts/lexicon-en-core-0.1.2.sqlite
uv run lexicon inspect artifacts/lexicon-en-core-0.1.2.jsonl
uv run lexicon export-legacy --input artifacts/lexicon-en-core-0.1.2.jsonl --output artifacts/vocab-compat-0.1.2.json
```

The checked-in seed is deliberately small and curated. Builds automatically apply the checked-in
`data/overrides/` corrections; pass `--overrides PATH` to use another override directory. See
`docs/overrides.md` for how overrides behave. Each build writes `duplicate-report.json`, and
conflicting normalized duplicates stop the build.

Expected input and validation errors are printed with a stable category, for example
`error [overrides.invalid_configuration]: ...`.

External source acquisition and AI enrichment are outside v0.1.x.

## Release a dataset bundle

```bash
uv run python scripts/release.py
```

This checks formatting, linting, types, and tests; builds a fresh bundle under
`dist/lexicon-en-core-0.1.2`; creates the legacy compatibility export; and verifies all artifact
and release-manifest checksums. The command fails rather than overwriting an existing release.

See [the Vocab consumer contract](docs/consumer-contract.md) for the runtime boundary.
