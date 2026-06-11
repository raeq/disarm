"""Formalized invariant specifications for disarm.

Each invariant is stated as a formal property and tested via exhaustive
enumeration (where the domain is bounded) or Hypothesis (for unbounded domains).

Invariants
----------
I1: ASCII Passthrough   — ASCII input is returned unchanged.
I2: ASCII Output        — ErrorMode 'ignore' produces ASCII-only output.
I3: Idempotence         — Applying transliterate twice yields the same as once.
I4: No Exceptions       — No valid Unicode input causes an exception.
I5: Deterministic       — Same input always produces the same output.
I6: Input Size Bounded  — Inputs > 10 MiB are rejected with DisarmError.
I7: Output Length Bound — len(output) ≤ len(input) * 4 + char_count.
"""

import string

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import disarm

# All tests in this module are marked 'formal' so they are excluded from
# everyday pytest runs.  Run before release with: pytest -m formal
pytestmark = pytest.mark.formal


# ── I1: ASCII Passthrough ───────────────────────────────────────────────


class TestI1AsciiPassthrough:
    """I1: For all s where s.isascii(), transliterate(s) == s."""

    def test_all_128_ascii_codepoints_individually(self):
        for i in range(128):
            ch = chr(i)
            result = disarm.transliterate(ch)
            assert result == ch, f"ASCII U+{i:04X} ({ch!r}) → {result!r}"

    def test_all_printable_ascii_combined(self):
        text = string.printable
        assert disarm.transliterate(text) == text

    @given(st.text(alphabet=st.characters(max_codepoint=127), min_size=1, max_size=500))
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_hypothesis_random_ascii(self, text):
        assert disarm.transliterate(text) == text


# ── I2: ASCII Output (ErrorMode::Ignore) ───────────────────────────────


class TestI2AsciiOutput:
    """I2: For all s, transliterate(s, errors='ignore').isascii() == True."""

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
    def test_hypothesis_full_unicode(self, text):
        result = disarm.transliterate(text, errors="ignore")
        assert result.isascii(), f"Non-ASCII output for {text!r}: {result!r}"

    def test_smp_characters(self):
        """SMP characters (above U+FFFF) also produce ASCII with errors='ignore'."""
        smp_chars = [
            "\U00010000",  # Linear B Syllable B008 A
            "\U0001f600",  # Grinning Face emoji
            "\U00020000",  # CJK Unified Ideograph Extension B
            "\U0001d400",  # Mathematical Bold Capital A
            "\U00010900",  # Phoenician Letter Alf
        ]
        for ch in smp_chars:
            result = disarm.transliterate(ch, errors="ignore")
            assert result.isascii(), f"SMP U+{ord(ch):04X} → {result!r} not ASCII"


# ── I3: Idempotence ────────────────────────────────────────────────────


class TestI3Idempotence:
    """I3: For all s, transliterate(transliterate(s, errors='ignore'), errors='ignore')
    == transliterate(s, errors='ignore')."""

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_hypothesis_idempotence(self, text):
        once = disarm.transliterate(text, errors="ignore")
        twice = disarm.transliterate(once, errors="ignore")
        assert once == twice, f"Not idempotent: {text!r} → {once!r} → {twice!r}"


# ── I4: No Exceptions ──────────────────────────────────────────────────


class TestI4NoExceptions:
    """I4: For all valid Unicode strings s with len(s) ≤ 10 MiB,
    transliterate(s) does not raise an exception."""

    @given(st.text(min_size=0, max_size=500))
    @settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
    def test_hypothesis_no_exceptions(self, text):
        # Should not raise for any valid Unicode input
        disarm.transliterate(text)

    def test_edge_cases(self):
        """Specific edge cases that might trigger errors."""
        edge_cases = [
            "",  # empty string
            "\x00",  # null byte
            "\ufeff",  # BOM
            "\ufffd",  # replacement character
            "\uffff",  # non-character
            "\U0010ffff",  # max Unicode scalar
            "\ud800"[0:0],  # empty (can't create surrogates in Python)
            "a" * 1000,  # long ASCII
            "\u0300" * 100,  # combining marks only
            "\U0001f1fa\U0001f1f8",  # flag sequence (US)
        ]
        for text in edge_cases:
            disarm.transliterate(text)  # should not raise


# ── I5: Deterministic ──────────────────────────────────────────────────


class TestI5Deterministic:
    """I5: For all s, n > 0: transliterate(s) called n times yields the same result."""

    def test_100x_repeat_mixed_scripts(self):
        inputs = [
            "北京市 서울 Москва café ひらがな",
            "नमस्ते مرحبا שלום Αθήνα",
            "混合テスト αβγ δεζ",
            "Ünïcödé Ärger straße",
            "カタカナ ひらがな 漢字",
            "대한민국 한글 テスト",
            "กรุงเทพ ลาว ថ្នាក់",
            "සිංහල མཁའ་འགྲོ ម៉ាស៊ីន",
            "emoji: 🎉🌍🔥",
            "mixed: abc 北京 ㄱ カタ",
        ]
        for text in inputs:
            first = disarm.transliterate(text, errors="ignore")
            for _ in range(100):
                result = disarm.transliterate(text, errors="ignore")
                assert result == first, f"Determinism violated for {text!r}"


# ── I6: No library-imposed input-size cap (#80) ─────────────────────────


class TestI6NoInputSizeCap:
    """I6: disarm imposes no raw input-size limit — bounding untrusted input is
    the caller's responsibility (every operation is linear time/memory). The only
    retained size bound is the register_replacements output amplification guard,
    where a tiny input can expand to an enormous string via a caller-registered
    replacement value (an amplification the caller's own input check cannot see).
    """

    def test_large_ascii_accepted(self):
        """>10 MiB ASCII input is accepted unchanged (no cap, fast path)."""
        text = "a" * (12 * 1024 * 1024)
        assert disarm.transliterate(text) == text

    def test_large_non_ascii_accepted(self):
        """>10 MiB non-ASCII input is accepted (exercises the Rust path)."""
        text = "\u00e9" * (6 * 1024 * 1024)  # ~12 MiB; e-acute -> e
        assert disarm.transliterate(text) == "e" * (6 * 1024 * 1024)

    def test_replacement_amplification_bounded(self):
        """The one retained guard: replacement expansion is still bounded."""
        disarm.clear_replacements()
        disarm.register_replacements({"a": "X" * 2_000_000})
        try:
            with pytest.raises(disarm.DisarmError):
                disarm.transliterate("a" * 10)  # ~20 MB output > 10 MiB cap
        finally:
            disarm.clear_replacements()


# ── I7: Output Length Bounded ───────────────────────────────────────────


class TestI7OutputLengthBound:
    """I7: For ErrorMode::Ignore, len(output) ≤ len(input) * 4 + char_count.

    This bound arises because:
    - Each input byte maps to at most ~4 output ASCII bytes (CJK pinyin is longest)
    - Spacing between CJK characters adds at most char_count spaces
    """

    @given(st.text(min_size=1, max_size=500))
    @settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
    def test_hypothesis_output_bound(self, text):
        result = disarm.transliterate(text, errors="ignore")
        bound = len(text.encode("utf-8")) * 4 + len(text)
        assert len(result) <= bound, (
            f"Output length {len(result)} exceeds bound {bound} "
            f"for input of {len(text)} chars / {len(text.encode('utf-8'))} bytes"
        )
