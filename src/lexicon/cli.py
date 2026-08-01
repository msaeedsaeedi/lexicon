from __future__ import annotations

import json
from pathlib import Path

import typer

from .archive import create_release_archive, verify_release_archive, write_checksum_file
from .compile import write_jsonl, write_sqlite
from .export import export_legacy
from .health import check_baseline, dataset_health, write_health_report
from .manifest import write_attribution, write_manifest
from .normalize import normalize_dataset_with_report
from .oewn import acquire as acquire_oewn_archive
from .oewn import import_archive, load_lock, write_staging
from .overrides import apply_overrides, load_overrides
from .publish import (
    ensure_no_existing_release,
    publish_release,
    resolve_main_commit,
    resolve_tag_commit,
    validate_release_tag,
    validate_tag_at_main,
)
from .release import verify_release, write_release_manifest
from .reports import write_duplicate_report
from .staging import load_staging
from .validate import validate_artifact, validate_build_directory, validate_dataset
from .version import DATASET_NAME, DATASET_VERSION, PIPELINE_VERSION, SCHEMA_VERSION

app = typer.Typer(no_args_is_help=True, help="Deterministic lexical dataset pipeline.")


@app.command()
def build(
    input_dir: Path = typer.Option(..., "--input", exists=True, file_okay=False),
    output_dir: Path = typer.Option(..., "--output", file_okay=False),
    overrides_dir: Path | None = typer.Option(None, "--overrides", file_okay=False),
    import_report_path: Path | None = typer.Option(None, "--import-report", exists=True),
    baseline_path: Path | None = typer.Option(None, "--baseline", exists=True, dir_okay=False),
) -> None:
    """Compile curated staging data into canonical dataset artifacts."""
    try:
        sources, records = load_staging(input_dir)
        normalized = normalize_dataset_with_report(sources, records)
        dataset = apply_overrides(
            normalized.dataset, load_overrides(overrides_dir or input_dir.parent / "overrides")
        )
        validate_dataset(dataset)
        health_report_path = output_dir / "health-report.json"
        health_report = dataset_health(dataset, normalized)
        write_health_report(health_report, health_report_path)
        if baseline_path is not None:
            check_baseline(health_report, baseline_path)
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
        artifacts = {
            "duplicate_report": duplicate_report_path,
            "health_report": health_report_path,
            "jsonl": jsonl_path,
            "sqlite": sqlite_path,
        }
        import_report: dict[str, object] | None = None
        if import_report_path is not None:
            import_report = json.loads(import_report_path.read_text(encoding="utf-8"))
            published_report_path = output_dir / "import-report.json"
            from .compile import write_text_atomic

            write_text_atomic(
                published_report_path,
                json.dumps(import_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            )
            artifacts["import_report"] = published_report_path
        write_manifest(
            dataset,
            artifacts,
            output_dir / "manifest.json",
            import_report,
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


@app.command("acquire-oewn")
def acquire_oewn(
    cache_dir: Path = typer.Option(Path(".cache/raw"), "--cache", file_okay=False),
    lock_path: Path = typer.Option(Path("data/sources/oewn-2025.lock.json"), "--lock", exists=True),
) -> None:
    """Download the checksum-locked OEWN 2025 source archive into the local cache."""
    try:
        archive = acquire_oewn_archive(load_lock(lock_path), cache_dir)
    except Exception as error:
        _exit_with_pipeline_error(error)
        raise
    typer.echo(archive)


@app.command("import-oewn")
def import_oewn(
    input_path: Path = typer.Option(..., "--input", exists=True, dir_okay=False),
    output_dir: Path = typer.Option(..., "--output", file_okay=False),
    lock_path: Path = typer.Option(Path("data/sources/oewn-2025.lock.json"), "--lock", exists=True),
) -> None:
    """Convert a checksum-locked OEWN archive into generic Lexicon staging records."""
    try:
        result = import_archive(input_path, load_lock(lock_path))
        write_staging(result, output_dir)
    except Exception as error:
        _exit_with_pipeline_error(error)
        raise
    typer.echo(
        f"Imported {result.synset_count} synsets into {len(result.records)} lexemes in {output_dir}"
    )


@app.command()
def validate(path: Path = typer.Argument(..., exists=True)) -> None:
    """Validate one artifact or confirm JSONL/SQLite agreement in a build directory."""
    try:
        counts = validate_build_directory(path) if path.is_dir() else validate_artifact(path)
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
    baseline_path: Path | None = typer.Option(None, "--baseline", exists=True, dir_okay=False),
) -> None:
    """Verify a complete, finalized dataset release bundle."""
    try:
        counts = verify_release(directory, baseline_path=baseline_path)
    except Exception as error:
        _exit_with_pipeline_error(error)
        raise
    typer.echo(json.dumps(counts, sort_keys=True))


@app.command("create-archive")
def create_archive_command(
    directory: Path = typer.Option(..., "--directory", exists=True, file_okay=False),
    archive_path: Path = typer.Option(..., "--output", dir_okay=False),
    checksum_path: Path = typer.Option(None, "--checksum", dir_okay=False),
) -> None:
    """Create a deterministic release archive and its top-level SHA-256 checksum."""
    try:
        create_release_archive(directory, archive_path)
        checksum = checksum_path or archive_path.with_name(archive_path.name + ".sha256")
        write_checksum_file(archive_path, checksum)
    except Exception as error:
        _exit_with_pipeline_error(error)
        raise
    typer.echo(f"Created release archive {archive_path}")


@app.command("verify-archive")
def verify_archive_command(
    archive_path: Path = typer.Option(..., "--archive", exists=True, dir_okay=False),
    checksum_path: Path = typer.Option(None, "--checksum", exists=True, dir_okay=False),
    extract_dir: Path = typer.Option(Path(".cache/archive-check"), "--extract", file_okay=False),
) -> None:
    """Verify a release archive checksum and validate its extracted bundle."""
    try:
        checksum = checksum_path or archive_path.with_name(archive_path.name + ".sha256")
        counts = verify_release_archive(archive_path, checksum, extract_dir)
    except Exception as error:
        _exit_with_pipeline_error(error)
        raise
    typer.echo(json.dumps(counts, sort_keys=True))


@app.command("publish-gate")
def publish_gate_command(
    tag: str = typer.Option(..., "--tag"),
    owner_repo: str = typer.Option(..., "--owner-repo"),
    main_sha: str | None = typer.Option(None, "--main-sha"),
    repo_dir: Path | None = typer.Option(None, "--repo-dir", exists=True, file_okay=False),
) -> None:
    """Require the tag to match the dataset version and point exactly at main."""
    try:
        validate_release_tag(tag)
        main_commit = main_sha if main_sha is not None else resolve_main_commit(repo_dir)
        validate_tag_at_main(resolve_tag_commit(tag, repo_dir), main_commit)
        ensure_no_existing_release(owner_repo, tag)
    except Exception as error:
        _exit_with_pipeline_error(error)
        raise
    typer.echo(f"Release gate passed for {tag}")


@app.command("publish-release")
def publish_release_command(
    tag: str = typer.Option(..., "--tag"),
    owner_repo: str = typer.Option(..., "--owner-repo"),
    archive: Path = typer.Option(..., "--archive", exists=True, dir_okay=False),
    checksum: Path = typer.Option(..., "--checksum", exists=True, dir_okay=False),
) -> None:
    """Create an immutable GitHub Release with the archive and checksum assets."""
    try:
        publish_release(owner_repo, tag, archive, checksum)
    except Exception as error:
        _exit_with_pipeline_error(error)
        raise
    typer.echo(f"Published GitHub Release for {tag}")


def _exit_with_pipeline_error(error: Exception) -> None:
    from .errors import PipelineError

    if isinstance(error, PipelineError):
        typer.echo(f"error [{error.code}]: {error}", err=True)
        raise typer.Exit(code=1) from error
    raise error
