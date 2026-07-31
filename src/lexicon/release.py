from __future__ import annotations

import json
from pathlib import Path

from .compile import sha256, write_text_atomic
from .errors import PipelineError
from .validate import validate_artifact
from .version import DATASET_NAME, DATASET_VERSION, PIPELINE_VERSION, SCHEMA_VERSION


class ReleaseVerificationError(PipelineError):
    code = "release.invalid_bundle"


def write_release_manifest(directory: Path) -> Path:
    verify_release(directory, require_release_manifest=False)
    target = directory / "release-manifest.json"
    files = sorted(path for path in directory.iterdir() if path.is_file() and path != target)
    payload = {
        "dataset": DATASET_NAME,
        "dataset_version": DATASET_VERSION,
        "schema_version": SCHEMA_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "files": [{"filename": path.name, "sha256": sha256(path)} for path in files],
    }
    write_text_atomic(
        target, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return target


def verify_release(directory: Path, *, require_release_manifest: bool = True) -> dict[str, int]:
    manifest = _read_json(directory / "manifest.json", "dataset manifest")
    _require_versions(manifest, "dataset manifest")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise ReleaseVerificationError("dataset manifest must contain an artifacts list")
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ReleaseVerificationError("dataset manifest contains an invalid artifact entry")
        filename = artifact.get("filename")
        checksum = artifact.get("sha256")
        if not isinstance(filename, str) or not isinstance(checksum, str):
            raise ReleaseVerificationError(
                "dataset manifest artifact entries require filename and sha256"
            )
        path = directory / filename
        if not path.is_file() or sha256(path) != checksum:
            raise ReleaseVerificationError(f"dataset artifact checksum mismatch: {filename}")

    stem = f"{DATASET_NAME}-{DATASET_VERSION}"
    jsonl_counts = validate_artifact(directory / f"{stem}.jsonl")
    sqlite_counts = validate_artifact(directory / f"{stem}.sqlite")
    if jsonl_counts != sqlite_counts:
        raise ReleaseVerificationError("SQLite and JSONL artifact record counts differ")
    if manifest.get("record_counts") != sqlite_counts:
        raise ReleaseVerificationError("dataset manifest record counts do not match artifacts")

    attribution = directory / "ATTRIBUTION.md"
    if not attribution.is_file() or not attribution.read_text(encoding="utf-8").strip():
        raise ReleaseVerificationError("release bundle is missing attribution")
    _validate_legacy_export(directory / f"vocab-compat-{DATASET_VERSION}.json")

    release_manifest = directory / "release-manifest.json"
    if require_release_manifest:
        release_payload = _read_json(release_manifest, "release manifest")
        _require_versions(release_payload, "release manifest")
        _verify_release_files(directory, release_payload)
    return sqlite_counts


def _read_json(path: Path, label: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseVerificationError(f"cannot read {label}: {path}") from error
    if not isinstance(payload, dict):
        raise ReleaseVerificationError(f"{label} must be a JSON object")
    return payload


def _require_versions(payload: dict[str, object], label: str) -> None:
    expected = {
        "dataset": DATASET_NAME,
        "dataset_version": DATASET_VERSION,
        "schema_version": SCHEMA_VERSION,
        "pipeline_version": PIPELINE_VERSION,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise ReleaseVerificationError(f"{label} has incompatible {key}")


def _validate_legacy_export(path: Path) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseVerificationError(
            f"cannot read legacy compatibility export: {path}"
        ) from error
    if not isinstance(payload, list):
        raise ReleaseVerificationError("legacy compatibility export must be a JSON array")
    for entry in payload:
        if not isinstance(entry, dict) or set(entry) != {"word", "definition", "example"}:
            raise ReleaseVerificationError("legacy compatibility export contains an invalid entry")


def _verify_release_files(directory: Path, payload: dict[str, object]) -> None:
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        raise ReleaseVerificationError("release manifest must contain file checksums")
    expected_names = {
        path.name
        for path in directory.iterdir()
        if path.is_file() and path.name != "release-manifest.json"
    }
    actual_names: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            raise ReleaseVerificationError("release manifest contains an invalid file entry")
        filename = item.get("filename")
        checksum = item.get("sha256")
        if not isinstance(filename, str) or not isinstance(checksum, str):
            raise ReleaseVerificationError(
                "release manifest file entries require filename and sha256"
            )
        actual_names.add(filename)
        path = directory / filename
        if not path.is_file() or sha256(path) != checksum:
            raise ReleaseVerificationError(f"release file checksum mismatch: {filename}")
    if actual_names != expected_names:
        raise ReleaseVerificationError("release manifest file list does not match bundle contents")
