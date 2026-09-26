"""The documented properties the #1040 fuzz targets found false, through the binding.

The Rust side of each is in ``tests/fuzz_findings.rs``, and the fuzz targets in ``fuzz/``
assert the full properties again. Non-ASCII test data is written as escapes so that no
invisible or unusual character is written into this file.
"""

from __future__ import annotations

import unicodedata

import pytest

from disarm import (
    DisarmError,
    canonicalize,
    canonicalize_strict,
    catalog_key,
    find_confusables,
    find_unmapped_confusables,
    find_untranslatable,
    is_confusable,
    normalize_confusables,
    sanitize_filename,
    search_key,
    skeleton_key,
    slugify,
    strip_obfuscation,
    transliterate,
)

# -- 1. slugify: a numeric entity that fails to decode ------------------------------------


@pytest.mark.parametrize(
    ("text", "slug"),
    [
        ("Q&#A session", "q-a-session"),
        ("Tom &#and Jerry", "tom-and-jerry"),
        ("issue &#12 fixed", "issue-fixed"),
        ("a &#x; b", "a-x-b"),
        ("caf&#233;", "cafe"),
        ("caf&#233 au lait", "cafe-au-lait"),
    ],
)
def test_text_after_an_undecodable_entity_survives(text: str, slug: str) -> None:
    assert slugify(text) == slug


@pytest.mark.parametrize(
    "text", ["&#a\u0301", "&#\u00e1", "&#xa\u0301", "&#x4a\u0301b", "&#x\u030741;"]
)
def test_an_entity_reads_the_same_in_both_normal_forms(text: str) -> None:
    nfc = unicodedata.normalize("NFC", text)
    nfd = unicodedata.normalize("NFD", text)
    assert slugify(nfc, allow_unicode=True) == slugify(nfd, allow_unicode=True)


# -- 2. The locators report a character of the input, at its own offset --------------

LOCATED = [
    "\u04aa\u0327",
    "x\ufe0f",
    "a\u0456\u0308",
    "\u05e9\u05bc",
    "a\u0301\u0323",
    "\u0915\u093c\u0903",
    "\U00016d63\U00016d67\U00016d67",
]


@pytest.mark.parametrize("text", LOCATED)
def test_every_report_points_at_its_character(text: str) -> None:
    for target in ("latin", "cyrillic", "arabic", "hebrew"):
        for ch, offset, _ in find_confusables(text, target_script=target):
            assert text.encode()[offset:].decode().startswith(ch)
        for ch, offset in find_unmapped_confusables(text, target_script=target):
            assert text.encode()[offset:].decode().startswith(ch)
    for ch, offset in find_untranslatable(text):
        assert text.encode()[offset:].decode().startswith(ch)


def test_a_mark_is_at_its_own_offset_and_a_homoglyph_is_its_base() -> None:
    assert find_untranslatable("x\ufe0f") == [("\ufe0f", 1)]
    assert ("\u0327", 2) in find_unmapped_confusables("\u04aa\u0327")
    assert find_confusables("a\u0456\u0308") == [("\u0456", 1, "i")]


# -- 3. find_untranslatable: a compatibility character recovered only in part ---------


def test_a_partial_compatibility_recovery_is_reported() -> None:
    assert transliterate("\U0001f240") == "[?]ben[?]"
    assert find_untranslatable("x\U0001f240y") == [("\U0001f240", 1)]
    with pytest.raises(DisarmError, match=r"U\+1F240"):
        transliterate("\U0001f240", errors="strict")
    assert find_untranslatable("\ufb01\u337f") == []


# -- 4. sanitize_filename: a fixed point, however many passes it takes -----------------


@pytest.mark.parametrize("n", [1, 8, 9, 64])
@pytest.mark.parametrize("unit", [".*", ". ", ".?.", "*."])
@pytest.mark.parametrize("preserve_extension", [False, True])
def test_a_run_of_empty_extensions_is_a_fixed_point(
    n: int, unit: str, preserve_extension: bool
) -> None:
    once = sanitize_filename("a" + unit * n, preserve_extension=preserve_extension)
    assert sanitize_filename(once, preserve_extension=preserve_extension) == once


def test_nine_empty_extensions() -> None:
    assert sanitize_filename("a" + ".*" * 9, preserve_extension=False) == "a"


# -- 5. slugify: allow_unicode with an empty separator composes across words ----------


@pytest.mark.parametrize(
    ("text", "slug"),
    [
        ("\u1100 \u1161", "\uac00"),
        ("\U00016d67,\U00016d67", "\U00016d68"),
        ("\U00016d63!\U00016d67", "\U00016d69"),
    ],
)
def test_an_empty_separator_slug_is_its_own_slug(text: str, slug: str) -> None:
    once = slugify(text, allow_unicode=True, separator="")
    assert once == slug
    assert slugify(once, allow_unicode=True, separator="") == once


# -- 8. slugify: an enclosed Latin letter comes from the separator, not the text ------


def test_an_enclosed_latin_letter_in_the_slug_is_the_separators() -> None:
    circled_a = "\u24b6"
    assert slugify("admin x", allow_unicode=True, separator=circled_a) == "admin" + circled_a + "x"
    out = slugify(circled_a + "dmin " + circled_a, allow_unicode=True, separator="-")
    assert out == "dmin"


# -- 7. The key builders end in NFC ------------------------------------------------------


@pytest.mark.parametrize("digit_policy", ["numeric", "tr39", "preserve"])
@pytest.mark.parametrize(
    "text",
    [
        "\ufffd\ufffd\U00016d67\x16\U00016d67",
        "\U00016d67\x00\U00016d67",
        "\U00016d63\x01\U00016d67",
    ],
)
def test_a_key_is_its_own_key_across_a_stripped_control(text: str, digit_policy: str) -> None:
    for key in (catalog_key, search_key):
        once = key(text, digit_policy=digit_policy)
        assert key(once, digit_policy=digit_policy) == once
        assert "\x00" not in once and "\x01" not in once
    assert catalog_key("\U00016d67\x00\U00016d67") == "\U00016d68"


# -- 9. normalize_confusables: a fold cycle outlasted the pass cap ------------------------


@pytest.mark.parametrize("digit_policy", ["numeric", "tr39", "preserve"])
@pytest.mark.parametrize(("base", "mark"), [("C", "\u0327"), ("c", "\u0327"), ("i", "\u0309")])
@pytest.mark.parametrize("n", [9, 64, 10_000])
def test_a_fold_cycle_takes_every_mark_however_many(
    base: str, mark: str, n: int, digit_policy: str
) -> None:
    once = normalize_confusables(base + mark * n, digit_policy=digit_policy)
    assert once == base
    assert not is_confusable(once)


@pytest.mark.parametrize("digit_policy", ["numeric", "tr39", "preserve"])
@pytest.mark.parametrize(
    "text",
    [
        "C" + "\u0327" * 9,
        "c" + "\u0327" * 64,
        "i" + "\u0309" * 2_000,
        "A. \u03aa\u04aa\u0327\u032a\u0327\u0327\u0327\u0327\u032a\u0327\u0327\u0327\u032c",
    ],
)
def test_every_preset_takes_every_mark_of_a_fold_cycle(text: str, digit_policy: str) -> None:
    for preset in (
        canonicalize,
        canonicalize_strict,
        strip_obfuscation,
        catalog_key,
        search_key,
        skeleton_key,
    ):
        once = preset(text, digit_policy=digit_policy)
        assert preset(once, digit_policy=digit_policy) == once, preset.__name__
