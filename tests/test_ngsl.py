from pathlib import Path

from lexicon.ngsl import import_csv, load_lock


def test_ngsl_import_uses_the_configured_five_bands() -> None:
    imported = import_csv(
        Path("data/seed/ngsl-1.2.csv"), load_lock(Path("data/sources/ngsl.lock.json"))
    )

    assert len(imported.members) == 2801
    by_rank = {member.rank: member.band for member in imported.members}
    assert by_rank[1] == 1
    assert by_rank[560] == 1
    assert by_rank[561] == 2
    assert by_rank[1121] == 3
    assert by_rank[1681] == 4
    assert by_rank[2241] == 5
    assert by_rank[2801] == 5
