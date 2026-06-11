"""Property-based coverage for register_replacements() (#51).

Marked `hypothesis` so it is excluded from CI (slow/non-deterministic) per the
project's test tiering, but run locally via `pytest`.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from disarm import clear_replacements, register_replacements, transliterate

pytestmark = pytest.mark.hypothesis

# Single, non-surrogate characters for the replacement key.
_keys = st.characters(blacklist_categories=("Cs",))
# Short replacement / input strings, no surrogates.
_vals = st.text(st.characters(blacklist_categories=("Cs",)), max_size=6)
_texts = st.text(st.characters(blacklist_categories=("Cs",)), max_size=40)


@given(key=_keys, value=_vals, text=_texts)
def test_single_key_equiv_to_str_replace_then_transliterate(
    key: str, value: str, text: str
) -> None:
    """For a single key, applying the registered replacement then transliterating
    must equal transliterating the input with the key textually replaced first.

    This pins both the longest-match pre-pass semantics (which, for one key,
    coincide with str.replace) AND that the replacement is actually wired into
    transliterate() on every path — including pure-ASCII inputs that take the
    Python fast path.
    """
    # Baseline: replace in source text, then transliterate with no table active.
    clear_replacements()
    expected = transliterate(text.replace(key, value))

    # Registered path: transliterate the raw text with the replacement active.
    clear_replacements()
    register_replacements({key: value})
    try:
        actual = transliterate(text)
    finally:
        clear_replacements()

    assert actual == expected


@given(text=_texts)
def test_empty_table_is_identity_transliteration(text: str) -> None:
    """With no replacements registered, output matches a clean transliterate."""
    clear_replacements()
    baseline = transliterate(text)
    register_replacements({})  # registering nothing must not change anything
    try:
        assert transliterate(text) == baseline
    finally:
        clear_replacements()
