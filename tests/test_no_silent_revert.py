"""A merged pull request's data files are still on `main`.

Written because one was not. #851 was collapsed to a single commit with
`git reset --soft origin/main` at a moment when `origin/main` had moved ahead: the
working tree predated #847, so committing recorded the **deletion** of everything #847
had added. Fourteen files, 140 lines of `build.rs` and the whole of
`data/confusables_lgr.tsv` and `tests/test_lgr_pairs.py`.

CI stayed green, and that is the part worth a gate. The test file that would have caught
it was deleted in the same commit, so the only surviving evidence was that
`canonicalize("ż") != canonicalize("ź")` — a behaviour nothing else asserted.

This checks the *artifacts* rather than the behaviour, because behaviour tests travel with
the feature and vanish with it. A bundled data file is referenced from `build.rs` or a
generator, so its absence is a build-level fact that a deleted test cannot hide.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: Bundled data every shipped feature depends on, with what reads it. A file here must
#: exist *and* be referenced, since an orphaned file is its own kind of rot.
BUNDLED_DATA = {
    "data/confusables.txt": "scripts/gen_confusables.py",
    "data/confusables_lgr.tsv": "scripts/gen_confusables.py",
    "data/confusables_supplement.tsv": "scripts/gen_confusables.py",
    "data/confusables_attested.tsv": "scripts/gen_confusables.py",
    "src/tables/data/confusables_to_latin.tsv": "build.rs",
    "src/tables/data/assigned_ranges.tsv": "build.rs",
    "src/tables/data/bidi_strong_ranges.tsv": "build.rs",
}


@pytest.mark.parametrize(("data", "reader"), sorted(BUNDLED_DATA.items()))
def test_the_data_file_exists_and_something_reads_it(data: str, reader: str) -> None:
    path = ROOT / data
    assert path.is_file(), (
        f"{data} is gone. It is bundled data a shipped feature depends on — if its "
        "removal is deliberate, take it off this list in the same change."
    )
    assert path.stat().st_size > 0, f"{data} is empty"
    name = Path(data).name
    source = (ROOT / reader).read_text(encoding="utf-8")
    assert name in source, f"{data} exists but {reader} no longer names it, so nothing consumes it"


def test_the_lgr_pairs_still_collide() -> None:
    """The behaviour the deletion silently removed, asserted where it cannot travel with
    the feature.

    `tests/test_lgr_pairs.py` covers this properly and in detail — and was deleted by the
    same commit that removed the data, so it could not fail. This duplicate lives in a
    file about *artifacts* precisely so that losing the feature's own tests does not also
    lose the alarm.
    """
    import disarm

    for left, right, why in [
        ("ż", "ź", "z-dot / z-acute"),
        ("ò", "ỏ", "o-grave / o-hook"),
        ("ǝ", "ə", "turned e / schwa"),
    ]:
        assert disarm.canonicalize(left) == disarm.canonicalize(right), (
            f"the ICANN LGR pair {why} no longer collides (#831); the data or the "
            "build-time merge has gone"
        )


def test_the_build_assert_on_non_ascii_targets_is_present() -> None:
    """#831's two conditions are build-time asserts, and asserts can be deleted.

    They are the reason a non-ASCII fold target is safe. Their absence would not fail any
    build, because an assert that is not there does not fire.
    """
    build = (ROOT / "build.rs").read_text(encoding="utf-8")
    for marker, why in [
        ("is_latin_letter", "the non-ASCII target must be a Latin letter"),
        ("COMMON_SCRIPT_TARGETS", "the named exemption for Script=Common targets"),
        ("itself a source", "the target must not chain the fold"),
    ]:
        assert marker in build, f"build.rs lost {marker!r} — {why} (#831)"
