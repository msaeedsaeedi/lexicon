from __future__ import annotations

import json
from pathlib import Path

import typer

from .compile import write_jsonl, write_sqlite
from .export import export_legacy
from .manifest import write_attribution, write_manifest
from .normalize import normalize_dataset
from .staging import load_staging
from .validate import ArtifactValidationError, validate_artifact
from .version import DATASET_NAME, DATASET_VERSION, PIPELINE_VERSION, SCHEMA_VERSION

app = typer.Typer(no_args_is_help=True, help="Deterministic lexical dataset pipeline.")


@app.command()
def build(
    input_dir: Path = typer.Option(..., "--input", exists=True, file_okay=False),
    output_dir: Path = typer.Option(..., "--output", file_okay=False),
) -> None:
    """Compile curated staging data into canonical dataset artifacts."""
    sources, records = load_staging(input_dir)
    dataset = normalize_dataset(sources, records)
    stem = f"{DATASET_NAME}-{DATASET_VERSION}"
    jsonl_path = output_dir / f"{stem}.jsonl"
    sqlite_path = output_dir / f"{stem}.sqlite"
    write_jsonl(dataset, jsonl_path)
    write_sqlite(dataset, sqlite_path, {"dataset_name": DATASET_NAME, "dataset_version": DATASET_VERSION, "schema_version": SCHEMA_VERSION, "pipeline_version": PIPELINE_VERSION})
    write_manifest(dataset, {"jsonl": jsonl_path, "sqlite": sqlite_path}, output_dir / "manifest.json")
    write_attribution(dataset, output_dir / "ATTRIBUTION.md")
    typer.echo(f"Built {len(dataset.lexemes)} lexemes in {output_dir}")


@app.command()
def validate(path: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    """Validate a generated SQLite or JSONL artifact."""
    try:
        counts = validate_artifact(path)
    except ArtifactValidationError as error:
        raise typer.Exit(code=1) from error
    typer.echo(json.dumps(counts, sort_keys=True))


@app.command()
def inspect(path: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    """Show a compact summary of an artifact."""
    typer.echo(json.dumps(validate_artifact(path), sort_keys=True, indent=2))


@app.command("export-legacy")
def export_legacy_command(
    input_path: Path = typer.Option(..., "--input", exists=True, dir_okay=False),
    output_path: Path = typer.Option(..., "--output", dir_okay=False),
) -> None:
    """Generate the non-canonical word/definition/example compatibility projection."""
    count = export_legacy(input_path, output_path)
    typer.echo(f"Exported {count} compatibility entries to {output_path}")
