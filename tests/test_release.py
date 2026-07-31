import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lexicon.cli import app
from lexicon.release import ReleaseVerificationError, verify_release
from lexicon.version import DATASET_VERSION


def test_finalized_release_verifies_all_bundle_files(tmp_path: Path) -> None:
    runner = CliRunner()
    assert (
        runner.invoke(app, ["build", "--input", "data/seed", "--output", str(tmp_path)]).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            [
                "export-legacy",
                "--input",
                str(tmp_path / f"lexicon-en-core-{DATASET_VERSION}.jsonl"),
                "--output",
                str(tmp_path / f"vocab-compat-{DATASET_VERSION}.json"),
            ],
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["finalize-release", "--directory", str(tmp_path)]).exit_code == 0
    result = runner.invoke(app, ["verify-release", "--directory", str(tmp_path)])

    assert result.exit_code == 0, result.output
    release_manifest = json.loads((tmp_path / "release-manifest.json").read_text())
    assert {item["filename"] for item in release_manifest["files"]} == {
        "ATTRIBUTION.md",
        "duplicate-report.json",
        f"lexicon-en-core-{DATASET_VERSION}.jsonl",
        f"lexicon-en-core-{DATASET_VERSION}.sqlite",
        "manifest.json",
        f"vocab-compat-{DATASET_VERSION}.json",
    }


def test_release_verification_rejects_changed_bundle_file(tmp_path: Path) -> None:
    runner = CliRunner()
    runner.invoke(app, ["build", "--input", "data/seed", "--output", str(tmp_path)])
    runner.invoke(
        app,
        [
            "export-legacy",
            "--input",
            str(tmp_path / f"lexicon-en-core-{DATASET_VERSION}.jsonl"),
            "--output",
            str(tmp_path / f"vocab-compat-{DATASET_VERSION}.json"),
        ],
    )
    runner.invoke(app, ["finalize-release", "--directory", str(tmp_path)])
    (tmp_path / "ATTRIBUTION.md").write_text("changed\n")

    with pytest.raises(ReleaseVerificationError, match="release file checksum mismatch"):
        verify_release(tmp_path)
