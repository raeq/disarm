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
    slugify,
    strip_accents,
    transliterate,
)

pytestmark = pytest.mark.hypothesis

# ---------------------------------------------------------------------------
# 1. transliterate(list) ↔ transliterate(str)
# ---------------------------------------------------------------------------


class TestTransliterateBatchConsistency:
    """transliterate(xs) == [transliterate(x) for x in xs]."""

    @given(text=unicode_text)
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_single_element(self, text: str) -> None:
        single = transliterate(text)
        batch = transliterate([text])
        assert batch == [single]

    @given(texts=st.lists(unicode_text, min_size=0, max_size=20))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_multi_element(self, texts: list[str]) -> None:
        singles = [transliterate(t) for t in texts]
        batch = transliterate(texts)
        assert batch == singles

    @given(texts=st.lists(unicode_text, min_size=0, max_size=10))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_with_errors_ignore(self, texts: list[str]) -> None:
        singles = [transliterate(t, errors="ignore") for t in texts]
        batch = transliterate(texts, errors="ignore")
        assert batch == singles

    @given(texts=st.lists(unicode_text, min_size=0, max_size=10))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_with_errors_preserve(self, texts: list[str]) -> None:
        singles = [transliterate(t, errors="preserve") for t in texts]
        batch = transliterate(texts, errors="preserve")
        assert batch == singles

    def test_empty_batch(self) -> None:
        assert transliterate([]) == []


# ---------------------------------------------------------------------------
# 2. slugify(list) ↔ slugify(str)
# ---------------------------------------------------------------------------


class TestSlugifyBatchConsistency:
    """slugify(xs) == [slugify(x) for x in xs]."""

    @given(text=unicode_text)
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_single_element(self, text: str) -> None:
        single = slugify(text)
        batch = slugify([text])
        assert batch == [single]

    @given(texts=st.lists(unicode_text, min_size=0, max_size=20))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_multi_element(self, texts: list[str]) -> None:
        singles = [slugify(t) for t in texts]
        batch = slugify(texts)
        assert batch == singles

    @given(texts=st.lists(unicode_text, min_size=0, max_size=10))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_with_separator(self, texts: list[str]) -> None:
        singles = [slugify(t, separator="_") for t in texts]
        batch = slugify(texts, separator="_")
        assert batch == singles

    @given(texts=st.lists(unicode_text, min_size=0, max_size=10))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_with_stopwords(self, texts: list[str]) -> None:
        sw = ("the", "a", "an")
        singles = [slugify(t, stopwords=sw) for t in texts]
        batch = slugify(texts, stopwords=sw)
        assert batch == singles

    @given(texts=st.lists(unicode_text, min_size=0, max_size=10))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_with_max_length(self, texts: list[str]) -> None:
        singles = [slugify(t, max_length=20) for t in texts]
        batch = slugify(texts, max_length=20)
        assert batch == singles

    def test_empty_batch(self) -> None:
        assert slugify([]) == []


# ---------------------------------------------------------------------------
# 3. normalize(list) ↔ normalize(str)
# ---------------------------------------------------------------------------


class TestNormalizeBatchConsistency:
    """normalize(xs, form=F) == [normalize(x, form=F) for x in xs]."""

    @given(text=unicode_text, form=nf_forms)
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_single_element(self, text: str, form: str) -> None:
        single = normalize(text, form=form)
        batch = normalize([text], form=form)
        assert batch == [single]

    @given(texts=st.lists(unicode_text, min_size=0, max_size=20), form=nf_forms)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_multi_element(self, texts: list[str], form: str) -> None:
        singles = [normalize(t, form=form) for t in texts]
        batch = normalize(texts, form=form)
        assert batch == singles

    def test_empty_batch(self) -> None:
        assert normalize([]) == []

    def test_empty_batch_all_forms(self) -> None:
        for form in ("NFC", "NFD", "NFKC", "NFKD"):
            assert normalize([], form=form) == []


# ---------------------------------------------------------------------------
# 4. strip_accents(list) ↔ strip_accents(str)
# ---------------------------------------------------------------------------


class TestStripAccentsBatchConsistency:
    """strip_accents(xs) == [strip_accents(x) for x in xs]."""

    @given(text=unicode_text)
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_single_element(self, text: str) -> None:
        single = strip_accents(text)
        batch = strip_accents([text])
        assert batch == [single]

    @given(texts=st.lists(unicode_text, min_size=0, max_size=20))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_multi_element(self, texts: list[str]) -> None:
        singles = [strip_accents(t) for t in texts]
        batch = strip_accents(texts)
        assert batch == singles

    def test_empty_batch(self) -> None:
        assert strip_accents([]) == []


class TestChunkBoundary:
    """#239: batch APIs extract/process in chunks of 64. Inputs spanning many
    chunks (and the exact boundary) must still equal the single-call results,
    and a non-str item must raise the same TypeError (just after some compute)."""

    @pytest.mark.parametrize("n", [1, 63, 64, 65, 128, 200])
    def test_transliterate_across_chunks(self, n: int) -> None:
        texts = [f"café {i} Москва 北京 Seoul 서울" for i in range(n)]
        assert transliterate(texts) == [transliterate(t) for t in texts]

    @pytest.mark.parametrize("n", [1, 64, 65, 200])
    def test_slugify_across_chunks(self, n: int) -> None:
        texts = [f"Héllo World {i} Москва" for i in range(n)]
        assert slugify(texts) == [slugify(t) for t in texts]

    def test_non_str_item_raises_typeerror(self) -> None:
        # A non-str item still raises TypeError (the all-or-raise contract holds;
        # only the timing — after some compute — changed).
        with pytest.raises(TypeError):
            transliterate(["ok"] * 70 + [123] + ["ok"])
        with pytest.raises(TypeError):
            slugify(["ok"] * 70 + [None] + ["ok"])
