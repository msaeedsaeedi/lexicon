import json
from pathlib import Path

from typer.testing import CliRunner

from lexicon.cli import app
from lexicon.version import DATASET_VERSION


def _write_overrides(
    directory: Path, blocked: list[dict[str, str]], fixes: list[dict[str, str]]
) -> None:
    directory.mkdir()
    (directory / "blocked-lexemes.json").write_text(json.dumps(blocked))
    (directory / "definition-fixes.json").write_text(json.dumps(fixes))


def test_overrides_block_lexemes_and_fix_definitions(tmp_path: Path) -> None:
    overrides = tmp_path / "overrides"
    _write_overrides(
        overrides,
        [{"lexeme_id": "en:record:noun", "reason": "fixture coverage"}],
        [
            {
                "definition_id": "en:ambiguous:adjective:1:definition:1",
                "text": "Having several possible meanings.",
            }
        ],
    )
    result = CliRunner().invoke(
        app,
        [
            "build",
            "--input",
            "data/seed",
            "--overrides",
            str(overrides),
            "--output",
            str(tmp_path / "artifacts"),
        ],
    )

    assert result.exit_code == 0, result.output
    records = [
        json.loads(line)
        for line in (tmp_path / "artifacts" / f"lexicon-en-core-{DATASET_VERSION}.jsonl")
        .read_text()
        .splitlines()
    ]
    assert [record["id"] for record in records] == ["en:ambiguous:adjective", "en:record:verb"]
    assert records[0]["senses"][0]["definitions"][0]["text"] == "Having several possible meanings."


def test_invalid_overrides_return_a_categorized_cli_diagnostic(tmp_path: Path) -> None:
    overrides = tmp_path / "overrides"
    _write_overrides(overrides, [{"lexeme_id": "en:missing:noun", "reason": "bad fixture"}], [])
    result = CliRunner().invoke(
        app,
        [
            "build",
            "--input",
            "data/seed",
            "--overrides",
            str(overrides),
            "--output",
            str(tmp_path / "artifacts"),
        ],
    )

    assert result.exit_code == 1
    assert "error [overrides.invalid_configuration]" in result.output
