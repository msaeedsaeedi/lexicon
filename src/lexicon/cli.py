from __future__ import annotations

import json
from pathlib import Path

import typer

from .compile import write_jsonl, write_sqlite
from .export import export_legacy
from .manifest import write_attribution, write_manifest
from .normalize import normalize_dataset_with_report
from .overrides import apply_overrides, load_overrides
from .release import verify_release, write_release_manifest
from .reports import write_duplicate_report
from .staging import load_staging
from .validate import validate_artifact, validate_dataset
from .version import DATASET_NAME, DATASET_VERSION, PIPELINE_VERSION, SCHEMA_VERSION

app = typer.Typer(no_args_is_help=True, help="Deterministic lexical dataset pipeline.")


@app.command()
def build(
    input_dir: Path = typer.Option(..., "--input", exists=True, file_okay=False),
    output_dir: Path = typer.Option(..., "--output", file_okay=False),
    overrides_dir: Path | None = typer.Option(None, "--overrides", file_okay=False),
) -> None:
    """Compile curated staging data into canonical dataset artifacts."""
    try:
        sources, records = load_staging(input_dir)
        normalized = normalize_dataset_with_report(sources, records)
        dataset = apply_overrides(
            normalized.dataset, load_overrides(overrides_dir or input_dir.parent / "overrides")
        )
        validate_dataset(dataset)
        stem = f"{DATASET_NAME}-{DATASET_VERSION}"
        jsonl_path = output_dir / f"{stem}.jsonl"
        sqlite_path = output_dir / f"{stem}.sqlite"
        duplicate_report_path = output_dir / "duplicate-report.json"
        write_jsonl(dataset, jsonl_path)
        write_sqlite(
            dataset,
            sqlite_path,
            {
                "dataset_name": DATASET_NAME,
                "dataset_version": DATASET_VERSION,
                "schema_version": SCHEMA_VERSION,
                "pipeline_version": PIPELINE_VERSION,
            },
        )
        write_duplicate_report(normalized, duplicate_report_path)
        write_manifest(
            dataset,
            {"duplicate_report": duplicate_report_path, "jsonl": jsonl_path, "sqlite": sqlite_path},
            output_dir / "manifest.json",
        )
        write_attribution(dataset, output_dir / "ATTRIBUTION.md")
    except Exception as error:
        from .errors import PipelineError

        if isinstance(error, PipelineError):
            typer.echo(f"error [{error.code}]: {error}", err=True)
            raise typer.Exit(code=1) from error
        raise
    typer.echo(
        f"Built {len(dataset.lexemes)} lexemes in {output_dir}; {len(normalized.exact_duplicate_lexeme_ids)} exact duplicate inputs reported"
    )


@app.command()
def validate(path: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    """Validate a generated SQLite or JSONL artifact."""
    try:
        counts = validate_artifact(path)
    except Exception as error:
        from .errors import PipelineError

        if isinstance(error, PipelineError):
            typer.echo(f"error [{error.code}]: {error}", err=True)
            raise typer.Exit(code=1) from error
        raise
    typer.echo(json.dumps(counts, sort_keys=True))


@app.command()
def inspect(path: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    """Show a compact summary of an artifact."""
    try:
        typer.echo(json.dumps(validate_artifact(path), sort_keys=True, indent=2))
    except Exception as error:
        from .errors import PipelineError

        if isinstance(error, PipelineError):
            typer.echo(f"error [{error.code}]: {error}", err=True)
            raise typer.Exit(code=1) from error
        raise


@app.command("export-legacy")
def export_legacy_command(
    input_path: Path = typer.Option(..., "--input", exists=True, dir_okay=False),
    output_path: Path = typer.Option(..., "--output", dir_okay=False),
) -> None:
    """Generate the non-canonical word/definition/example compatibility projection."""
    count = export_legacy(input_path, output_path)
    typer.echo(f"Exported {count} compatibility entries to {output_path}")


@app.command("finalize-release")
def finalize_release(
    directory: Path = typer.Option(..., "--directory", exists=True, file_okay=False),
) -> None:
    """Write the checksummed release manifest after assembling a release bundle."""
    try:
        target = write_release_manifest(directory)
    except Exception as error:
        _exit_with_pipeline_error(error)
        raise
    typer.echo(f"Wrote release manifest to {target}")


@app.command("verify-release")
def verify_release_command(
    directory: Path = typer.Option(..., "--directory", exists=True, file_okay=False),
) -> None:
    """Verify a complete, finalized dataset release bundle."""
    try:
        counts = verify_release(directory)
    except Exception as error:
        _exit_with_pipeline_error(error)
        raise
    typer.echo(json.dumps(counts, sort_keys=True))


def _exit_with_pipeline_error(error: Exception) -> None:
    from .errors import PipelineError

    if isinstance(error, PipelineError):
        typer.echo(f"error [{error.code}]: {error}", err=True)
        raise typer.Exit(code=1) from error
    raise error
