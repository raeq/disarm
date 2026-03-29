"""Property-based tests: batch APIs must produce identical results to single-call APIs.

This is a critical production invariant — users expect batch processing to be a
pure performance optimisation with zero semantic difference from looping over
individual calls.
"""

from __future__ import annotations

import pytest
from conftest import nf_forms, unicode_text
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from translit import (
    normalize,
    normalize_batch,
    slugify,
    slugify_batch,
    strip_accents,
    strip_accents_batch,
    transliterate,
    transliterate_batch,
)

pytestmark = pytest.mark.hypothesis

# ---------------------------------------------------------------------------
# 1. transliterate_batch ↔ transliterate
# ---------------------------------------------------------------------------


class TestTransliterateBatchConsistency:
    """transliterate_batch(xs) == [transliterate(x) for x in xs]."""

    @given(text=unicode_text)
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_single_element(self, text: str) -> None:
        single = transliterate(text)
        batch = transliterate_batch([text])
        assert batch == [single]

    @given(texts=st.lists(unicode_text, min_size=0, max_size=20))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_multi_element(self, texts: list[str]) -> None:
        singles = [transliterate(t) for t in texts]
        batch = transliterate_batch(texts)
        assert batch == singles

    @given(texts=st.lists(unicode_text, min_size=0, max_size=10))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_with_errors_ignore(self, texts: list[str]) -> None:
        singles = [transliterate(t, errors="ignore") for t in texts]
        batch = transliterate_batch(texts, errors="ignore")
        assert batch == singles

    @given(texts=st.lists(unicode_text, min_size=0, max_size=10))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_with_errors_preserve(self, texts: list[str]) -> None:
        singles = [transliterate(t, errors="preserve") for t in texts]
        batch = transliterate_batch(texts, errors="preserve")
        assert batch == singles

    def test_empty_batch(self) -> None:
        assert transliterate_batch([]) == []


# ---------------------------------------------------------------------------
# 2. slugify_batch ↔ slugify
# ---------------------------------------------------------------------------


class TestSlugifyBatchConsistency:
    """slugify_batch(xs) == [slugify(x) for x in xs]."""

    @given(text=unicode_text)
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_single_element(self, text: str) -> None:
        single = slugify(text)
        batch = slugify_batch([text])
        assert batch == [single]

    @given(texts=st.lists(unicode_text, min_size=0, max_size=20))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_multi_element(self, texts: list[str]) -> None:
        singles = [slugify(t) for t in texts]
        batch = slugify_batch(texts)
        assert batch == singles

    @given(texts=st.lists(unicode_text, min_size=0, max_size=10))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_with_separator(self, texts: list[str]) -> None:
        singles = [slugify(t, separator="_") for t in texts]
        batch = slugify_batch(texts, separator="_")
        assert batch == singles

    @given(texts=st.lists(unicode_text, min_size=0, max_size=10))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_with_stopwords(self, texts: list[str]) -> None:
        sw = ("the", "a", "an")
        singles = [slugify(t, stopwords=sw) for t in texts]
        batch = slugify_batch(texts, stopwords=sw)
        assert batch == singles

    @given(texts=st.lists(unicode_text, min_size=0, max_size=10))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_with_max_length(self, texts: list[str]) -> None:
        singles = [slugify(t, max_length=20) for t in texts]
        batch = slugify_batch(texts, max_length=20)
        assert batch == singles

    def test_empty_batch(self) -> None:
        assert slugify_batch([]) == []


# ---------------------------------------------------------------------------
# 3. normalize_batch ↔ normalize
# ---------------------------------------------------------------------------


class TestNormalizeBatchConsistency:
    """normalize_batch(xs, form=F) == [normalize(x, form=F) for x in xs]."""

    @given(text=unicode_text, form=nf_forms)
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_single_element(self, text: str, form: str) -> None:
        single = normalize(text, form=form)
        batch = normalize_batch([text], form=form)
        assert batch == [single]

    @given(texts=st.lists(unicode_text, min_size=0, max_size=20), form=nf_forms)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_multi_element(self, texts: list[str], form: str) -> None:
        singles = [normalize(t, form=form) for t in texts]
        batch = normalize_batch(texts, form=form)
        assert batch == singles

    def test_empty_batch(self) -> None:
        assert normalize_batch([]) == []

    def test_empty_batch_all_forms(self) -> None:
        for form in ("NFC", "NFD", "NFKC", "NFKD"):
            assert normalize_batch([], form=form) == []


# ---------------------------------------------------------------------------
# 4. strip_accents_batch ↔ strip_accents
# ---------------------------------------------------------------------------


class TestStripAccentsBatchConsistency:
    """strip_accents_batch(xs) == [strip_accents(x) for x in xs]."""

    @given(text=unicode_text)
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_single_element(self, text: str) -> None:
        single = strip_accents(text)
        batch = strip_accents_batch([text])
        assert batch == [single]

    @given(texts=st.lists(unicode_text, min_size=0, max_size=20))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_multi_element(self, texts: list[str]) -> None:
        singles = [strip_accents(t) for t in texts]
        batch = strip_accents_batch(texts)
        assert batch == singles

    def test_empty_batch(self) -> None:
        assert strip_accents_batch([]) == []
