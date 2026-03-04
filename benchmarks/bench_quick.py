#!/usr/bin/env python3
"""Quick stdlib-only timing benchmarks for translit.

No external dependencies required (uses timeit from stdlib).
For rigorous benchmarks with statistical analysis, use bench_pyperf.py.

Usage:
    python benchmarks/bench_quick.py
"""

from __future__ import annotations

import timeit

import translit

# ---------------------------------------------------------------------------
# Input corpus
# ---------------------------------------------------------------------------

INPUTS = {
    "ascii_short": "hello world",
    "latin_diacritics": "café résumé naïve Ångström",
    "cyrillic": "Москва — столица России",
    "cjk": "北京是中国的首都",
    "mixed": "Hello café мир 日本 résumé Straße",
    "slug_title": "My Blog Post — Ünïcödé Édition! #3",
}


def _bench(label: str, func, *, number: int = 50_000) -> None:
    elapsed = timeit.timeit(func, number=number)
    ops_per_sec = number / elapsed
    ns_per_op = elapsed / number * 1e9
    print(f"  {label:42s}  {ns_per_op:8.1f} ns/op  ({ops_per_sec:12,.0f} ops/s)")


def main() -> None:
    print("=" * 78)
    print("translit quick benchmarks (timeit, 50k iterations)")
    print("=" * 78)

    # -- Transliteration --
    print("\n--- transliterate ---")
    for name, text in INPUTS.items():
        if name == "slug_title":
            continue
        _bench(f"transliterate/{name}", lambda t=text: translit.transliterate(t))

    # ASCII fast path
    _bench(
        "transliterate/ascii_fast_path",
        lambda: translit.transliterate("pure ascii text no accents"),
    )

    # -- Slugify --
    print("\n--- slugify ---")
    _bench("slugify/default", lambda: translit.slugify(INPUTS["slug_title"]))
    _bench(
        "slugify/with_options",
        lambda: translit.slugify(
            INPUTS["slug_title"],
            separator="_",
            max_length=30,
            word_boundary=True,
        ),
    )

    # -- Case folding --
    print("\n--- fold_case ---")
    for name, text in [
        ("ascii", "HELLO WORLD"),
        ("german", "GROSSE STRAßE"),
        ("mixed", "Hello Мир WORLD Straße"),
    ]:
        _bench(f"fold_case/{name}", lambda t=text: translit.fold_case(t))

    # -- fold_case vs str.casefold --
    print("\n--- fold_case vs str.casefold() ---")
    text = "CAFÉ RÉSUMÉ NAÏVE ÅNGSTRÖM"
    _bench("fold_case/translit", lambda: translit.fold_case(text))
    _bench("fold_case/str.casefold()", lambda: text.casefold())

    # -- Precompiled pipelines --
    print("\n--- precompiled pipelines ---")
    _bench("security_clean", lambda: translit.security_clean("Ηello Ꮤorld\u200b"))
    _bench("ml_normalize", lambda: translit.ml_normalize("Café RÉSUMÉ"))
    _bench("display_clean", lambda: translit.display_clean("hello\x00  world\u200b"))

    # -- Grapheme --
    print("\n--- grapheme ---")
    family = "\U0001f469\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466"
    _bench("grapheme_len/emoji", lambda: translit.grapheme_len(f"Hello {family}!"))
    _bench("grapheme_len/ascii", lambda: translit.grapheme_len("hello world"))

    # -- Batch vs loop --
    print("\n--- batch APIs (100 strings) ---")
    batch = [INPUTS["latin_diacritics"]] * 100
    _bench(
        "transliterate_batch/100",
        lambda: translit.transliterate_batch(batch),
        number=5_000,
    )
    _bench(
        "transliterate_loop/100",
        lambda: [translit.transliterate(t) for t in batch],
        number=5_000,
    )

    print("\n" + "=" * 78)
    print("Done. For rigorous benchmarks, use: python benchmarks/bench_pyperf.py")


if __name__ == "__main__":
    main()
