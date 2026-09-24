"""The documented properties the #1040 fuzz targets found false, through the binding.

The Rust side of each is in ``tests/fuzz_findings.rs``, and the fuzz targets in ``fuzz/``
assert the full properties again. Non-ASCII test data is written as escapes so that no
invisible or unusual character is written into this file.
"""

from __future__ import annotations

import unicodedata

import pytest

from disarm import slugify

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
