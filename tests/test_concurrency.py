"""Concurrent access tests for global caches (LANG_TABLES, HANGUL_CACHE).

These tests exercise the RwLock-protected global state from multiple threads
to detect data races, deadlocks, or cache inconsistencies that single-threaded
tests cannot reveal.
"""

from __future__ import annotations

import threading

import disarm


def _transliterate_many(lang: str | None, texts: list[str], results: list[str]) -> None:
    for text in texts:
        results.append(disarm.transliterate(text, lang=lang))


def _register_and_lookup(code: str, mapping: dict[str, str], char: str, out: list[str]) -> None:
    disarm.register_lang(code, mapping)
    result = disarm.transliterate(char, lang=code)
    out.append(result)


class TestConcurrentTransliteration:
    """Multiple threads reading the default cache simultaneously."""

    def test_concurrent_default_transliteration(self) -> None:
        texts = ["北京", "서울", "東京", "Москва", "café"]
        all_results: list[list[str]] = [[] for _ in range(8)]
        threads = [
            threading.Thread(target=_transliterate_many, args=(None, texts, all_results[i]))
            for i in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should produce identical results
        assert all(r == all_results[0] for r in all_results), "Inconsistent results across threads"
        # Each thread should have processed all texts
        assert all(len(r) == len(texts) for r in all_results)

    def test_concurrent_hangul_cache_population(self) -> None:
        """Multiple threads hitting Hangul romanization simultaneously.

        The Hangul cache is populated lazily on first access per syllable.
        Concurrent population must not produce duplicate leaks or inconsistent
        results.
        """
        hangul_texts = ["한국어", "서울특별시", "가나다라마바사"]
        results: list[list[str]] = [[] for _ in range(16)]
        threads = [
            threading.Thread(target=_transliterate_many, args=(None, hangul_texts, results[i]))
            for i in range(16)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r == results[0] for r in results), (
            "Hangul cache produced inconsistent results under concurrency"
        )


class TestConcurrentLangRegistration:
    """Concurrent registration and lookup of user language tables."""

    def test_register_and_lookup_concurrent(self) -> None:
        """Register a custom lang table from multiple threads, then read it."""
        results: list[list[str]] = [[] for _ in range(4)]
        mapping = {"Ü": "Ue", "Ö": "Oe", "Ä": "Ae"}

        threads = [
            threading.Thread(
                target=_register_and_lookup,
                args=(f"_conc_test_{i}", mapping, "Ü", results[i]),
            )
            for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each thread registered its own lang code, so each result should be "Ue"
        assert all(r == ["Ue"] for r in results), (
            f"Unexpected results under concurrent registration: {results}"
        )

    def test_concurrent_read_during_write(self) -> None:
        """Readers should not block indefinitely while a writer registers."""
        read_results: list[str] = []
        write_done = threading.Event()

        def reader() -> None:
            # Keep reading until the writer finishes
            for _ in range(100):
                read_results.append(disarm.transliterate("café"))
            write_done.wait(timeout=5.0)

        def writer() -> None:
            disarm.register_lang("_conc_writer_test", {"ß": "ss"})
            write_done.set()

        t_reader = threading.Thread(target=reader)
        t_writer = threading.Thread(target=writer)
        t_reader.start()
        t_writer.start()
        t_reader.join(timeout=10.0)
        t_writer.join(timeout=10.0)

        assert not t_reader.is_alive(), "Reader thread deadlocked"
        assert not t_writer.is_alive(), "Writer thread deadlocked"
        assert len(read_results) == 100


class TestMalformedUnicodeInput:
    """Transliteration with edge-case Unicode inputs."""

    def test_empty_string(self) -> None:
        assert disarm.transliterate("") == ""

    def test_lone_combining_mark(self) -> None:
        # Combining acute accent without a base character
        result = disarm.transliterate("\u0301")
        assert isinstance(result, str)

    def test_zero_width_characters(self) -> None:
        # Zero-width non-joiner, zero-width joiner, zero-width space
        for zwc in ["\u200c", "\u200d", "\u200b"]:
            result = disarm.transliterate(zwc)
            assert isinstance(result, str)

    def test_bidi_override_characters(self) -> None:
        # Right-to-left override, left-to-right override
        for bidi in ["\u202e", "\u202d"]:
            result = disarm.transliterate(bidi)
            assert isinstance(result, str)

    def test_null_character(self) -> None:
        result = disarm.transliterate("a\x00b")
        assert isinstance(result, str)

    def test_private_use_area(self) -> None:
        # Private Use Area codepoints have no defined transliteration
        result = disarm.transliterate("\ue000\uf8ff", errors="ignore")
        assert isinstance(result, str)

    def test_surrogate_range_as_replacement(self) -> None:
        # Python str cannot contain lone surrogates; test near-surrogate edge
        near_surrogate = "\ud7ff"  # just below surrogate range
        result = disarm.transliterate(near_surrogate, errors="replace")
        assert isinstance(result, str)

    def test_noncharacters(self) -> None:
        # Unicode noncharacters (U+FFFE, U+FFFF)
        for nc in ["\ufffe", "\uffff"]:
            result = disarm.transliterate(nc, errors="preserve")
            assert isinstance(result, str)

    def test_high_plane_cjk_extension_b(self) -> None:
        # CJK Extension B (U+20000) — not in default tables, should use error mode
        ch = "\U00020000"
        result = disarm.transliterate(ch, errors="ignore")
        assert result == ""
        result_preserve = disarm.transliterate(ch, errors="preserve")
        assert result_preserve == ch

    def test_very_long_cjk_string(self) -> None:
        # Stress the CJK capacity estimation path
        long_cjk = "北京" * 500
        result = disarm.transliterate(long_cjk)
        assert "bei" in result
        assert "jing" in result

    def test_mixed_scripts_all_at_once(self) -> None:
        # Latin + Cyrillic + CJK + Hangul + Arabic in one string
        mixed = "Hello Москва 北京 서울 مرحبا"
        result = disarm.transliterate(mixed)
        assert isinstance(result, str)
        assert result.isascii() or any(c.isalpha() for c in result)


# ---------------------------------------------------------------------------
# GIL release: batch APIs run their Rust compute with the GIL released (#70)
# ---------------------------------------------------------------------------

import os  # noqa: E402
import time  # noqa: E402

import pytest  # noqa: E402

from disarm import normalize, slugify, transliterate  # noqa: E402

# A batch big enough that the Rust compute dominates thread/setup overhead.
_BIG = ["Москва Αθήνα 北京 café résumé" * 20] * 40_000


def _best_of(fn, rounds: int = 5) -> float:
    best = float("inf")
    for _ in range(rounds):
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return best


def _concurrent(fn, threads: int, rounds: int = 5) -> float:
    best = float("inf")
    for _ in range(rounds):
        workers = [threading.Thread(target=fn) for _ in range(threads)]
        start = time.perf_counter()
        for w in workers:
            w.start()
        for w in workers:
            w.join()
        best = min(best, time.perf_counter() - start)
    return best


class TestBatchGilReleaseParity:
    """The GIL release must not change batch results."""

    def test_transliterate_batch_parity(self) -> None:
        data = ["北京", "café", "Москва", "naïve", "ψυχή"] * 50
        assert transliterate(data) == [transliterate(x) for x in data]

    def test_normalize_batch_parity(self) -> None:
        data = ["é", "ño", "café"] * 50
        assert normalize(data, form="NFKC") == [normalize(x, form="NFKC") for x in data]

    def test_slugify_batch_parity(self) -> None:
        data = ["Crème Brûlée", "Москва!", "北京 city"] * 50
        assert slugify(data) == [slugify(x) for x in data]


@pytest.mark.skipif(
    (os.cpu_count() or 1) < 2,
    reason="parallel speedup needs at least 2 cores",
)
class TestBatchReleasesGil:
    """Two threads must finish a pair of batches faster than serial (#70).

    With the GIL held the whole call, concurrent ≈ serial (~1.0x). With it
    released, concurrent approaches single-batch time (~2x). The 1.3x threshold
    sits comfortably above the no-release baseline while tolerating CI noise
    (best-of-N minimises scheduler jitter).
    """

    def _assert_parallel(self, fn) -> None:
        serial = 2 * _best_of(fn)
        concurrent = _concurrent(fn, threads=2)
        speedup = serial / concurrent
        assert speedup > 1.3, (
            f"no parallelism: serial~{serial:.3f}s vs concurrent {concurrent:.3f}s "
            f"(speedup {speedup:.2f}x); GIL may not be released"
        )

    def test_transliterate_releases_gil(self) -> None:
        self._assert_parallel(lambda: transliterate(_BIG))

    def test_slugify_releases_gil(self) -> None:
        self._assert_parallel(lambda: slugify(_BIG))
