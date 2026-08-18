"""#563 — coverage introspection: which confusables does disarm NOT fold?

``find_untranslatable`` has existed for transliteration since #184. There was no
confusables analogue, so answering the coverage question meant building a harness
outside the library against a cached copy of ``confusables.txt``. That harness should
not have had to exist, and a user could not re-run the measurement against their own
traffic.

Assertions here are derived from the transform's actual behaviour wherever possible,
not from hardcoded expectations, so the two cannot drift apart silently.
"""

from __future__ import annotations

import pytest

import disarm

CYRILLIC_A = "а"  # folds to Latin 'a'
CYRILLIC_IE = "е"  # folds to Latin 'e'


@pytest.fixture(scope="module")
def latin_exposure() -> frozenset[str]:
    return disarm.unmapped_confusables()


# ── the global exposure set ──────────────────────────────────────────────────


def test_returns_a_frozenset_of_single_characters(latin_exposure: frozenset[str]) -> None:
    assert isinstance(latin_exposure, frozenset)
    assert latin_exposure
    assert all(isinstance(c, str) and len(c) == 1 for c in latin_exposure)


def test_nothing_in_the_set_actually_folds(latin_exposure: frozenset[str]) -> None:
    """The defining property, checked against the transform rather than the table.

    If the reported set ever disagreed with what ``normalize_confusables`` does, the
    coverage number would be describing something other than the library's behaviour.
    """
    for ch in latin_exposure:
        assert disarm.normalize_confusables(ch) == ch, f"U+{ord(ch):04X} folds"


def test_mapped_homoglyphs_are_absent(latin_exposure: frozenset[str]) -> None:
    for ch in (CYRILLIC_A, CYRILLIC_IE, "о"):
        assert ch not in latin_exposure


def test_the_two_targets_differ() -> None:
    """Coverage is per-table; one number for both would be wrong."""
    assert disarm.unmapped_confusables() != disarm.unmapped_confusables(target_script="cyrillic")


def test_unknown_target_script_raises() -> None:
    with pytest.raises(disarm.InvalidArgumentError):
        disarm.unmapped_confusables(target_script="klingon")


def test_ascii_residue_is_the_five_documented_skeleton_sources(
    latin_exposure: frozenset[str],
) -> None:
    """Pins the documented ASCII case.

    TR39 is a skeleton transform, so ``%``, ``0``, ``1``, ``I`` and ``m`` are upstream
    sources (m→rn, I/1→l, 0→O). disarm does not apply those rows, because folding a
    legitimate ASCII ``m`` to ``rn`` corrupts prose. They are reported rather than
    filtered — a coverage report that quietly drops rows reads as coverage it does not
    have — so a per-input scan over ordinary English will hit ``m``. This test makes any
    change to that set deliberate.
    """
    assert sorted(c for c in latin_exposure if c.isascii()) == ["%", "0", "1", "I", "m"]


def test_set_is_stable_across_calls(latin_exposure: frozenset[str]) -> None:
    assert disarm.unmapped_confusables() == latin_exposure


# ── the per-input scan ───────────────────────────────────────────────────────


def test_clean_input_reports_nothing() -> None:
    assert disarm.find_unmapped_confusables("") == []
    assert disarm.find_unmapped_confusables("hello") == []


def test_a_folded_homoglyph_is_coverage_not_a_gap() -> None:
    spoof = f"p{CYRILLIC_A}yp{CYRILLIC_A}l"
    assert disarm.normalize_confusables(spoof) == "paypal"
    assert disarm.find_unmapped_confusables(spoof) == []


def test_offsets_are_byte_offsets_in_the_input() -> None:
    text = f"am{CYRILLIC_A}xm"
    hits = disarm.find_unmapped_confusables(text)
    assert hits == [("m", 1), ("m", 5)]
    raw = text.encode("utf-8")
    for ch, offset in hits:
        assert raw[offset:].decode("utf-8")[0] == ch


def test_decomposed_homoglyph_counts_as_covered() -> None:
    """#475/#477 parity.

    ``і`` U+0456 + combining diaeresis composes to ``ї`` U+0457, which folds. Reporting
    the bare base as a gap would make the coverage number disagree with the transform.
    """
    decomposed = "ї"
    assert disarm.normalize_confusables(decomposed) == "i"
    assert disarm.find_unmapped_confusables(decomposed) == []


def test_offsets_survive_composition() -> None:
    """Offsets anchor to the caller's string, not the composed intermediate."""
    text = "їm"  # 2 + 2 bytes, then 'm'
    assert disarm.find_unmapped_confusables(text) == [("m", 4)]


def test_scan_only_reports_members_of_the_global_set(
    latin_exposure: frozenset[str],
) -> None:
    sample = "".join(sorted(latin_exposure)[:300])
    reported = disarm.find_unmapped_confusables(sample)
    assert reported
    for ch, _offset in reported:
        assert ch in latin_exposure


def test_scan_rejects_non_str() -> None:
    with pytest.raises(TypeError):
        disarm.find_unmapped_confusables(b"bytes")  # type: ignore[arg-type]


def test_scan_unknown_target_script_raises() -> None:
    with pytest.raises(disarm.InvalidArgumentError):
        disarm.find_unmapped_confusables("x", target_script="klingon")


@pytest.mark.parametrize(
    "text",
    [
        "hello world",
        f"p{CYRILLIC_A}ypal.com",
        "\U0001f980​́",
        "Ｆｕｌｌｗｉｄｔｈ",
        "각",  # conjoining Hangul jamo (#483)
        "á̂̃b",
    ],
)
def test_scan_is_sound_on_mixed_input(text: str) -> None:
    """Never panics; every reported offset indexes a real character in the input."""
    raw = text.encode("utf-8")
    for target in ("latin", "cyrillic"):
        for ch, offset in disarm.find_unmapped_confusables(text, target_script=target):
            assert 0 <= offset < len(raw)
            assert raw[offset:].decode("utf-8")[0] == ch


def test_this_is_what_makes_the_coverage_gap_regression_testable() -> None:
    """The motivating use: pin the residue so a closed gap cannot silently reopen.

    Once the established-core miss list is closed, a deployment can assert its own
    exposure does not grow. Demonstrated here with a bound rather than an exact count,
    since the number legitimately moves with a table refresh.
    """
    exposure = disarm.unmapped_confusables()
    assert 1_000 < len(exposure) < 6_000
