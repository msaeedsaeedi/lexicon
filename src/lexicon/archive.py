from __future__ import annotations

import gzip
import io
import tarfile
from pathlib import Path

from .compile import sha256, write_bytes_atomic, write_text_atomic
from .errors import PipelineError
from .release import verify_release

ARCHIVE_MTIME = 0


class ArchiveError(PipelineError):
    code = "release.invalid_archive"


def create_release_archive(bundle_dir: Path, archive_path: Path) -> Path:
    """Write a deterministic gzip-compressed tar archive of a release bundle."""
    filenames = sorted(path.name for path in bundle_dir.iterdir() if path.is_file())
    if not filenames:
        raise ArchiveError(f"cannot archive empty release bundle: {bundle_dir}")
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _tar_bytes(bundle_dir.name, bundle_dir, filenames)
    write_bytes_atomic(archive_path, gzip.compress(payload, mtime=ARCHIVE_MTIME))
    return archive_path


def write_checksum_file(archive_path: Path, checksum_path: Path) -> str:
    """Write a top-level SHA-256 checksum file for an archive."""
    digest = sha256(archive_path)
    write_text_atomic(checksum_path, f"{digest}  {archive_path.name}\n")
    return digest


def verify_release_archive(
    archive_path: Path, checksum_path: Path, extract_dir: Path
) -> dict[str, int]:
    """Verify an archive checksum, extract it, and validate the bundled release."""
    if not archive_path.is_file():
        raise ArchiveError(f"archive does not exist: {archive_path}")
    expected = _read_checksum(checksum_path)
    if sha256(archive_path) != expected:
        raise ArchiveError(f"archive checksum mismatch: {archive_path}")
    extract_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:gz") as archive:
        archive.extractall(extract_dir, filter="data")
    bundle_dir = _single_bundle_dir(extract_dir)
    return verify_release(bundle_dir)


def _tar_bytes(top_level: str, bundle_dir: Path, filenames: list[str]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.GNU_FORMAT) as archive:
        directory = tarfile.TarInfo(top_level)
        directory.type = tarfile.DIRTYPE
        directory.mode = 0o755
        directory.mtime = ARCHIVE_MTIME
        archive.addfile(directory)
        for filename in filenames:
            source = bundle_dir / filename
            info = archive.gettarinfo(str(source), arcname=f"{top_level}/{filename}")
            info.mode = 0o644
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = ARCHIVE_MTIME
            with source.open("rb") as handle:
                archive.addfile(info, handle)
    return buffer.getvalue()


def _read_checksum(checksum_path: Path) -> str:
    try:
        value = checksum_path.read_text(encoding="utf-8").strip().split()[0]
    except (OSError, IndexError) as error:
        raise ArchiveError(f"cannot read archive checksum file: {checksum_path}") from error
    if len(value) != 64:
        raise ArchiveError(f"invalid archive checksum file: {checksum_path}")
    return value


def _single_bundle_dir(extract_dir: Path) -> Path:
    entries = [path for path in extract_dir.iterdir() if path.is_dir()]
    if len(entries) != 1:
        raise ArchiveError(
            f"archive must extract to exactly one top-level bundle directory, found {len(entries)}"
        )
    return entries[0]
