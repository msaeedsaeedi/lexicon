import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from lexicon.cli import app
from lexicon.publish import (
    ReleaseGateError,
    ensure_no_existing_release,
    resolve_main_commit,
    resolve_tag_commit,
    validate_release_tag,
    validate_tag_at_main,
)
from lexicon.version import DATASET_VERSION


def test_validate_release_tag_accepts_matching_version() -> None:
    assert validate_release_tag(f"v{DATASET_VERSION}") is None


def test_validate_release_tag_rejects_other_version() -> None:
    with pytest.raises(ReleaseGateError, match="does not match expected"):
        validate_release_tag("v9.9.9")


def test_validate_tag_at_main_requires_exact_commit() -> None:
    validate_tag_at_main("abc123", "abc123")
    with pytest.raises(ReleaseGateError, match="does not point to the current main"):
        validate_tag_at_main("abc123", "def456")


def test_resolve_tag_commit_uses_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(command, capture_output, text):
        return SimpleNamespace(returncode=0, stdout="deadbeef\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert resolve_tag_commit(f"v{DATASET_VERSION}", tmp_path) == "deadbeef"


def test_resolve_main_commit_uses_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(command, capture_output, text):
        return SimpleNamespace(returncode=0, stdout="cafebabe\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert resolve_main_commit(tmp_path) == "cafebabe"


def test_ensure_no_existing_release_fails_when_release_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0))
    with pytest.raises(ReleaseGateError, match="already exists"):
        ensure_no_existing_release("owner/repo", f"v{DATASET_VERSION}")


def test_ensure_no_existing_release_passes_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1))
    assert ensure_no_existing_release("owner/repo", f"v{DATASET_VERSION}") is None


def test_publish_gate_cli_rejects_non_matching_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command, capture_output, text):
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "publish-gate",
            "--tag",
            "v9.9.9",
            "--owner-repo",
            "owner/repo",
            "--main-sha",
            "abc123",
        ],
    )
    assert result.exit_code == 1
    assert "release.gate_failed" in result.output
    assert "does not match expected" in result.output


def test_publish_gate_cli_passes_for_valid_state(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command: list[str], capture_output: bool, text: bool) -> Any:
        resolved = {
            f"v{DATASET_VERSION}^" + "{commit}": "abc123",
            "refs/remotes/origin/main": "abc123",
        }
        expression = " ".join(command[1:])
        if expression.startswith("rev-parse"):
            ref = expression.removeprefix("rev-parse ").strip()
            return SimpleNamespace(
                returncode=0, stdout=resolved.get(ref, "abc123") + "\n", stderr=""
            )
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "publish-gate",
            "--tag",
            f"v{DATASET_VERSION}",
            "--owner-repo",
            "owner/repo",
        ],
    )
    assert result.exit_code == 0, result.output
    assert f"Release gate passed for v{DATASET_VERSION}" in result.output
