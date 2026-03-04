"""Benchmarks for slug generation performance."""

import time


def bench_slugify_basic():
    """Benchmark: Basic slug generation."""
    from translit import slugify

    titles = [
        "Hello World, This is a Test!",
        "Ça fait déjà longtemps",
        "München ist eine schöne Stadt",
        "Привет мир",
        "The Quick Brown Fox Jumps Over The Lazy Dog",
    ] * 20

    start = time.perf_counter()
    for _ in range(10_000):
        for title in titles:
            slugify(title)
    elapsed = time.perf_counter() - start

    slugs_per_sec = len(titles) * 10_000 / elapsed
    print(f"Basic slugify: {elapsed:.3f}s, {slugs_per_sec:,.0f} slugs/sec")


def bench_slugify_with_options():
    """Benchmark: Slug generation with all options."""
    from translit import slugify

    text = "The Quick Brown Fox & Friends: A Story! (Part 2)"

    start = time.perf_counter()
    for _ in range(10_000):
        slugify(
            text,
            separator="_",
            max_length=30,
            word_boundary=True,
            stopwords=["the", "a", "and"],
        )
    elapsed = time.perf_counter() - start

    print(f"Slugify with options: {elapsed:.3f}s, {10_000 / elapsed:,.0f} ops/sec")


if __name__ == "__main__":
    bench_slugify_basic()
    bench_slugify_with_options()
