import json
import tarfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lexicon.archive import (
    ArchiveError,
    create_release_archive,
    verify_release_archive,
    write_checksum_file,
)
from lexicon.cli import app
from lexicon.compile import sha256
from lexicon.release import ReleaseVerificationError
from lexicon.version import DATASET_NAME, DATASET_VERSION


def _build_bundle(tmp_path: Path) -> Path:
    runner = CliRunner()
    bundle = tmp_path / f"{DATASET_NAME}-{DATASET_VERSION}"
    assert (
        runner.invoke(app, ["build", "--input", "data/seed", "--output", str(bundle)]).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            [
                "export-legacy",
                "--input",
                str(bundle / f"{DATASET_NAME}-{DATASET_VERSION}.jsonl"),
                "--output",
                str(bundle / f"vocab-compat-{DATASET_VERSION}.json"),
            ],
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["finalize-release", "--directory", str(bundle)]).exit_code == 0
    return bundle


def test_create_archive_is_deterministic(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    create_release_archive(bundle, first)
    create_release_archive(bundle, second)

    assert sha256(first) == sha256(second)
    with tarfile.open(first, "r:gz") as archive:
        members = [member.name for member in archive.getmembers()]
    assert members[0] == f"{DATASET_NAME}-{DATASET_VERSION}"
    assert f"{DATASET_NAME}-{DATASET_VERSION}/release-manifest.json" in members


def test_verify_archive_round_trip_validates_bundle(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    archive = tmp_path / f"{DATASET_NAME}-{DATASET_VERSION}.tar.gz"
    checksum = tmp_path / f"{DATASET_NAME}-{DATASET_VERSION}.tar.gz.sha256"
    create_release_archive(bundle, archive)
    write_checksum_file(archive, checksum)
    extract = tmp_path / "extract"

    counts = verify_release_archive(archive, checksum, extract)
    assert counts == {
        "lexemes": 3,
        "forms": 6,
        "senses": 4,
        "definitions": 4,
        "examples": 4,
    }
    extracted_bundle = extract / f"{DATASET_NAME}-{DATASET_VERSION}"
    assert extracted_bundle.is_dir()
    assert json.loads((extracted_bundle / "release-manifest.json").read_text())["dataset"] == (
        DATASET_NAME
    )


def test_verify_archive_rejects_checksum_mismatch(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    archive = tmp_path / "bundle.tar.gz"
    checksum = tmp_path / "bundle.tar.gz.sha256"
    create_release_archive(bundle, archive)
    write_checksum_file(archive, checksum)
    (tmp_path / "stray.txt").write_text("x")
    changed = tmp_path / "bundle.tar.gz"
    changed.write_bytes(archive.read_bytes() + b"\x00")

    with pytest.raises(ArchiveError, match="checksum mismatch"):
        verify_release_archive(changed, checksum, tmp_path / "extract")


def test_verify_archive_rejects_modified_bundle_file(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    archive = tmp_path / "bundle.tar.gz"
    checksum = tmp_path / "bundle.tar.gz.sha256"
    create_release_archive(bundle, archive)
    write_checksum_file(archive, checksum)
    extract = tmp_path / "extract"
    verify_release_archive(archive, checksum, extract)

    modified = extract / f"{DATASET_NAME}-{DATASET_VERSION}" / "ATTRIBUTION.md"
    modified.write_text("changed\n")
    tampered_archive = tmp_path / "tampered.tar.gz"
    tampered_checksum = tmp_path / "tampered.tar.gz.sha256"
    create_release_archive(extract / f"{DATASET_NAME}-{DATASET_VERSION}", tampered_archive)
    write_checksum_file(tampered_archive, tampered_checksum)

    with pytest.raises(ReleaseVerificationError, match="checksum mismatch"):
        verify_release_archive(tampered_archive, tampered_checksum, tmp_path / "extract2")


def test_cli_create_archive_and_verify(tmp_path: Path) -> None:
    runner = CliRunner()
    bundle = _build_bundle(tmp_path)
    archive = tmp_path / f"{DATASET_NAME}-{DATASET_VERSION}.tar.gz"
    checksum = tmp_path / f"{DATASET_NAME}-{DATASET_VERSION}.tar.gz.sha256"

    result = runner.invoke(
        app,
        [
            "create-archive",
            "--directory",
            str(bundle),
            "--output",
            str(archive),
            "--checksum",
            str(checksum),
        ],
    )
    assert result.exit_code == 0, result.output
    assert archive.is_file()
    assert checksum.is_file()
    verify = runner.invoke(
        app,
        [
            "verify-archive",
            "--archive",
            str(archive),
            "--checksum",
            str(checksum),
            "--extract",
            str(tmp_path / "extract"),
        ],
    )
    assert verify.exit_code == 0, verify.output
    assert json.loads(verify.output)["lexemes"] == 3
