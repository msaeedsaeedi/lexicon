import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lexicon.cli import app
from lexicon.health import QualityRegressionError
from lexicon.release import ReleaseVerificationError, verify_release
from lexicon.version import DATASET_NAME, DATASET_VERSION


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
                str(tmp_path / f"{DATASET_NAME}-{DATASET_VERSION}.jsonl"),
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
        "health-report.json",
        f"{DATASET_NAME}-{DATASET_VERSION}.jsonl",
        f"{DATASET_NAME}-{DATASET_VERSION}.sqlite",
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
            str(tmp_path / f"{DATASET_NAME}-{DATASET_VERSION}.jsonl"),
            "--output",
            str(tmp_path / f"vocab-compat-{DATASET_VERSION}.json"),
        ],
    )
    runner.invoke(app, ["finalize-release", "--directory", str(tmp_path)])
    (tmp_path / "ATTRIBUTION.md").write_text("changed\n")

    with pytest.raises(ReleaseVerificationError, match="release file checksum mismatch"):
        verify_release(tmp_path)


def test_release_verification_checks_health_against_baseline(tmp_path: Path) -> None:
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
                str(tmp_path / f"{DATASET_NAME}-{DATASET_VERSION}.jsonl"),
                "--output",
                str(tmp_path / f"vocab-compat-{DATASET_VERSION}.json"),
            ],
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["finalize-release", "--directory", str(tmp_path)]).exit_code == 0
    baseline = tmp_path.parent / "baseline.json"
    baseline.write_text((tmp_path / "health-report.json").read_text())

    assert verify_release(tmp_path, baseline_path=baseline) is not None

    payload = json.loads(baseline.read_text())
    payload["record_counts"]["definitions"] = 5
    baseline.write_text(json.dumps(payload))
    with pytest.raises(QualityRegressionError, match="record_counts.definitions"):
        verify_release(tmp_path, baseline_path=baseline)
