from pathlib import Path

from typer.testing import CliRunner

from lexicon.cli import app
from lexicon.compile import sha256


def test_repeated_builds_have_identical_artifact_checksums(tmp_path: Path) -> None:
    runner = CliRunner()
    first = tmp_path / "first"
    second = tmp_path / "second"
    assert runner.invoke(app, ["build", "--input", "data/seed", "--output", str(first)]).exit_code == 0
    assert runner.invoke(app, ["build", "--input", "data/seed", "--output", str(second)]).exit_code == 0

    for filename in ("lexicon-en-core-0.1.0.jsonl", "lexicon-en-core-0.1.0.sqlite", "manifest.json"):
        assert sha256(first / filename) == sha256(second / filename)
