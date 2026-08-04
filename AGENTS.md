# Repository Guidelines

## Project Structure & Module Organization

`src/lexicon/` contains the deterministic dataset pipeline and Typer CLI. Keep source-specific
logic in its own module (for example, `oewn.py`); keep canonical models, normalization,
validation, compilation, and release concerns separated. Tests live in `tests/` and mirror
pipeline areas as `test_<area>.py`. Checked-in inputs belong in `data/`: the small seed is a test
fixture, OEWN metadata is in `data/sources/`, and corrections are in `data/overrides/`.

`schemas/` defines consumer-facing JSON schemas and `docs/` holds release and contract documents.
Generated caches, staging directories, `artifacts/` contents, and `dist/` bundles are local
outputs; do not commit them.

## Build, Test, and Development Commands

Use Python 3.14 and uv:

```bash
uv sync                                      # install locked dependencies
uv run pytest                                # run all tests
uv run ruff format --check . && uv run ruff check .
uv run pyright                               # standard type checking
uv run lexicon build --input data/seed --output artifacts
uv run python scripts/release.py             # create and verify a full release bundle
```

For the OEWN flow, run `lexicon acquire-oewn --cache .cache/raw`, then `import-oewn` into a
staging directory before building. The source lock file supplies the required URL and SHA-256.

## Coding Style & Naming Conventions

Use four-space indentation, type annotations, and Python 3.14 syntax. Ruff enforces a
100-character line target, imports, and common correctness rules; run its formatter instead of
hand-formatting. Use `snake_case` for functions, variables, modules, and JSON fields;
`PascalCase` for Pydantic models and exceptions. Preserve deterministic ordering and stable error
categories (for example, `oewn.invalid_input`) because artifacts and CLI errors are contractual.

## Testing Guidelines

Write pytest tests named `test_<behavior>`. Prefer small temporary source archives and staging
fixtures over real OEWN downloads. Cover normal behavior, invalid input, deterministic output,
and any schema or manifest change. Run the complete test, lint, formatting, and type-check suite
before proposing a release.

## Commit & Pull Request Guidelines

The existing history uses release commits such as `release(v0.2.0): release completed`; use a
concise imperative subject for other work and keep commits focused. Pull requests should explain
the data/pipeline effect, list validation commands run, and call out schema, dataset-version, or
source-lock changes. Do not attach generated release artifacts unless explicitly requested.
