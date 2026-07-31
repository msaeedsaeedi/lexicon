# Lexicon pipeline

`lexicon` builds deterministic, versioned lexical dataset artifacts for Vocab. It contains
language knowledge only: it does not contain learner progress, scheduling, or application state.

v0.3.0 imports the OEWN 2025 common edition through a checksum-locked acquisition step. The
published dataset is OEWN-only; the curated seed remains a small pipeline fixture.

## Quick start

```bash
uv sync
uv run lexicon acquire-oewn --cache .cache/raw
uv run lexicon import-oewn --input .cache/raw/english-wordnet-2025.zip --output staging/oewn-2025
uv run lexicon build --input staging/oewn-2025 --import-report staging/oewn-2025/import-report.json --output artifacts
uv run lexicon validate artifacts
```

The OEWN archive URL and SHA-256 are committed in `data/sources/oewn-2025.lock.json`; raw archives
are cached locally and ignored by Git. Builds automatically apply the checked-in `data/overrides/`
corrections; pass `--overrides PATH` to use another override directory. See `docs/overrides.md`
for how overrides behave. Each build writes `duplicate-report.json`, and conflicting normalized
duplicates stop the build.

Expected input and validation errors are printed with a stable category, for example
`error [overrides.invalid_configuration]: ...`.

OEWN is licensed CC-BY 4.0 and is attributed in every release bundle. Semantic relations,
frequency, pronunciation, morphology, and AI enrichment are outside v0.2.0.

## Release a dataset bundle

```bash
uv run python scripts/release.py
```

This checks formatting, linting, types, and tests; builds a fresh bundle under
`dist/lexicon-en-oewn-0.3.0`; checks its health against the committed OEWN baseline; creates the
legacy compatibility export; and verifies all artifact and release-manifest checksums. The command
fails rather than overwriting an existing release.

See [the Vocab consumer contract](docs/consumer-contract.md) for the runtime boundary.
