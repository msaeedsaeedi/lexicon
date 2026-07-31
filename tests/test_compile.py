import json
from pathlib import Path

from typer.testing import CliRunner

from lexicon.cli import app
from lexicon.validate import validate_artifact


def test_cli_build_generates_equivalent_artifacts(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["build", "--input", "data/seed", "--output", str(tmp_path)])

    assert result.exit_code == 0, result.output
    jsonl_path = tmp_path / "lexicon-en-core-0.1.0.jsonl"
    sqlite_path = tmp_path / "lexicon-en-core-0.1.0.sqlite"
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert validate_artifact(jsonl_path) == {"lexemes": 3, "forms": 6, "senses": 4}
    assert validate_artifact(sqlite_path) == {
        "lexemes": 3,
        "forms": 6,
        "senses": 4,
        "definitions": 4,
        "examples": 4,
    }
    assert manifest["record_counts"] == {"definitions": 4, "examples": 4, "forms": 6, "lexemes": 3, "senses": 4}
    assert manifest["pipeline_version"] == "0.1.1"
    assert {item["name"] for item in manifest["artifacts"]} == {"duplicate_report", "jsonl", "sqlite"}
    assert json.loads((tmp_path / "duplicate-report.json").read_text()) == {
        "conflicting_duplicates": "build failure",
        "exact_duplicate_lexemes": [{"discarded_record_count": 1, "lexeme_id": "en:ambiguous:adjective"}],
        "input_record_count": 4,
        "normalized_lexeme_count": 3,
    }


def test_legacy_export_is_only_a_projection(tmp_path: Path) -> None:
    runner = CliRunner()
    runner.invoke(app, ["build", "--input", "data/seed", "--output", str(tmp_path)])
    output = tmp_path / "compat.json"
    result = runner.invoke(app, ["export-legacy", "--input", str(tmp_path / "lexicon-en-core-0.1.0.jsonl"), "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert json.loads(output.read_text()) == [
        {"definition": "Having more than one possible meaning.", "example": "The message was ambiguous.", "word": "ambiguous"},
        {"definition": "A written account or stored collection of information.", "example": "The archive keeps a record of each decision.", "word": "record"},
        {"definition": "To store information so that it can be used later.", "example": "Please record the result in the log.", "word": "record"},
    ]
