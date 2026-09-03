"""The map for derived deterministic identifiers (#731), backed the way the CVE page is.

``docs/security/derived-identifiers.md`` carries a variance-class x key matrix. The table
is *generated* from the registry below, not transcribed, because it moves when the
confusables data moves (#644, #645): this file renders it and fails when the page drifts.
Every prose claim on the page that quotes a count is asserted here as well.

**Every assertion here was measured before it was written.**
"""

from __future__ import annotations

from pathlib import Path

import pytest

import disarm

DOC = Path(__file__).resolve().parent.parent / "docs" / "security" / "derived-identifiers.md"

#: The seven keys a caller might reach for. `sort_key` is not one: a sort key exists to
#: order, and `find_key_collisions` declines it for the same reason.
KEYS = (
    "fold_case",
    "search_key",
    "catalog_key",
    "canonicalize",
    "canonicalize_strict",
    "normalize_confusables",
    "skeleton_key",
)

#: Same order, spelled two ways. A derived identifier must merge these.
MUST_MERGE = (
    ("NFC vs NFD", "r\u00e9sum\u00e9", "re\u0301sume\u0301"),
    ("fullwidth digits", "order 123", "order １２３"),
    ("fullwidth letters", "abc", "ａｂｃ"),
    ("case", "Order", "order"),
    ("zero-width space", "ab", "a\u200bb"),
    ("soft hyphen", "ab", "a\u00adb"),
    ("RLO control", "ab", "a\u202eb"),
    ("Cyrillic homoglyph", "paypal", "pаypal"),
    ("NBSP for space", "a b", "a\u00a0b"),
    ("edge whitespace", "ab", " ab "),
    ("duplicated marks", "e\u0301", "e\u0301\u0301"),
    ("tag characters", "ab", "a\U000e0041b"),
    ("variation selector", "ab", "a\ufe0fb"),
    ("ligature", "fi", "ﬁ"),
    ("sharp s", "strasse", "straße"),
)

#: Distinct values. A derived identifier must keep these apart.
MUST_NOT_MERGE = (
    ("accent (`resume`/`résumé`)", "resume", "résumé"),
    ("digit system (`1`/`١`)", "1", "١"),
    ("vulgar fraction (`1/2`/`½`)", "1/2", "½"),
    ("circled digits (`100.00`/`①⓪⓪.⓪⓪`)", "100.00", "①⓪⓪.⓪⓪"),
    ("romanization (`Война`/`Voyna`)", "Война", "Voyna"),
    ("case-significant id (`SKU-a`/`SKU-A`)", "SKU-a", "SKU-A"),
)


def merges(key: str, a: str, b: str) -> bool:
    f = getattr(disarm, key)
    return bool(f(a) == f(b))


def render(rows: tuple[tuple[str, str, str], ...], want_merge: bool) -> str:
    """The table exactly as the page carries it. `<-` marks a cell the use cannot take."""
    out = ["| class | " + " | ".join(f"`{k}`" for k in KEYS) + " |", "|---|" + "---|" * len(KEYS)]
    for name, a, b in rows:
        cells = []
        for k in KEYS:
            m = merges(k, a, b)
            cells.append(("merge" if m else "distinct") + (" `<-`" if m != want_merge else ""))
        out.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def wrong(rows: tuple[tuple[str, str, str], ...], want_merge: bool, key: str) -> list[str]:
    return [name for name, a, b in rows if merges(key, a, b) != want_merge]


class TestTheRegistryIsWellFormed:
    def test_the_counts_the_page_quotes(self) -> None:
        assert len(MUST_MERGE) == 15
        assert len(MUST_NOT_MERGE) == 6

    def test_every_pair_really_is_two_spellings(self) -> None:
        assert all(a != b for _, a, b in MUST_MERGE + MUST_NOT_MERGE)


class TestDocsMatrixDrift:
    """The page and the build must agree, cell for cell."""

    def test_doc_page_exists(self) -> None:
        assert DOC.is_file(), f"missing {DOC}"

    def test_the_must_merge_table_is_the_rendered_one(self) -> None:
        assert render(MUST_MERGE, True) in DOC.read_text(encoding="utf-8")

    def test_the_must_not_merge_table_is_the_rendered_one(self) -> None:
        assert render(MUST_NOT_MERGE, False) in DOC.read_text(encoding="utf-8")


class TestWhatThePageSays:
    """Each count in the prose, pinned so the sentence cannot go stale alone."""

    def test_no_column_is_clean(self) -> None:
        for key in KEYS:
            assert wrong(MUST_MERGE, True, key) or wrong(MUST_NOT_MERGE, False, key), key

    @pytest.mark.parametrize("key", ["search_key", "catalog_key"])
    def test_search_and_catalog_keys_merge_every_distinct_value(self, key: str) -> None:
        assert wrong(MUST_MERGE, True, key) == []
        assert len(wrong(MUST_NOT_MERGE, False, key)) == len(MUST_NOT_MERGE)

    def test_canonicalize_is_closest_and_every_failure_changes_a_number(self) -> None:
        assert wrong(MUST_MERGE, True, "canonicalize") == ["case", "sharp s"]
        assert wrong(MUST_NOT_MERGE, False, "canonicalize") == [
            "digit system (`1`/`١`)",
            "vulgar fraction (`1/2`/`½`)",
            "circled digits (`100.00`/`①⓪⓪.⓪⓪`)",
        ]
        assert disarm.canonicalize("amount-١") == "amount-1"
        assert disarm.canonicalize("qty-½") == "qty-1/2"
        assert disarm.canonicalize("①⓪⓪.⓪⓪") == "100.00"

    def test_skeleton_key_is_a_spoof_key(self) -> None:
        assert len(wrong(MUST_NOT_MERGE, False, "skeleton_key")) == 4

    def test_preserve_is_a_no_op_on_six_builders_until_949(self) -> None:
        # Both halves: the fold and the one threaded builder honour it, the six do not.
        # When #896 threads the policy through the presets this flips, and so does #949.
        x = "amount-١"
        assert disarm.normalize_confusables(x, digit_policy="preserve") == x
        assert disarm.skeleton_key(x, digit_policy="preserve") == x
        for name in (
            "canonicalize",
            "canonicalize_strict",
            "strip_obfuscation",
            "search_key",
            "catalog_key",
            "sort_key",
        ):
            assert getattr(disarm, name)(x, digit_policy="preserve") == "amount-1", name

    def test_is_canonical_is_the_write_time_check(self) -> None:
        assert disarm.is_canonical("amount-1", preset="canonicalize")
        assert not disarm.is_canonical("amount-١", preset="canonicalize")
