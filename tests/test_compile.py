import json
from pathlib import Path

from typer.testing import CliRunner

from lexicon.cli import app
from lexicon.export import export_legacy
from lexicon.model import Definition, Lexeme, Sense
from lexicon.validate import validate_artifact
from lexicon.version import DATASET_NAME, DATASET_VERSION, PIPELINE_VERSION


def test_cli_build_generates_equivalent_artifacts(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["build", "--input", "data/seed", "--output", str(tmp_path)])

    assert result.exit_code == 0, result.output
    jsonl_path = tmp_path / f"{DATASET_NAME}-{DATASET_VERSION}.jsonl"
    sqlite_path = tmp_path / f"{DATASET_NAME}-{DATASET_VERSION}.sqlite"
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert validate_artifact(jsonl_path) == {
        "lexemes": 3,
        "forms": 6,
        "senses": 4,
        "definitions": 4,
        "examples": 4,
    }
    assert validate_artifact(sqlite_path) == {
        "lexemes": 3,
        "forms": 6,
        "senses": 4,
        "definitions": 4,
        "examples": 4,
    }
    assert manifest["record_counts"] == {
        "definitions": 4,
        "examples": 4,
        "forms": 6,
        "lexemes": 3,
        "senses": 4,
    }
    assert manifest["dataset_version"] == DATASET_VERSION
    assert manifest["pipeline_version"] == PIPELINE_VERSION
    assert {item["name"] for item in manifest["artifacts"]} == {
        "duplicate_report",
        "jsonl",
        "sqlite",
    }
    assert json.loads((tmp_path / "duplicate-report.json").read_text()) == {
        "conflicting_duplicates": "build failure",
        "exact_duplicate_lexemes": [
            {"discarded_record_count": 1, "lexeme_id": "en:ambiguous:adjective"}
        ],
        "input_record_count": 4,
        "normalized_lexeme_count": 3,
    }


def test_legacy_export_is_only_a_projection(tmp_path: Path) -> None:
    runner = CliRunner()
    runner.invoke(app, ["build", "--input", "data/seed", "--output", str(tmp_path)])
    output = tmp_path / "compat.json"
    result = runner.invoke(
        app,
        [
            "export-legacy",
            "--input",
            str(tmp_path / f"{DATASET_NAME}-{DATASET_VERSION}.jsonl"),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(output.read_text()) == [
        {
            "definition": "Having more than one possible meaning.",
            "example": "The message was ambiguous.",
            "word": "ambiguous",
        },
        {
            "definition": "A written account or stored collection of information.",
            "example": "The archive keeps a record of each decision.",
            "word": "record",
        },
        {
            "definition": "To store information so that it can be used later.",
            "example": "Please record the result in the log.",
            "word": "record",
        },
    ]


def test_legacy_export_uses_an_empty_example_when_a_sense_has_none(tmp_path: Path) -> None:
    record = Lexeme(
        id="en:plain:adjective",
        language_id="en",
        lemma="plain",
        normalized_lemma="plain",
        part_of_speech="adjective",
        source_id="fixture",
        forms=(),
        senses=(
            Sense(
                id="en:plain:adjective:1",
                lexeme_id="en:plain:adjective",
                sense_key="1",
                source_sense_key="fixture:1",
                gloss=None,
                definitions=(
                    Definition(
                        id="en:plain:adjective:1:definition:1",
                        sense_id="en:plain:adjective:1",
                        text="Not decorated.",
                        definition_type="canonical",
                        audience="general",
                        source_id="fixture",
                    ),
                ),
                examples=(),
            ),
        ),
    )
    input_path = tmp_path / "input.jsonl"
    input_path.write_text(json.dumps(record.model_dump(mode="json")) + "\n")
    output_path = tmp_path / "legacy.json"

    assert export_legacy(input_path, output_path) == 1
    assert json.loads(output_path.read_text()) == [
        {"word": "plain", "definition": "Not decorated.", "example": ""}
    ]
