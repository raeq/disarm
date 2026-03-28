"""Formalized invariant specifications for translit.

Each invariant is stated as a formal property and tested via exhaustive
enumeration (where the domain is bounded) or Hypothesis (for unbounded domains).

Invariants
----------
I1: ASCII Passthrough   — ASCII input is returned unchanged.
I2: ASCII Output        — ErrorMode 'ignore' produces ASCII-only output.
I3: Idempotence         — Applying transliterate twice yields the same as once.
I4: No Exceptions       — No valid Unicode input causes an exception.
I5: Deterministic       — Same input always produces the same output.
I6: Input Size Bounded  — Inputs > 10 MiB are rejected with TranslitError.
I7: Output Length Bound — len(output) ≤ len(input) * 4 + char_count.
"""

import string

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import translit

# All tests in this module are marked 'formal' so they are excluded from
# everyday pytest runs.  Run before release with: pytest -m formal
pytestmark = pytest.mark.formal


# ── I1: ASCII Passthrough ───────────────────────────────────────────────

class TestI1AsciiPassthrough:
    """I1: For all s where s.isascii(), transliterate(s) == s."""

    def test_all_128_ascii_codepoints_individually(self):
        for i in range(128):
            ch = chr(i)
            result = translit.transliterate(ch)
            assert result == ch, f"ASCII U+{i:04X} ({ch!r}) → {result!r}"

    def test_all_printable_ascii_combined(self):
        text = string.printable
        assert translit.transliterate(text) == text

    @given(st.text(alphabet=st.characters(max_codepoint=127), min_size=1, max_size=500))
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_hypothesis_random_ascii(self, text):
        assert translit.transliterate(text) == text


# ── I2: ASCII Output (ErrorMode::Ignore) ───────────────────────────────

class TestI2AsciiOutput:
    """I2: For all s, transliterate(s, errors='ignore').isascii() == True."""

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
    def test_hypothesis_full_unicode(self, text):
        result = translit.transliterate(text, errors="ignore")
        assert result.isascii(), f"Non-ASCII output for {text!r}: {result!r}"

    def test_smp_characters(self):
        """SMP characters (above U+FFFF) also produce ASCII with errors='ignore'."""
        smp_chars = [
            "\U00010000",  # Linear B Syllable B008 A
            "\U0001F600",  # Grinning Face emoji
            "\U00020000",  # CJK Unified Ideograph Extension B
            "\U0001D400",  # Mathematical Bold Capital A
            "\U00010900",  # Phoenician Letter Alf
        ]
        for ch in smp_chars:
            result = translit.transliterate(ch, errors="ignore")
            assert result.isascii(), f"SMP U+{ord(ch):04X} → {result!r} not ASCII"


# ── I3: Idempotence ────────────────────────────────────────────────────

class TestI3Idempotence:
    """I3: For all s, transliterate(transliterate(s, errors='ignore'), errors='ignore')
    == transliterate(s, errors='ignore')."""

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_hypothesis_idempotence(self, text):
        once = translit.transliterate(text, errors="ignore")
        twice = translit.transliterate(once, errors="ignore")
        assert once == twice, f"Not idempotent: {text!r} → {once!r} → {twice!r}"


# ── I4: No Exceptions ──────────────────────────────────────────────────

class TestI4NoExceptions:
    """I4: For all valid Unicode strings s with len(s) ≤ 10 MiB,
    transliterate(s) does not raise an exception."""

    @given(st.text(min_size=0, max_size=500))
    @settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
    def test_hypothesis_no_exceptions(self, text):
        # Should not raise for any valid Unicode input
        translit.transliterate(text)

    def test_edge_cases(self):
        """Specific edge cases that might trigger errors."""
        edge_cases = [
            "",                          # empty string
            "\x00",                      # null byte
            "\uFEFF",                    # BOM
            "\uFFFD",                    # replacement character
            "\uFFFF",                    # non-character
            "\U0010FFFF",               # max Unicode scalar
            "\uD800"[0:0],              # empty (can't create surrogates in Python)
            "a" * 1000,                  # long ASCII
            "\u0300" * 100,             # combining marks only
            "\U0001F1FA\U0001F1F8",     # flag sequence (US)
        ]
        for text in edge_cases:
            translit.transliterate(text)  # should not raise


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
            first = translit.transliterate(text, errors="ignore")
            for _ in range(100):
                result = translit.transliterate(text, errors="ignore")
                assert result == first, f"Determinism violated for {text!r}"


# ── I6: Input Size Bounded ──────────────────────────────────────────────

class TestI6InputSizeBound:
    """I6: Inputs exceeding 10 MiB are rejected with TranslitError.

    Note: The Python wrapper has an ASCII fast path (`text.isascii() → return text`)
    that bypasses the Rust size check. We use non-ASCII input to exercise the
    Rust-level enforcement.
    """

    def test_at_boundary_ascii(self):
        """10 MiB ASCII input succeeds (Python fast path, no Rust call)."""
        text = "a" * (10 * 1024 * 1024)
        result = translit.transliterate(text)
        assert result == text

    def test_over_boundary_non_ascii(self):
        """Non-ASCII input over 10 MiB raises TranslitError.

        Using 'é' (2 bytes UTF-8) × (5 MiB + 1) = 10 MiB + 2 bytes.
        """
        text = "\u00e9" * (5 * 1024 * 1024 + 1)
        with pytest.raises(translit.TranslitError):
            translit.transliterate(text)


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
        result = translit.transliterate(text, errors="ignore")
        bound = len(text.encode("utf-8")) * 4 + len(text)
        assert len(result) <= bound, (
            f"Output length {len(result)} exceeds bound {bound} "
            f"for input of {len(text)} chars / {len(text.encode('utf-8'))} bytes"
        )
