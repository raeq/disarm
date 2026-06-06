"""Tests for make_cached_transliterator: caching, option binding, and
self-invalidation when the global tables change."""

from __future__ import annotations

from translit import (
    clear_replacements,
    make_cached_transliterator,
    register_lang,
    register_replacements,
    transliterate,
)


def test_caches_and_matches_transliterate() -> None:
    t = make_cached_transliterator()
    assert t("café") == "cafe"
    assert t("café") == transliterate("café")
    assert t.cache_info().hits >= 1


def test_option_binding() -> None:
    t = make_cached_transliterator(lang="de")
    assert t("Ärger") == transliterate("Ärger", lang="de") == "Aerger"


def test_self_invalidates_on_register_lang() -> None:
    # Leading-underscore code: the dynamic-coverage tests skip test-registered langs.
    t = make_cached_transliterator(lang="_zzcache")
    before = t("ñ")  # '_zzcache' unregistered -> default
    register_lang("_zzcache", {"ñ": "NYE"})
    after = t("ñ")  # must self-invalidate and recompute
    assert before != after
    assert after == transliterate("ñ", lang="_zzcache") == "NYE"


def test_mutation_clears_cache() -> None:
    clear_replacements()
    t = make_cached_transliterator()
    t("a")
    t("b")
    assert t.cache_info().currsize == 2
    register_replacements({"zzz": "qqq"})  # any table change bumps the generation
    t("a")  # next call clears the (now-stale) cache, then caches one entry
    assert t.cache_info().currsize == 1
    clear_replacements()


def test_cache_clear_and_info_exposed() -> None:
    t = make_cached_transliterator()
    t("café")
    assert t.cache_info().currsize == 1
    t.cache_clear()
    assert t.cache_info().currsize == 0


def test_maxsize_is_bounded() -> None:
    t = make_cached_transliterator(maxsize=2)
    for s in ["x", "y", "z"]:
        t(s)
    assert t.cache_info().currsize <= 2
