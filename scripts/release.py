from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from lexicon.version import DATASET_NAME, DATASET_VERSION

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build and verify a releasable lexicon dataset bundle."
    )
    parser.add_argument(
        "--output", type=Path, default=Path("dist") / f"{DATASET_NAME}-{DATASET_VERSION}"
    )
    arguments = parser.parse_args()
    output = arguments.output if arguments.output.is_absolute() else ROOT / arguments.output
    output = output.resolve()
    if output.exists():
        parser.error(f"release output already exists: {output}")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    staging = Path(tempfile.mkdtemp(prefix=".oewn-staging.", dir=output.parent))
    try:
        _run("uv", "run", "ruff", "format", "--check", ".")
        _run("uv", "run", "ruff", "check", ".")
        _run("uv", "run", "pyright")
        _run("uv", "run", "pytest")
        _run("uv", "run", "lexicon", "acquire-oewn", "--cache", ".cache/raw")
        _run("uv", "run", "lexicon", "acquire-ngsl", "--cache", ".cache/raw")
        archive = ROOT / ".cache/raw/english-wordnet-2025.zip"
        _run(
            "uv", "run", "lexicon", "import-oewn", "--input", str(archive), "--output", str(staging)
        )
        _run(
            "uv",
            "run",
            "lexicon",
            "build",
            "--input",
            str(staging),
            "--import-report",
            str(staging / "import-report.json"),
            "--baseline",
            str(ROOT / "data/quality/oewn-2025.baseline.json"),
            "--output",
            str(temporary),
        )
        _run(
            "uv",
            "run",
            "lexicon",
            "export-legacy",
            "--input",
            str(temporary / f"{DATASET_NAME}-{DATASET_VERSION}.jsonl"),
            "--output",
            str(temporary / f"vocab-compat-{DATASET_VERSION}.json"),
        )
        _run("uv", "run", "lexicon", "finalize-release", "--directory", str(temporary))
        _run(
            "uv",
            "run",
            "lexicon",
            "verify-release",
            "--directory",
            str(temporary),
            "--baseline",
            str(ROOT / "data/quality/oewn-2025.baseline.json"),
        )
        temporary.replace(output)
        archive = output.parent / f"{output.name}.tar.gz"
        checksum = output.parent / f"{output.name}.tar.gz.sha256"
        _run(
            "uv",
            "run",
            "lexicon",
            "create-archive",
            "--directory",
            str(output),
            "--output",
            str(archive),
            "--checksum",
            str(checksum),
        )
        extract = Path(tempfile.mkdtemp(prefix=".archive-check.", dir=output.parent))
        try:
            _run(
                "uv",
                "run",
                "lexicon",
                "verify-archive",
                "--archive",
                str(archive),
                "--checksum",
                str(checksum),
                "--extract",
                str(extract),
            )
        finally:
            shutil.rmtree(extract, ignore_errors=True)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        shutil.rmtree(output, ignore_errors=True)
        archive = output.parent / f"{output.name}.tar.gz"
        archive.unlink(missing_ok=True)
        archive.with_name(archive.name + ".sha256").unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    print(f"Release bundle verified: {output}")
    print(f"Release archive verified: {output.name}.tar.gz")
    return 0


def _run(*command: str) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


if __name__ == "__main__":
    sys.exit(main())
