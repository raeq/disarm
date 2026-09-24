"""The documented properties the #1040 fuzz targets found false, through the binding.

The Rust side of each is in ``tests/fuzz_findings.rs``, and the fuzz targets in ``fuzz/``
assert the full properties again. Non-ASCII test data is written as escapes so that no
invisible or unusual character is written into this file.
"""

from __future__ import annotations

import unicodedata

import pytest

from disarm import (
    find_confusables,
    find_unmapped_confusables,
    find_untranslatable,
    slugify,
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
