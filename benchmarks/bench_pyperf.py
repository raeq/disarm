#!/usr/bin/env python3
"""Comprehensive pyperf benchmarks for translit vs competitor libraries.

Usage
-----
    # Full suite (rigorous, ~15 min):
    python benchmarks/bench_pyperf.py -o results.json

    # Quick sanity-check (fast, lower confidence):
    python benchmarks/bench_pyperf.py --fast -o results.json

    # View results:
    python -m pyperf stats results.json

    # Compare two runs:
    python -m pyperf compare_to baseline.json improved.json

Dependencies
------------
    pip install pyperf Unidecode text-unidecode anyascii python-slugify pathvalidate
"""

from __future__ import annotations

import pyperf


# ---------------------------------------------------------------------------
# Input corpora
# ---------------------------------------------------------------------------

# Latin diacritics — French text, representative of European languages
LATIN_SHORT = "Ünïcödé téxt — café résumé naïve Ångström"  # 42 chars
LATIN_LONG = (
    "Ça fait déjà longtemps que je n'ai pas mangé de crème brûlée. "
    "Les élèves préfèrent étudier à la bibliothèque où il y a "
    "beaucoup de références académiques."
) * 10  # ~1.7 KB

# Cyrillic — Russian text
CYRILLIC_SHORT = "Привет мир, это тест транслитерации кириллицы"  # 45 chars
CYRILLIC_LONG = (
    "Привет мир, это тест транслитерации кириллицы. "
    "Быстрая коричневая лиса перепрыгнула через ленивую собаку. "
    "Москва — столица Российской Федерации."
) * 10  # ~1.5 KB

# CJK — Chinese text (Mandarin)
CJK_SHORT = "北京市朝阳区建国门外大街"  # 12 chars
CJK_LONG = (
    "北京市朝阳区建国门外大街一号国贸大厦三期。"
    "上海浦东新区陆家嘴金融贸易区银城中路。"
    "深圳市南山区科技园科苑路。"
) * 10  # ~0.8 KB

# Mixed scripts — realistic web content
MIXED = "Hello café мир 日本 résumé Straße 东京 naïve Zürich"  # 50 chars

# Slug input — typical blog/CMS title
SLUG_INPUT = "My Blog Post — Ünïcödé Édition! #3 🚀 café & résumé"
SLUG_LONG = (
    "Breaking News: Ünïcödé Söftware Cömpany Ànnóunces "
    "Révölutionary Prödüct für 2024 — «Ça change tout» "
    "says CEO Müller-Straße at the 日本 tech summit"
)

# Filename sanitization inputs
FILENAME_SIMPLE = "my<file>:name?.txt"
FILENAME_UNICODE = "café — résumé (final version) [2024].docx"
FILENAME_ADVERSARIAL = "../../etc/passwd\x00.txt"

# Normalization inputs
NORM_INPUT = "café résumé naïve"
NORM_LONG = "Ça fait déjà longtemps" * 20


# ---------------------------------------------------------------------------
# Benchmark definitions
# ---------------------------------------------------------------------------


def add_transliteration_benchmarks(runner: pyperf.Runner) -> None:
    """Transliteration: translit vs Unidecode, text-unidecode, anyascii."""

    # -- translit --
    runner.timeit(
        "translit:translit:latin_short",
        "transliterate(text)",
        globals={
            "transliterate": __import__("translit").transliterate,
            "text": LATIN_SHORT,
        },
    )
    runner.timeit(
        "translit:translit:latin_long",
        "transliterate(text)",
        globals={
            "transliterate": __import__("translit").transliterate,
            "text": LATIN_LONG,
        },
    )
    runner.timeit(
        "translit:translit:cyrillic_short",
        "transliterate(text)",
        globals={
            "transliterate": __import__("translit").transliterate,
            "text": CYRILLIC_SHORT,
        },
    )
    runner.timeit(
        "translit:translit:cyrillic_long",
        "transliterate(text)",
        globals={
            "transliterate": __import__("translit").transliterate,
            "text": CYRILLIC_LONG,
        },
    )
    runner.timeit(
        "translit:translit:cjk_short",
        "transliterate(text)",
        globals={
            "transliterate": __import__("translit").transliterate,
            "text": CJK_SHORT,
        },
    )
    runner.timeit(
        "translit:translit:cjk_long",
        "transliterate(text)",
        globals={
            "transliterate": __import__("translit").transliterate,
            "text": CJK_LONG,
        },
    )
    runner.timeit(
        "translit:translit:mixed",
        "transliterate(text)",
        globals={"transliterate": __import__("translit").transliterate, "text": MIXED},
    )

    # -- Unidecode --
    runner.timeit(
        "translit:Unidecode:latin_short",
        "unidecode(text)",
        globals={"unidecode": __import__("unidecode").unidecode, "text": LATIN_SHORT},
    )
    runner.timeit(
        "translit:Unidecode:latin_long",
        "unidecode(text)",
        globals={"unidecode": __import__("unidecode").unidecode, "text": LATIN_LONG},
    )
    runner.timeit(
        "translit:Unidecode:cyrillic_short",
        "unidecode(text)",
        globals={
            "unidecode": __import__("unidecode").unidecode,
            "text": CYRILLIC_SHORT,
        },
    )
    runner.timeit(
        "translit:Unidecode:cyrillic_long",
        "unidecode(text)",
        globals={"unidecode": __import__("unidecode").unidecode, "text": CYRILLIC_LONG},
    )
    runner.timeit(
        "translit:Unidecode:cjk_short",
        "unidecode(text)",
        globals={"unidecode": __import__("unidecode").unidecode, "text": CJK_SHORT},
    )
    runner.timeit(
        "translit:Unidecode:cjk_long",
        "unidecode(text)",
        globals={"unidecode": __import__("unidecode").unidecode, "text": CJK_LONG},
    )
    runner.timeit(
        "translit:Unidecode:mixed",
        "unidecode(text)",
        globals={"unidecode": __import__("unidecode").unidecode, "text": MIXED},
    )

    # -- text-unidecode --
    runner.timeit(
        "translit:text_unidecode:latin_short",
        "unidecode(text)",
        globals={
            "unidecode": __import__("text_unidecode").unidecode,
            "text": LATIN_SHORT,
        },
    )
    runner.timeit(
        "translit:text_unidecode:latin_long",
        "unidecode(text)",
        globals={
            "unidecode": __import__("text_unidecode").unidecode,
            "text": LATIN_LONG,
        },
    )
    runner.timeit(
        "translit:text_unidecode:cyrillic_short",
        "unidecode(text)",
        globals={
            "unidecode": __import__("text_unidecode").unidecode,
            "text": CYRILLIC_SHORT,
        },
    )
    runner.timeit(
        "translit:text_unidecode:cyrillic_long",
        "unidecode(text)",
        globals={
            "unidecode": __import__("text_unidecode").unidecode,
            "text": CYRILLIC_LONG,
        },
    )
    runner.timeit(
        "translit:text_unidecode:cjk_short",
        "unidecode(text)",
        globals={
            "unidecode": __import__("text_unidecode").unidecode,
            "text": CJK_SHORT,
        },
    )
    runner.timeit(
        "translit:text_unidecode:cjk_long",
        "unidecode(text)",
        globals={"unidecode": __import__("text_unidecode").unidecode, "text": CJK_LONG},
    )
    runner.timeit(
        "translit:text_unidecode:mixed",
        "unidecode(text)",
        globals={"unidecode": __import__("text_unidecode").unidecode, "text": MIXED},
    )

    # -- anyascii --
    runner.timeit(
        "translit:anyascii:latin_short",
        "anyascii(text)",
        globals={"anyascii": __import__("anyascii").anyascii, "text": LATIN_SHORT},
    )
    runner.timeit(
        "translit:anyascii:latin_long",
        "anyascii(text)",
        globals={"anyascii": __import__("anyascii").anyascii, "text": LATIN_LONG},
    )
    runner.timeit(
        "translit:anyascii:cyrillic_short",
        "anyascii(text)",
        globals={"anyascii": __import__("anyascii").anyascii, "text": CYRILLIC_SHORT},
    )
    runner.timeit(
        "translit:anyascii:cyrillic_long",
        "anyascii(text)",
        globals={"anyascii": __import__("anyascii").anyascii, "text": CYRILLIC_LONG},
    )
    runner.timeit(
        "translit:anyascii:cjk_short",
        "anyascii(text)",
        globals={"anyascii": __import__("anyascii").anyascii, "text": CJK_SHORT},
    )
    runner.timeit(
        "translit:anyascii:cjk_long",
        "anyascii(text)",
        globals={"anyascii": __import__("anyascii").anyascii, "text": CJK_LONG},
    )
    runner.timeit(
        "translit:anyascii:mixed",
        "anyascii(text)",
        globals={"anyascii": __import__("anyascii").anyascii, "text": MIXED},
    )


def add_slugify_benchmarks(runner: pyperf.Runner) -> None:
    """Slugification: translit vs python-slugify."""

    # -- translit --
    runner.timeit(
        "slugify:translit:short",
        "slugify(text)",
        globals={"slugify": __import__("translit").slugify, "text": SLUG_INPUT},
    )
    runner.timeit(
        "slugify:translit:long",
        "slugify(text)",
        globals={"slugify": __import__("translit").slugify, "text": SLUG_LONG},
    )
    runner.timeit(
        "slugify:translit:options",
        "slugify(text, separator='_', max_length=30, stopwords=['the', 'a', 'and'])",
        globals={"slugify": __import__("translit").slugify, "text": SLUG_LONG},
    )

    # -- python-slugify --
    from slugify import slugify as py_slugify

    runner.timeit(
        "slugify:python_slugify:short",
        "slugify(text)",
        globals={"slugify": py_slugify, "text": SLUG_INPUT},
    )
    runner.timeit(
        "slugify:python_slugify:long",
        "slugify(text)",
        globals={"slugify": py_slugify, "text": SLUG_LONG},
    )
    runner.timeit(
        "slugify:python_slugify:options",
        "slugify(text, separator='_', max_length=30, stopwords=['the', 'a', 'and'])",
        globals={"slugify": py_slugify, "text": SLUG_LONG},
    )


def add_normalize_benchmarks(runner: pyperf.Runner) -> None:
    """Normalization: translit vs unicodedata (stdlib C extension)."""
    import unicodedata

    runner.timeit(
        "normalize:translit:nfc_short",
        "normalize(text, form='NFC')",
        globals={"normalize": __import__("translit").normalize, "text": NORM_INPUT},
    )
    runner.timeit(
        "normalize:translit:nfc_long",
        "normalize(text, form='NFC')",
        globals={"normalize": __import__("translit").normalize, "text": NORM_LONG},
    )
    runner.timeit(
        "normalize:translit:nfkc_short",
        "normalize(text, form='NFKC')",
        globals={"normalize": __import__("translit").normalize, "text": NORM_INPUT},
    )

    runner.timeit(
        "normalize:unicodedata:nfc_short",
        "normalize('NFC', text)",
        globals={"normalize": unicodedata.normalize, "text": NORM_INPUT},
    )
    runner.timeit(
        "normalize:unicodedata:nfc_long",
        "normalize('NFC', text)",
        globals={"normalize": unicodedata.normalize, "text": NORM_LONG},
    )
    runner.timeit(
        "normalize:unicodedata:nfkc_short",
        "normalize('NFKC', text)",
        globals={"normalize": unicodedata.normalize, "text": NORM_INPUT},
    )


def add_filename_benchmarks(runner: pyperf.Runner) -> None:
    """Filename sanitization: translit vs pathvalidate."""
    from pathvalidate import sanitize_filename as pv_sanitize

    runner.timeit(
        "filename:translit:simple",
        "sanitize(text, platform='universal')",
        globals={
            "sanitize": __import__("translit").sanitize_filename,
            "text": FILENAME_SIMPLE,
        },
    )
    runner.timeit(
        "filename:translit:unicode",
        "sanitize(text, platform='universal')",
        globals={
            "sanitize": __import__("translit").sanitize_filename,
            "text": FILENAME_UNICODE,
        },
    )
    runner.timeit(
        "filename:translit:adversarial",
        "sanitize(text, platform='universal')",
        globals={
            "sanitize": __import__("translit").sanitize_filename,
            "text": FILENAME_ADVERSARIAL,
        },
    )

    runner.timeit(
        "filename:pathvalidate:simple",
        "sanitize(text)",
        globals={"sanitize": pv_sanitize, "text": FILENAME_SIMPLE},
    )
    runner.timeit(
        "filename:pathvalidate:unicode",
        "sanitize(text)",
        globals={"sanitize": pv_sanitize, "text": FILENAME_UNICODE},
    )
    runner.timeit(
        "filename:pathvalidate:adversarial",
        "sanitize(text)",
        globals={"sanitize": pv_sanitize, "text": FILENAME_ADVERSARIAL},
    )


def add_strip_accents_benchmarks(runner: pyperf.Runner) -> None:
    """Accent stripping: translit (Rust) vs unicodedata-based Python approach."""

    # Common pure-Python accent stripping implementation
    setup = (
        "import unicodedata\n"
        "def py_strip(text):\n"
        "    nfkd = unicodedata.normalize('NFD', text)\n"
        "    return ''.join(c for c in nfkd if unicodedata.category(c) != 'Mn')\n"
    )

    runner.timeit(
        "strip_accents:translit:short",
        "strip_accents(text)",
        globals={
            "strip_accents": __import__("translit").strip_accents,
            "text": LATIN_SHORT,
        },
    )
    runner.timeit(
        "strip_accents:translit:long",
        "strip_accents(text)",
        globals={
            "strip_accents": __import__("translit").strip_accents,
            "text": LATIN_LONG,
        },
    )

    runner.timeit(
        "strip_accents:python_nfkd:short",
        "py_strip(text)",
        setup=setup,
        globals={"text": LATIN_SHORT},
    )
    runner.timeit(
        "strip_accents:python_nfkd:long",
        "py_strip(text)",
        setup=setup,
        globals={"text": LATIN_LONG},
    )


def add_batch_benchmarks(runner: pyperf.Runner) -> None:
    """Batch APIs: single-call vs loop-of-calls for N strings."""
    import translit

    # Build a realistic batch: 100 mixed Latin/Cyrillic strings
    batch_100 = [LATIN_SHORT, CYRILLIC_SHORT, CJK_SHORT, MIXED] * 25

    # --- transliterate_batch vs loop ---
    runner.timeit(
        "batch:transliterate_batch:100",
        "transliterate_batch(texts)",
        globals={
            "transliterate_batch": translit.transliterate_batch,
            "texts": batch_100,
        },
    )
    runner.timeit(
        "batch:transliterate_loop:100",
        "[transliterate(t) for t in texts]",
        globals={"transliterate": translit.transliterate, "texts": batch_100},
    )

    # --- slugify_batch vs loop ---
    runner.timeit(
        "batch:slugify_batch:100",
        "slugify_batch(texts)",
        globals={"slugify_batch": translit.slugify_batch, "texts": batch_100},
    )
    runner.timeit(
        "batch:slugify_loop:100",
        "[slugify(t) for t in texts]",
        globals={"slugify": translit.slugify, "texts": batch_100},
    )

    # --- Unidecode loop baseline for comparison ---
    runner.timeit(
        "batch:Unidecode_loop:100",
        "[unidecode(t) for t in texts]",
        globals={"unidecode": __import__("unidecode").unidecode, "texts": batch_100},
    )


def add_fold_case_benchmarks(runner: pyperf.Runner) -> None:
    """Case folding: translit vs str.casefold()."""

    runner.timeit(
        "fold_case:translit:short",
        "fold_case(text)",
        globals={"fold_case": __import__("translit").fold_case, "text": LATIN_SHORT},
    )
    runner.timeit(
        "fold_case:translit:long",
        "fold_case(text)",
        globals={"fold_case": __import__("translit").fold_case, "text": LATIN_LONG},
    )

    runner.timeit(
        "fold_case:str_casefold:short",
        "text.casefold()",
        globals={"text": LATIN_SHORT},
    )
    runner.timeit(
        "fold_case:str_casefold:long",
        "text.casefold()",
        globals={"text": LATIN_LONG},
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    runner = pyperf.Runner()

    add_transliteration_benchmarks(runner)
    add_slugify_benchmarks(runner)
    add_normalize_benchmarks(runner)
    add_filename_benchmarks(runner)
    add_strip_accents_benchmarks(runner)
    add_fold_case_benchmarks(runner)
    add_batch_benchmarks(runner)


if __name__ == "__main__":
    main()
