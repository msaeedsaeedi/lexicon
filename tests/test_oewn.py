import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from lexicon.oewn import OEWNError, OEWNLock, acquire, import_archive, write_staging
from lexicon.staging import load_staging


def _fixture_archive(tmp_path: Path) -> tuple[Path, OEWNLock]:
    archive = tmp_path / "english-wordnet-2025.zip"
    data = {
        "oewn2025/data.noun": '00001740 03 n 02 ice_cream 0 gelato 0 000 | a frozen dessert; "we ate ice cream"\n',
        "oewn2025/data.verb": "00001740 03 v 01 run 0 000 | move quickly on foot\n",
        "oewn2025/data.adj": "00001740 03 s 01 unable 0 000 | lacking the ability to do something\n",
        "oewn2025/data.adv": "00001740 03 r 01 quickly 0 000 | with rapid movements\n",
    }
    with zipfile.ZipFile(archive, "w") as package:
        for name, content in data.items():
            package.writestr(name, content)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    return archive, OEWNLock(
        id="oewn-2025",
        name="Open English WordNet",
        version="2025",
        distribution_url="https://example.invalid/oewn.zip",
        filename=archive.name,
        sha256=checksum,
        license="CC-BY-4.0",
        attribution_url="https://example.invalid",
        released_at="2025-12-31",
        scope="common",
    )


def test_importer_maps_wordnet_records_to_generic_staging(tmp_path: Path) -> None:
    archive, lock = _fixture_archive(tmp_path)
    result = import_archive(archive, lock)

    assert result.synset_count == 4
    assert result.example_count == 1
    ice_cream = next(record for record in result.records if record.lemma == "ice cream")
    assert ice_cream.part_of_speech == "noun"
    assert ice_cream.senses[0].source_sense_key == "oewn-2025:00001740-n"
    assert ice_cream.senses[0].examples[0].text == "we ate ice cream"
    unable = next(record for record in result.records if record.lemma == "unable")
    assert unable.part_of_speech == "adjective"
    assert unable.senses[0].source_sense_key == "oewn-2025:00001740-s"

    staging = tmp_path / "staging"
    write_staging(result, staging)
    sources, records = load_staging(staging)
    assert sources[0].checksum == lock.sha256
    assert len(records) == 5
    report = json.loads((staging / "import-report.json").read_text())
    assert report["skipped_records"] == 0
    assert report["synset_examples"] == 1


def test_importer_rejects_an_archive_with_the_wrong_checksum(tmp_path: Path) -> None:
    archive, lock = _fixture_archive(tmp_path)
    changed_lock = lock.model_copy(update={"sha256": "0" * 64})
    with pytest.raises(OEWNError, match="pinned checksum"):
        import_archive(archive, changed_lock)


def test_acquire_reuses_a_checksum_valid_cached_archive(tmp_path: Path) -> None:
    archive, lock = _fixture_archive(tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    cached = cache / lock.filename
    cached.write_bytes(archive.read_bytes())

    assert acquire(lock, cache) == cached
