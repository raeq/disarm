"""Tests that register_replacements() actually affects transliterate() output.

Regression coverage for #51: the global replacement table was write-only —
nothing consulted it, so register_replacements() was a silent no-op. These
tests pin the now-working contract: replacements are applied as a
longest-match pre-pass before transliteration, on the scalar, batch, and
context paths (forward direction only).
"""

from __future__ import annotations

import pytest

from disarm import (
    clear_replacements,
    register_replacements,
    remove_replacement,
    transliterate,
)


@pytest.fixture(autouse=True)
def _clean_replacement_table():
    """Isolate global replacement state: empty before and after every test."""
    clear_replacements()
    yield
    clear_replacements()


def test_non_ascii_key_applied() -> None:
    register_replacements({"Ω": "OMEGA", "→": "TO", "★": "STAR"})
    assert transliterate("Ω") == "OMEGA"
    assert transliterate("→") == "TO"
    assert transliterate("x★y") == "xSTARy"


def test_ascii_key_applied_despite_fast_path() -> None:
    # Pure-ASCII input previously short-circuited in Python before reaching
    # Rust, so ASCII-keyed replacements were ignored. They must apply now.
    register_replacements({"@": "(at)"})
    assert transliterate("a@b.com") == "a(at)b.com"


def test_no_replacements_is_identity_fast_path() -> None:
    # With nothing registered, ASCII passes straight through unchanged.
    assert transliterate("plain ascii") == "plain ascii"


def test_longest_match_wins() -> None:
    register_replacements({"ab": "X", "abc": "Y"})
    assert transliterate("abcd") == "Yd"  # "abc" beats "ab"
    assert transliterate("abx") == "Xx"


def test_no_cascade() -> None:
    # A replacement's output is not rescanned: a->b must not become b->c.
    register_replacements({"a": "b", "b": "c"})
    assert transliterate("aa") == "bb"


def test_runs_before_transliteration() -> None:
    # "™" -> "(tm)" pre-pass, then normal transliteration of the rest.
    register_replacements({"™": "(tm)"})
    assert transliterate("café™") == "cafe(tm)"


def test_batch_parity_with_scalar() -> None:
    register_replacements({"@": "(at)", "Ω": "OMEGA"})
    data = ["a@b", "Ωz", "plain"]
    assert transliterate(data) == [transliterate(x) for x in data]
    assert transliterate(data) == ["a(at)b", "OMEGAz", "plain"]


def test_clear_restores_defaults() -> None:
    register_replacements({"Ω": "OMEGA", "@": "(at)"})
    clear_replacements()
    assert transliterate("Ω") == "O"
    assert transliterate("a@b") == "a@b"


def test_remove_single_key_keeps_others() -> None:
    register_replacements({"@": "(at)", "#": "(hash)"})
    assert remove_replacement("@") is True
    assert transliterate("a@b") == "a@b"  # removed
    assert transliterate("a#b") == "a(hash)b"  # still active


def test_merge_overwrites_existing_key() -> None:
    register_replacements({"@": "(at)"})
    register_replacements({"@": "AT"})  # overwrite
    assert transliterate("@") == "AT"


def _arabic_context_available() -> bool:
    # Context dicts are not shipped/tracked (#53); CI has none, so skip rather
    # than fail. Only "dictionary not found" is a skip condition.
    try:
        transliterate("كتب", lang="ar", context=True)
        return True
    except Exception as e:
        if "not found" in str(e).lower():
            return False
        raise


@pytest.mark.skipif(
    not _arabic_context_available(),
    reason="Arabic context dictionary not available (build via bootstrap_dicts.sh)",
)
def test_context_path_parity() -> None:
    # Forward transliteration must behave the same with and without context=True.
    register_replacements({"@": "(at)"})
    assert transliterate("a@b", lang="ar", context=True) == "a(at)b"
