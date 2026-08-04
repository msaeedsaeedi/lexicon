# Lexicon pipeline

`lexicon` builds deterministic, versioned lexical dataset artifacts for Vocab. It contains
language knowledge only: it does not contain learner progress, scheduling, or application state.

v0.5.0 adds deterministic English lemma frequency rankings from wordfreq 3.1.1, the NGSL 1.2
learner-list backbone, curation, and the `en-general-starter` collection on top of the OEWN 2025
common edition. Schema 0.3.0 adds `rankings`, `collections`, `collection_members`,
`curated_lists`, `list_members`, and `curation` without changing the existing canonical tables.

## Quick start

```bash
uv sync
uv run lexicon acquire-oewn --cache .cache/raw
uv run lexicon import-oewn --input .cache/raw/english-wordnet-2025.zip --output staging/oewn-2025
uv run lexicon acquire-ngsl --cache .cache/raw
uv run lexicon build --input staging/oewn-2025 --import-report staging/oewn-2025/import-report.json --output artifacts
uv run lexicon validate artifacts
```

`build` now runs curation, the NGSL backbone, frequency rankings, and the starter collection, and
writes `collection-report.json` and `en-general-starter-<version>.jsonl` alongside the canonical
artifacts. Source URLs and SHA-256 checksums are committed in `data/sources/`
(`oewn-2025.lock.json`, `ngsl.lock.json`, `frequency.lock.json`); raw archives are cached locally
and ignored by Git. Builds automatically apply the checked-in `data/overrides/` corrections; pass
`--overrides PATH` to use another override directory. See `docs/overrides.md` for how overrides
behave. Each build writes `duplicate-report.json`, and conflicting normalized duplicates stop the
build.

Expected input and validation errors are printed with a stable category, for example
`error [overrides.invalid_configuration]: ...`.

OEWN is licensed CC-BY 4.0, NGSL is licensed CC-BY-SA 4.0, and wordfreq is licensed
Apache-2.0 (code) / CC-BY-SA 4.0 (data); all are attributed in every release bundle. Semantic
relations, pronunciation, morphology, and AI enrichment are outside v0.5.0.

## Release a dataset bundle

`scripts/release.py` is the developer preflight and single source of release assembly and
verification:

```bash
uv run python scripts/release.py
```

This checks formatting, linting, types, and tests; builds a fresh bundle under
`dist/lexicon-en-oewn-0.5.0`; checks its health against the committed OEWN baseline; verifies the
collection report and filtered collection JSONL against SQLite; creates the legacy compatibility
export; verifies all artifact and release-manifest checksums; and then creates and verifies the
deterministic archive `dist/lexicon-en-oewn-0.5.0.tar.gz` with its top-level
`dist/lexicon-en-oewn-0.5.0.tar.gz.sha256`. The command fails rather than overwriting an existing
release.

Pushing a `v*` tag runs the same release script in GitHub Actions and publishes the verified bundle
as an immutable GitHub Release only when the tag equals `v0.5.0`, points exactly to `main`, and no
release already exists for it. See `docs/v0.5.0.md` for the workflow and release gates.

See [the Vocab consumer contract](docs/consumer-contract.md) for the runtime boundary.
