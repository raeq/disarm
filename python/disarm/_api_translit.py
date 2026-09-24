"""Transliteration helpers: `find_untranslatable`, the keyword builder `slugify` uses,
the reverse-transliteration languages, and the language and script profiles.

`transliterate` and `slugify` themselves stay in `disarm._api`, with their `@overload`
stubs, because `typing` records overloads under the module that defines them."""

from __future__ import annotations

from collections.abc import Iterable

from disarm._api_common import _checked_i64_max
from disarm._boundary import (
    _find_untranslatable,
    _list_langs,
    _reverse_langs,
)
from disarm._enums import (
    LANG_META,
    SCRIPT_META,
    LangMeta,
    Script,
    ScriptMeta,
)


def find_untranslatable(
    text: str,
    *,
    lang: str | None = None,
    strict_iso9: bool = False,
    gost7034: bool = False,
    tones: bool = False,
) -> list[tuple[str, int]]:
    """Find every character in *text* that has no transliteration (#184).

    Returns a list of ``(character, byte_offset)`` pairs, in order of
    appearance — the exact set that `transliterate` would replace, drop,
    or preserve (and that ``errors="strict"`` raises on the first of). Pure-ASCII
    input, or input that fully transliterates, returns an empty list.

    Global `register_replacements` are applied first (so a replaced
    character is not reported), so the offsets are relative to the
    post-replacement text.

    Args:
        text: Input Unicode string.
        lang: Language code (same meaning as in `transliterate`).
        strict_iso9: Use the scholarly ASCII Cyrillic table.
        gost7034: Use GOST R 7.0.34 transliteration.
        tones: Consider toned-pinyin coverage for CJK characters.

    Returns:
        List of ``(char, byte_offset)`` for each untranslatable character. The
        character is the one *text* holds at that offset: a base followed by
        combining marks is judged as the character they compose to, and reported
        as the base, as written (#1040).

    Examples:
        >>> find_untranslatable("cafe")
        []
        >>> find_untranslatable("a\U0001f600b")  # emoji has no transliteration
        [('😀', 1)]
    """
    if not isinstance(text, str):
        raise TypeError(f"find_untranslatable() expects str, got {type(text).__name__}")
    return _find_untranslatable(
        text, lang=lang, strict_iso9=strict_iso9, gost7034=gost7034, tones=tones
    )


def _build_slug_kwargs(
    *,
    separator: str,
    lowercase: bool,
    max_length: int,
    word_boundary: bool,
    save_order: bool,
    stopwords: Iterable[str],
    regex_pattern: str | None,
    replacements: Iterable[tuple[str, str]],
    allow_unicode: bool,
    lang: str | None,
    entities: bool,
    decimal: bool,
    hexadecimal: bool,
) -> dict[str, object]:
    """Build the shared kwargs dict forwarded to _slugify/_slugify_batch.

    Mirrors _check_transliterate_conflicts for the slug path: a single
    canonical kwargs dict eliminates the 2-way duplication in slugify().
    (#120)
    """
    return dict(
        separator=separator,
        lowercase=lowercase,
        # #255: reject a max_length too large for the i64 boundary here (the one
        # bound the core can't see); negatives are still validated in the core.
        max_length=_checked_i64_max(max_length, "max_length"),
        word_boundary=word_boundary,
        save_order=save_order,
        stopwords=stopwords,
        regex_pattern=regex_pattern,
        replacements=replacements,
        allow_unicode=allow_unicode,
        lang=lang,
        entities=entities,
        decimal=decimal,
        hexadecimal=hexadecimal,
    )


# --- Reverse transliteration ---


def reverse_langs() -> list[str]:
    """Return language codes that support reverse transliteration.

    Returns:
        List of language code strings (e.g., ``["el", "ru", "uk"]``).

    Examples:
        >>> "ru" in reverse_langs()
        True
    """
    return _reverse_langs()


# --- Language profiles ---


def list_langs() -> list[str]:
    """Return available language codes for transliteration.

    Returns:
        Sorted list of language code strings (e.g. ["ar", "bg", "de", ...]).

    Raises:
        DisarmError: If the language table lock is poisoned.

    Examples:
        >>> "de" in list_langs()
        True
        >>> "ja" in list_langs()
        True
    """
    return _list_langs()


def list_scripts() -> list[str]:
    """Return recognized Unicode script names.

    Returns:
        Sorted list of script name strings matching Script enum values
        (e.g. ["Arabic", "Armenian", "Bengali", ...]).

    Examples:
        >>> "Latin" in list_scripts()
        True
        >>> "Han" in list_scripts()
        True
    """
    return sorted(s.value for s in Script)


def list_context_langs() -> list[str]:
    """Return language codes that support context-aware transliteration.

    These languages benefit from ``context=True`` in `transliterate`.
    Each entry has a ``context`` field in its `lang_info` metadata
    indicating the level of support: ``"full"`` or ``"partial"``.

    Returns:
        Sorted list of language codes (e.g. ``["ar", "fa", "he"]``).

    Examples:
        >>> "ar" in list_context_langs()
        True
        >>> "de" in list_context_langs()
        False
    """
    return sorted(code for code, meta in LANG_META.items() if meta["context"] != "none")


def lang_info(code: str) -> LangMeta:
    """Return metadata for a language code.

    Args:
        code: Language code (e.g. ``"de"``, ``"cop"``, ``"ban"``).

    Returns:
        A `LangMeta` dict with ``name``, ``script``, ``region``, and
        ``context`` keys (``context`` is ``"full"``, ``"partial"``, or
        ``"none"``).

    Raises:
        KeyError: If the code is not a recognized language.

    Examples:
        >>> lang_info("de")["name"]
        'German'
        >>> lang_info("cop")["script"]
        'Coptic'
    """
    return LANG_META[code]


def script_info(script: str | Script) -> ScriptMeta:
    """Return metadata for a Unicode script.

    Args:
        script: Script name (e.g. ``"Coptic"``) or `Script` enum value.

    Returns:
        A `ScriptMeta` dict with ``name``, ``default_lang``, ``example``,
        and ``context_aware`` keys.

    Raises:
        KeyError: If the script is not recognized.

    Examples:
        >>> script_info("Coptic")["default_lang"]
        'cop'
        >>> script_info(Script.THAI)["name"]
        'Thai'
    """
    key = script.value if isinstance(script, Script) else script
    return SCRIPT_META[key]
