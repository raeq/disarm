"""Property-based fuzzing of the raw-bytes decode path (#78).

The byte-decode API (`detect_encoding` / `decode_to_utf8`) is the one public
surface that ingests untrusted *raw bytes*. Unlike the str-based transforms it
was previously excluded from the adversarial/Hypothesis suites (those use
``st.text()`` and exclude surrogates). This module fuzzes it over arbitrary
byte sequences and asserts the security bar: **no panic + invariant
preservation**, never detection accuracy (a quality property per
THREAT_MODEL.md).

Tier 2 (developer worktree only) — excluded from CI like the other Hypothesis
suites. See CLAUDE.md.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from disarm import DisarmError, decode_to_utf8, detect_encoding

pytestmark = pytest.mark.hypothesis

# Encoding names accepted by the explicit-encoding decode path.
_ENCODINGS = [
    "utf-8",
    "utf-16",
    "shift_jis",
    "euc-jp",
    "euc-kr",
    "big5",
    "gb18030",
    "windows-1252",
]


def _assert_valid_str(s: str) -> None:
    assert isinstance(s, str)
    # A Rust String cannot contain lone surrogates; assert no leak regardless.
    assert not any(0xD800 <= ord(c) <= 0xDFFF for c in s)


@given(data=st.binary(max_size=4096))
def test_detect_encoding_never_panics(data: bytes) -> None:
    enc, conf = detect_encoding(data)
    assert isinstance(enc, str) and enc
    assert 0.0 <= conf <= 1.0


@given(data=st.binary(max_size=4096))
def test_decode_auto_never_panics(data: bytes) -> None:
    # min_confidence=0.0 disables the rejection gate, so this exercises the
    # full lossy-decode path for every byte sequence.
    s, had_errors = decode_to_utf8(data, min_confidence=0.0)
    _assert_valid_str(s)
    assert isinstance(had_errors, bool)


@given(data=st.binary(max_size=4096), encoding=st.sampled_from(_ENCODINGS))
def test_decode_explicit_encoding_never_panics(data: bytes, encoding: str) -> None:
    s, had_errors = decode_to_utf8(data, encoding=encoding)
    _assert_valid_str(s)
    assert isinstance(had_errors, bool)


@given(
    data=st.binary(max_size=4096),
    # Valid threshold domain is [0.0, 1.0]; exclude NaN/inf explicitly. (Bounded
    # st.floats already defaults allow_nan/allow_infinity to False, but being
    # explicit keeps the test's domain correct and version-independent — a NaN
    # would raise ValueError, not the DisarmError this property expects.)
    mc=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
def test_min_confidence_gate_is_total(data: bytes, mc: float) -> None:
    # For any byte sequence and any threshold, the auto path either returns a
    # valid (str, bool) or raises DisarmError on the confidence gate — never
    # anything else, never a panic.
    try:
        s, had_errors = decode_to_utf8(data, min_confidence=mc)
    except DisarmError:
        return
    _assert_valid_str(s)
    assert isinstance(had_errors, bool)


@given(data=st.binary(max_size=4096))
def test_decode_output_reencodes_to_utf8(data: bytes) -> None:
    # The returned str must itself be valid UTF-8 (round-trips cleanly).
    s, _ = decode_to_utf8(data, min_confidence=0.0)
    s.encode("utf-8")  # must not raise
