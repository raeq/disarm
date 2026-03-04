"""Fuzz tests using Hypothesis for translit edge cases.

Targets: entity decoder (via slugify), encoding detection/decoding,
emoji parsing (via demojize), and transliteration with random Unicode.
"""

from __future__ import annotations

from hypothesis import given, settings, HealthCheck
import hypothesis.strategies as st

import translit


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Unicode text including BMP, supplementary planes, and control chars
full_unicode = st.text(
    alphabet=st.characters(
        codec="utf-8",
        categories=("L", "M", "N", "P", "S", "Z", "C"),
    ),
    min_size=0,
    max_size=500,
)

# Text containing HTML entities
html_entity_text = st.one_of(
    st.from_regex(r"&#[0-9]{1,7};", fullmatch=True),
    st.from_regex(r"&#x[0-9a-fA-F]{1,6};", fullmatch=True),
    st.from_regex(r"&[a-zA-Z]{1,10};", fullmatch=True),
    full_unicode,
)

# Byte sequences for encoding detection
random_bytes = st.binary(min_size=0, max_size=1000)


# ---------------------------------------------------------------------------
# Transliteration fuzz
# ---------------------------------------------------------------------------


class TestTransliterateFuzz:
    """transliterate() must never panic on any valid Unicode string."""

    @given(text=full_unicode)
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_never_panics(self, text: str) -> None:
        result = translit.transliterate(text)
        assert isinstance(result, str)

    @given(text=full_unicode)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_errors_ignore_never_panics(self, text: str) -> None:
        result = translit.transliterate(text, errors="ignore")
        assert isinstance(result, str)

    @given(text=full_unicode)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_errors_preserve_never_panics(self, text: str) -> None:
        result = translit.transliterate(text, errors="preserve")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Slugify / entity decoder fuzz
# ---------------------------------------------------------------------------


class TestSlugifyFuzz:
    """slugify() exercises the entity decoder — must never panic."""

    @given(text=full_unicode)
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_never_panics(self, text: str) -> None:
        result = translit.slugify(text)
        assert isinstance(result, str)

    @given(text=html_entity_text)
    @settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
    def test_entity_patterns(self, text: str) -> None:
        result = translit.slugify(text, entities=True, decimal=True, hexadecimal=True)
        assert isinstance(result, str)

    @given(
        text=full_unicode,
        sep=st.sampled_from(["-", "_", ".", ""]),
        max_len=st.integers(min_value=0, max_value=500),
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_with_options(self, text: str, sep: str, max_len: int) -> None:
        result = translit.slugify(text, separator=sep, max_length=max_len)
        assert isinstance(result, str)
        if max_len > 0:
            assert len(result) <= max_len


# ---------------------------------------------------------------------------
# Encoding detection fuzz
# ---------------------------------------------------------------------------


class TestEncodingFuzz:
    """detect_encoding() and decode_to_utf8() must never panic on any bytes."""

    @given(data=random_bytes)
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_detect_never_panics(self, data: bytes) -> None:
        enc, conf = translit.detect_encoding(data)
        assert isinstance(enc, str)
        assert isinstance(conf, float)
        assert 0.0 <= conf <= 1.0

    @given(data=random_bytes)
    @settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
    def test_decode_auto_never_panics(self, data: bytes) -> None:
        text, had_errors = translit.decode_to_utf8(data)
        assert isinstance(text, str)
        assert isinstance(had_errors, bool)

    @given(
        data=random_bytes,
        encoding=st.sampled_from([
            "utf-8", "windows-1252", "iso-8859-1", "shift_jis",
            "euc-jp", "euc-kr", "big5", "gb18030",
        ]),
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_decode_with_encoding_never_panics(
        self, data: bytes, encoding: str
    ) -> None:
        text, had_errors = translit.decode_to_utf8(data, encoding=encoding)
        assert isinstance(text, str)
        assert isinstance(had_errors, bool)


# ---------------------------------------------------------------------------
# Demojize / emoji parser fuzz
# ---------------------------------------------------------------------------


class TestDemojizeFuzz:
    """demojize() must never panic on any Unicode string."""

    @given(text=full_unicode)
    @settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
    def test_never_panics(self, text: str) -> None:
        result = translit.demojize(text)
        assert isinstance(result, str)

    @given(text=full_unicode)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_strip_modifiers_never_panics(self, text: str) -> None:
        result = translit.demojize(text, strip_modifiers=True)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Pipeline fuzz
# ---------------------------------------------------------------------------


class TestPipelineFuzz:
    """Full pipeline with random flags must never panic."""

    @given(text=full_unicode)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_security_clean_never_panics(self, text: str) -> None:
        result = translit.security_clean(text)
        assert isinstance(result, str)

    @given(text=full_unicode)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_ml_normalize_never_panics(self, text: str) -> None:
        result = translit.ml_normalize(text)
        assert isinstance(result, str)

    @given(text=full_unicode)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_display_clean_never_panics(self, text: str) -> None:
        result = translit.display_clean(text)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Filename sanitization fuzz
# ---------------------------------------------------------------------------


class TestFilenameFuzz:
    """sanitize_filename() must never panic and must always return safe names."""

    @given(text=full_unicode)
    @settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
    def test_never_panics(self, text: str) -> None:
        result = translit.sanitize_filename(text)
        assert isinstance(result, str)
        # Must not contain path separators
        assert "/" not in result
        assert "\\" not in result
        # Must not exceed max length
        assert len(result.encode("utf-8")) <= 255


# ---------------------------------------------------------------------------
# Grapheme cluster fuzz
# ---------------------------------------------------------------------------


class TestGraphemeFuzz:
    """Grapheme functions must never panic on any Unicode string."""

    @given(text=full_unicode)
    @settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
    def test_grapheme_len_never_panics(self, text: str) -> None:
        n = translit.grapheme_len(text)
        assert isinstance(n, int)
        assert n >= 0

    @given(text=full_unicode)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_grapheme_split_never_panics(self, text: str) -> None:
        parts = translit.grapheme_split(text)
        assert isinstance(parts, list)
        # Rejoin must equal original
        assert "".join(parts) == text

    @given(text=full_unicode, n=st.integers(min_value=0, max_value=100))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_grapheme_truncate_never_panics(self, text: str, n: int) -> None:
        result = translit.grapheme_truncate(text, n)
        assert isinstance(result, str)
        assert translit.grapheme_len(result) <= n
