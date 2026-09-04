"""The per-script confusable denominator (#963, #884).

`unmapped_confusables` measures one bundled table against the whole 6,565-source
population. For a target disarm ships that is the right question. For a script it does
not, the answer is determined by the table's absence — Greek would report almost the
entire population unmapped, and the number would mean only "there is no Greek table". A
count determined by an absence is a blind spot with a number in front of it, which is
worse than the exception it replaced, because it looks like data.

`confusable_coverage` answers the fair question instead: of the sources whose prototype
is in this script, how many does disarm reach. The two are pinned against each other
below — a census that stopped describing the tables beside it would still look
plausible on its own.
"""

import pytest

import disarm
from disarm import Script

#: Every single-code-point source in the bundled `confusables.txt`.
POPULATION = 6565


def test_greek_reports_its_own_denominator_not_the_population() -> None:
    """The row the function exists for."""
    greek = disarm.confusable_coverage("Greek")
    assert greek["sources"] == 159
    assert greek["sources"] < POPULATION / 10
    # And it is not zero: 71 of the 159 are Greek letters the *Latin* table folds.
    assert 0 < greek["folded"] < greek["sources"]


def test_folded_never_exceeds_sources() -> None:
    for name in disarm.list_scripts():
        row = disarm.confusable_coverage(name)
        assert row["folded"] <= row["sources"], name


def test_a_script_tr39_never_targets_reports_zero_of_zero() -> None:
    """`0 of 0` is a different statement from "no such script", and both are answers."""
    row = disarm.confusable_coverage("Thaana")
    assert row == {"script": "Thaana", "sources": 0, "folded": 0}


def test_an_unknown_script_is_refused_rather_than_answered() -> None:
    with pytest.raises(disarm.InvalidArgumentError):
        disarm.confusable_coverage("Nonexistent")


def test_the_census_agrees_with_the_bundled_tables() -> None:
    """The number the census reports is the number the fold surfaces actually produce.

    Summed across scripts, `folded` must equal the sources at least one bundled table
    folds — which `unmapped_confusables` reports from the other side, as the sources
    *no* table folds. A generated census that drifted from the tables shipped beside it
    would pass every other test in this file.
    """
    targets = ("latin", "cyrillic", "arabic", "hebrew")
    unfolded_by_all = set.intersection(
        *[set(disarm.unmapped_confusables(target_script=t)) for t in targets]
    )
    folded_somewhere = POPULATION - len(unfolded_by_all)

    census_total = sum(disarm.confusable_coverage(name)["folded"] for name in _census_scripts())
    assert census_total == folded_somewhere


def test_the_census_sums_to_the_whole_source_population() -> None:
    """Every source is counted exactly once, so no script's row is a share of a bucket."""
    assert sum(disarm.confusable_coverage(n)["sources"] for n in _census_scripts()) == (POPULATION)


def test_every_script_name_the_library_hands_out_is_accepted() -> None:
    """The names `list_scripts()` returns must reach their own census row.

    The census groups by the UCD's script property, and the UCD spells a multi-word
    script `Canadian_Aboriginal` where disarm spells it `CanadianAboriginal`. Keyed in
    the UCD's namespace, the name the library hands a caller missed the census entirely
    and fell through to the `0 of 0` branch — `CanadianAboriginal` reported no sources
    when it has 143. A count that reads as coverage and is determined by a lookup miss is
    the exact failure this function exists to remove, so it is asserted over every name
    rather than the few that happen to be one word.
    """
    for name in disarm.list_scripts():
        row = disarm.confusable_coverage(name)
        assert row["script"] == name, f"{name} echoed back as {row['script']!r}"


def test_a_multi_word_script_reports_its_sources() -> None:
    """The single case above, pinned by value so a table refresh cannot zero it."""
    assert disarm.confusable_coverage("CanadianAboriginal")["sources"] == 143


def test_the_ucd_spelling_is_not_a_second_namespace() -> None:
    """One spelling per script, or the census becomes a place to guess names."""
    with pytest.raises(disarm.InvalidArgumentError):
        disarm.confusable_coverage("Canadian_Aboriginal")


def test_no_census_key_carries_an_underscore() -> None:
    for name in _census_scripts():
        assert "_" not in name, f"{name} is in the UCD's namespace, not disarm's"


def test_scripts_the_enum_does_not_name_are_still_addressable() -> None:
    """The grouping is the UCD's, so it names scripts disarm's own enum does not.

    Dropping them would lose 72 sources from the census silently, and the totals above
    would still balance if the loss were also dropped from the population.
    """
    yi = disarm.confusable_coverage("Yi")
    assert yi["sources"] == 12
    assert "Yi" not in disarm.list_scripts()
    with pytest.raises(KeyError):
        disarm.script_info("Yi")
    # And a multi-word one, spelled disarm's way rather than the UCD's.
    assert disarm.confusable_coverage("PauCinHau")["sources"] == 13


def test_common_and_inherited_are_answerable_here() -> None:
    """1,036 sources have a Common or Inherited prototype; `script_info` refuses both.

    This is why the census is its own entry point rather than two more fields on
    `ScriptMeta`: the metadata table cannot reach 16% of the population.
    """
    assert disarm.confusable_coverage("Common")["sources"] == 893
    assert disarm.confusable_coverage("Inherited")["sources"] == 143
    for name in ("Common", "Inherited"):
        with pytest.raises(KeyError):
            disarm.script_info(name)


def test_an_enum_member_is_accepted_like_the_other_script_surfaces() -> None:
    assert disarm.confusable_coverage(Script.THAANA) == disarm.confusable_coverage("Thaana")


def test_the_shipped_targets_are_the_scripts_with_the_most_folded() -> None:
    """A sanity floor on the direction of the numbers, not a target list.

    disarm ships to-Latin, to-Cyrillic, to-Arabic and to-Hebrew tables, so Latin should
    dominate `folded` and a script with no table should not.
    """
    latin = disarm.confusable_coverage("Latin")
    han = disarm.confusable_coverage("Han")
    assert latin["folded"] > 1000
    assert han["sources"] > 1000
    assert han["folded"] == 0, "no CJK fold table ships, so nothing should fold to Han"


def _census_scripts() -> list[str]:
    """Every script the generated census has a row for, read from the TSV it ships."""
    from pathlib import Path

    tsv = Path(__file__).resolve().parent.parent / (
        "src/tables/data/confusable_prototype_census.tsv"
    )
    return [
        line.split("\t")[0]
        for line in tsv.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]


def test_the_shipped_census_is_what_its_inputs_produce() -> None:
    """The generator is the only author of the TSV, and it is re-runnable.

    A hand-edit to the census would move the numbers `confusable_coverage` reports
    without touching either input, so the figure would stop describing the data it
    claims to describe. `--check` re-derives the file from `data/confusables.txt` and
    `data/Scripts.txt` and compares.
    """
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(root / "scripts" / "gen_confusable_census.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=root,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
