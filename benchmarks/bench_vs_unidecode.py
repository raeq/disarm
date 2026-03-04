"""Head-to-head benchmark: translit vs Unidecode / text-unidecode / anyascii.

Run after installing comparison libraries:
    pip install Unidecode text-unidecode anyascii
"""

import time
import sys


def bench_library(name: str, func, text: str, iterations: int = 10_000) -> float:
    """Benchmark a transliteration function."""
    start = time.perf_counter()
    for _ in range(iterations):
        func(text)
    elapsed = time.perf_counter() - start
    chars_per_sec = len(text) * iterations / elapsed
    print(f"  {name:20s}: {elapsed:.3f}s ({chars_per_sec:>12,.0f} chars/sec)")
    return elapsed


def main():
    text_latin = "Ça fait déjà longtemps que je n'ai pas mangé de crème brûlée" * 50
    text_cyrillic = "Привет мир, это тест транслитерации кириллицы" * 50
    text_mixed = "Hello café мир 日本 résumé Straße" * 50

    libraries = {}

    # translit (this library)
    try:
        from translit import transliterate

        libraries["translit"] = transliterate
    except ImportError:
        print("translit not installed, skipping")

    # Unidecode
    try:
        from unidecode import unidecode

        libraries["Unidecode"] = unidecode
    except ImportError:
        print("Unidecode not installed, skipping")

    # text-unidecode
    try:
        from text_unidecode import unidecode as text_unidecode

        libraries["text-unidecode"] = text_unidecode
    except ImportError:
        print("text-unidecode not installed, skipping")

    # anyascii
    try:
        from anyascii import anyascii

        libraries["anyascii"] = anyascii
    except ImportError:
        print("anyascii not installed, skipping")

    if not libraries:
        print("No libraries to benchmark!")
        sys.exit(1)

    for label, text in [
        ("Latin diacritics", text_latin),
        ("Cyrillic", text_cyrillic),
        ("Mixed scripts", text_mixed),
    ]:
        print(f"\n{label} ({len(text)} chars):")
        for name, func in libraries.items():
            bench_library(name, func, text)


if __name__ == "__main__":
    main()
