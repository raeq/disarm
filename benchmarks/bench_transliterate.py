"""Benchmarks for transliteration performance."""

import time


def bench_transliterate_latin():
    """Benchmark: Latin diacritics → ASCII."""
    from disarm import transliterate

    text = "Ça fait déjà longtemps que je n'ai pas mangé de crème brûlée" * 100

    start = time.perf_counter()
    for _ in range(10_000):
        transliterate(text)
    elapsed = time.perf_counter() - start

    chars_per_sec = len(text) * 10_000 / elapsed
    print(f"Latin diacritics: {elapsed:.3f}s, {chars_per_sec:,.0f} chars/sec")


def bench_transliterate_cyrillic():
    """Benchmark: Cyrillic → ASCII."""
    from disarm import transliterate

    text = "Привет мир, это тест транслитерации кириллицы" * 100

    start = time.perf_counter()
    for _ in range(10_000):
        transliterate(text)
    elapsed = time.perf_counter() - start

    chars_per_sec = len(text) * 10_000 / elapsed
    print(f"Cyrillic: {elapsed:.3f}s, {chars_per_sec:,.0f} chars/sec")


def bench_transliterate_ascii_passthrough():
    """Benchmark: Pure ASCII passthrough (best case)."""
    from disarm import transliterate

    text = "The quick brown fox jumps over the lazy dog. " * 100

    start = time.perf_counter()
    for _ in range(10_000):
        transliterate(text)
    elapsed = time.perf_counter() - start

    chars_per_sec = len(text) * 10_000 / elapsed
    print(f"ASCII passthrough: {elapsed:.3f}s, {chars_per_sec:,.0f} chars/sec")


if __name__ == "__main__":
    bench_transliterate_latin()
    bench_transliterate_cyrillic()
    bench_transliterate_ascii_passthrough()
