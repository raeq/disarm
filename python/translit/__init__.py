"""translit: Fast Unicode transliteration, slugification, and text normalization."""

from __future__ import annotations

import sys as _sys
import types as _stdlib_types
import warnings as _warnings
from collections.abc import Iterable
from functools import lru_cache, wraps
from typing import Any, Protocol, cast, overload

from translit._enums import (
    LANG_AM,
    LANG_AR,
    LANG_AS,
    LANG_BAN,
    LANG_BAX,
    LANG_BG,
    LANG_BN,
    LANG_BO,
    LANG_BUG,
    LANG_CA,
    LANG_CHR,
    LANG_CJM,
    LANG_COP,
    LANG_CS,
    LANG_CY,
    LANG_DA,
    LANG_DE,
    LANG_DV,
    LANG_EL,
    LANG_ES,
    LANG_ET,
    LANG_FA,
    LANG_FI,
    LANG_FR,
    LANG_GA,
    LANG_GU,
    LANG_HE,
    LANG_HI,
    LANG_HR,
    LANG_HU,
    LANG_HY,
    LANG_IS,
    LANG_IT,
    LANG_JA,
    LANG_JV,
    LANG_KA,
    LANG_KHB,
    LANG_KM,
    LANG_KN,
    LANG_KO,
    LANG_LIS,
    LANG_LO,
    LANG_LT,
    LANG_LV,
    LANG_META,
    LANG_ML,
    LANG_MN,
    LANG_MNI,
    LANG_MR,
    LANG_MT,
    LANG_MY,
    LANG_NE,
    LANG_NL,
    LANG_NO,
    LANG_NOD,
    LANG_NQO,
    LANG_OR,
    LANG_PA,
    LANG_PL,
    LANG_PT,
    LANG_RO,
    LANG_RU,
    LANG_SA,
    LANG_SAT,
    LANG_SI,
    LANG_SK,
    LANG_SL,
    LANG_SQ,
    LANG_SR,
    LANG_SU,
    LANG_SV,
    LANG_SYR,
    LANG_TA,
    LANG_TDD,
    LANG_TE,
    LANG_TH,
    LANG_TL,
    LANG_TR,
    LANG_TZM,
    LANG_UK,
    LANG_VAI,
    LANG_VI,
    LANG_ZH,
    SCRIPT_META,
    LangMeta,
    Script,
    ScriptMeta,
)
from translit._translit import (
    SafeHostnameDetails,
    # Exception
    TranslitError,
    _catalog_key,
    _clear_replacements,
    _collapse_whitespace,
    _decode_to_utf8,
    _demojize,
    # Encoding detection
    _detect_encoding,
    # Predicates
    _detect_scripts,
    _display_clean,
    _fold_case,
    # Grapheme cluster functions
    _grapheme_len,
    _grapheme_split,
    _grapheme_truncate,
    _inspect_auto_lang,
    _is_ascii,
    _is_confusable,
    _is_mixed_script,
    _is_normalized,
    # Hostname safety
    _is_safe_hostname,
    _is_zalgo,
    # Language profiles
    _list_langs,
    _ml_normalize,
    _normalize,  # noqa: F401  (used by normalize() and internal pipelines)
    _normalize_batch,
    _normalize_confusables,
    _register_lang,
    _register_replacements,
    _registrations_sealed,
    _remove_replacement,
    # Reverse transliteration
    _reverse_langs,
    _reverse_transliterate,
    _sanitize_filename,
    _sanitize_user_input,
    _seal_registrations,
    # Precompiled pipelines
    _search_key,
    _security_clean,
    # Emoji provider
    _set_emoji_provider,
    # Stateful
    _Slugifier,
    _slugify,
    _slugify_batch,
    _sort_key,
    _strip_accents,
    _strip_accents_batch,
    _strip_bidi,
    _strip_obfuscation,
    _strip_zalgo,
    _TextPipeline,
    # Core transforms (Rust implementations)
    _transliterate,
    # Batch APIs (single PyO3 boundary crossing for N strings)
    _transliterate_batch,
    _transliterate_context,
    _UniqueSlugifier,
)
from translit._types import NF, EmojiProvider, ErrorMode, NormalizationForm, Platform

# --- Resource limits (must match Rust-side constants) ---
_MAX_BATCH_SIZE: int = 100_000
_MAX_GRAPHEME_SPLIT_INPUT: int = 10 * 1024 * 1024  # 10 MiB

# --- Enum validation (must match Rust-side messages; validated in Python so the
#     ASCII fast-path cannot silently accept a typo'd value before reaching Rust, #99) ---
_VALID_ERROR_MODES: tuple[str, ...] = ("replace", "ignore", "preserve")
_VALID_NORM_FORMS: tuple[str, ...] = ("NFC", "NFD", "NFKC", "NFKD")


def _validate_batch(texts: object, func_name: str) -> None:
    """Validate that texts is a list[str] within batch size limits."""
    if not isinstance(texts, list):
        raise TypeError(f"{func_name}() expects list[str], got {type(texts).__name__}")
    if len(texts) > _MAX_BATCH_SIZE:
        raise TranslitError(
            f"batch too large ({len(texts)} items); maximum is {_MAX_BATCH_SIZE} items"
        )
    for i, t in enumerate(texts):
        if not isinstance(t, str):
            raise TypeError(f"{func_name}() element {i} must be str, got {type(t).__name__}")


# --- Core transforms ---


def _check_transliterate_conflicts(
    *,
    lang: str | None,
    target: str | None,
    errors: ErrorMode,
    replace_with: str,
    strict_iso9: bool,
    gost7034: bool,
    tones: bool,
    context: bool,
) -> None:
    """Reject conflicting ``transliterate()`` kwarg combinations (#69).

    A single conflict matrix, applied identically before the str/list dispatch
    so scalar and batch inputs raise the same error instead of one silently
    dropping a parameter the other honours.

    ``target`` selects *reverse* transliteration; ``context`` and ``tones`` are
    *forward-only*, so combining either with ``target`` is an error. ``context``
    (abjad vowel restoration) has no toned-pinyin output, so ``context`` +
    ``tones`` is rejected too.

    Also validates the ``errors`` enum up front (#99): the ASCII fast-path returns
    before reaching Rust, so a typo'd ``errors`` would otherwise silently no-op on
    ASCII input and only raise later on the first non-ASCII string.
    """
    if errors not in _VALID_ERROR_MODES:
        raise TranslitError(f"errors must be 'replace', 'ignore', or 'preserve', got {errors!r}")
    if target is not None and lang is not None:
        raise ValueError("'lang' and 'target' are mutually exclusive")
    if context and target is not None:
        raise ValueError("'context' and 'target' are mutually exclusive")
    if context and tones:
        raise ValueError(
            "'tones' cannot be used with 'context' — context-aware "
            "transliteration does not produce toned pinyin"
        )
    if target is not None:
        forward_only: dict[str, object] = {}
        if errors != "replace":
            forward_only["errors"] = errors
        if replace_with != "[?]":
            forward_only["replace_with"] = replace_with
        if strict_iso9:
            forward_only["strict_iso9"] = strict_iso9
        if gost7034:
            forward_only["gost7034"] = gost7034
        if tones:
            forward_only["tones"] = tones
        if forward_only:
            names = ", ".join(sorted(forward_only))
            raise ValueError(f"forward-only parameters ({names}) cannot be used with 'target'")


@overload
def transliterate(
    text: str,
    *,
    lang: str | None = ...,
    target: str | None = ...,
    errors: ErrorMode = ...,
    replace_with: str = ...,
    strict_iso9: bool = ...,
    gost7034: bool = ...,
    tones: bool = ...,
    context: bool = ...,
) -> str: ...


@overload
def transliterate(
    text: list[str],
    *,
    lang: str | None = ...,
    target: str | None = ...,
    errors: ErrorMode = ...,
    replace_with: str = ...,
    strict_iso9: bool = ...,
    gost7034: bool = ...,
    tones: bool = ...,
    context: bool = ...,
) -> list[str]: ...


def transliterate(
    text: str | list[str],
    *,
    lang: str | None = None,
    target: str | None = None,
    errors: ErrorMode = "replace",
    replace_with: str = "[?]",
    strict_iso9: bool = False,
    gost7034: bool = False,
    tones: bool = False,
    context: bool = False,
) -> str | list[str]:
    """Unicode → ASCII transliteration.

    Accepts a single string or a list of strings. When a list is passed,
    forward transliteration (the default) processes all strings in a single
    Rust call for better throughput; reverse transliteration (``target=...``)
    and context-aware transliteration (``context=True``) process the list item
    by item.

    Args:
        text: Input Unicode string, or list of strings for batch processing.
        lang: Language code for language-specific mappings.
              e.g. "de" (ü→ue), "ja" (kanji→romaji), "zh" (hanzi→pinyin).
              Use "auto" to detect the dominant non-Latin script and select
              the appropriate language automatically.
              Use "ja-kunrei" for Kunrei-shiki romanization of Japanese kana.
              None uses best-effort default tables.
        target: Target language code for *reverse* transliteration
                (romanized Latin → native script). Mutually exclusive with
                *lang*. Use :func:`reverse_langs` to list supported languages.
        errors: How to handle untransliterable characters.
                "replace" — substitute with *replace_with*.
                "ignore" — silently drop.
                "preserve" — keep the original character.
        replace_with: Replacement string when errors="replace". An empty string
                      (``""``) is equivalent to ``errors="ignore"`` — the
                      character is silently dropped. This matches the behaviour
                      of the Unidecode library.
        strict_iso9: Use a scholarly **ASCII** Cyrillic transliteration with
                     consistent 1:1-style overrides (e.g. й→j, ю→ju, я→ja).
                     NOTE: this is *not* the diacritic ISO 9:1995 standard
                     (which uses ž, č, š, ŝ, h). translit's tables are ASCII-only
                     by design, so it emits digraphs (ж→zh, ч→ch, ш→sh) instead
                     of the standard's diacritics — do not rely on this for
                     ISO 9-conformant library catalog access points (#94).
        gost7034: Use GOST R 7.0.34-2014 simplified transliteration for
                  Russian Cyrillic. Mutually exclusive with *strict_iso9*.
                  Key differences from default: х→x, ц→c, щ→shh, й→j.
        tones: Output toned pinyin (with diacritics) for CJK characters.
               e.g. "běi jīng" instead of "bei jing". Coverage includes
               the ~2000 most common characters; others fall through to
               toneless pinyin. Forward-only: cannot be combined with *target*
               or *context*.
        context: Use dictionary-based vowel restoration for abjad scripts
                 (Arabic/Persian/Hebrew), producing more readable output than
                 the context-free tables. Requires the prebuilt context
                 dictionaries (see ``bootstrap_dicts.sh`` / ``TRANSLIT_DICT_DIR``).
                 Forward-only: mutually exclusive with *target*, and cannot be
                 combined with *tones*.

    Returns:
        ASCII transliteration of the input. Returns ``str`` when given ``str``,
        ``list[str]`` when given ``list[str]``.

    Raises:
        TranslitError: If an internal Rust error occurs (e.g. invalid
            ``errors`` value passed at runtime).
        ValueError: If both *strict_iso9* and *gost7034* are True.
        ValueError: If both *lang* and *target* are set.
        ValueError: If *context* and *target* are both set.
        ValueError: If *context* and *tones* are both set.
        ValueError: If *target* is set with forward-only parameters.

    Examples:
        >>> transliterate("café résumé")
        'cafe resume'
        >>> transliterate(["café", "naïve"])
        ['cafe', 'naive']
        >>> transliterate("München", lang="de")
        'Muenchen'
        >>> transliterate("Moskva", target="ru")
        'Москва'
    """
    # Resolve conflicting kwargs once, before the str/list dispatch, so scalar
    # and batch inputs behave identically (#69).
    _check_transliterate_conflicts(
        lang=lang,
        target=target,
        errors=errors,
        replace_with=replace_with,
        strict_iso9=strict_iso9,
        gost7034=gost7034,
        tones=tones,
        context=context,
    )

    # ── Batch path ──
    if isinstance(text, list):
        _validate_batch(text, "transliterate")
        if context:
            # Context-aware: process each string individually through the context engine
            return [
                _transliterate_context(
                    t,
                    lang=lang,
                    errors=errors,
                    replace_with=replace_with,
                    strict_iso9=strict_iso9,
                    gost7034=gost7034,
                )
                for t in text
            ]
        if target is not None:
            return [_reverse_transliterate(t, lang=target) for t in text]
        return _transliterate_batch(
            text,
            lang=lang,
            errors=errors,
            replace_with=replace_with,
            strict_iso9=strict_iso9,
            gost7034=gost7034,
            tones=tones,
        )

    # ── Single-string path ──
    if not isinstance(text, str):
        raise TypeError(f"transliterate() expects str or list[str], got {type(text).__name__}")

    if target is not None:
        return _reverse_transliterate(text, lang=target)

    # Context-aware path: use dictionary-based vowel restoration for abjad scripts
    if context:
        return _transliterate_context(
            text,
            lang=lang,
            errors=errors,
            replace_with=replace_with,
            strict_iso9=strict_iso9,
            gost7034=gost7034,
        )

    # Fast path: pure ASCII needs no transliteration (~30 ns vs ~240 ns PyO3
    # call). Skipped when global replacements may be registered, since an
    # ASCII-keyed replacement (e.g. "@" -> "(at)") must still be applied in Rust.
    if text.isascii() and not _has_global_replacements:
        return text
    return _transliterate(
        text,
        lang=lang,
        errors=errors,
        replace_with=replace_with,
        strict_iso9=strict_iso9,
        gost7034=gost7034,
        tones=tones,
    )


@overload
def slugify(
    text: str,
    *,
    separator: str = ...,
    lowercase: bool = ...,
    max_length: int = ...,
    word_boundary: bool = ...,
    save_order: bool = ...,
    stopwords: Iterable[str] = ...,
    regex_pattern: str | None = ...,
    replacements: Iterable[tuple[str, str]] = ...,
    allow_unicode: bool = ...,
    lang: str | None = ...,
    entities: bool = ...,
    decimal: bool = ...,
    hexadecimal: bool = ...,
) -> str: ...


@overload
def slugify(
    text: list[str],
    *,
    separator: str = ...,
    lowercase: bool = ...,
    max_length: int = ...,
    word_boundary: bool = ...,
    save_order: bool = ...,
    stopwords: Iterable[str] = ...,
    regex_pattern: str | None = ...,
    replacements: Iterable[tuple[str, str]] = ...,
    allow_unicode: bool = ...,
    lang: str | None = ...,
    entities: bool = ...,
    decimal: bool = ...,
    hexadecimal: bool = ...,
) -> list[str]: ...


def slugify(
    text: str | list[str],
    *,
    separator: str = "-",
    lowercase: bool = True,
    max_length: int = 0,
    word_boundary: bool = False,
    save_order: bool = False,
    stopwords: Iterable[str] = (),
    regex_pattern: str | None = None,
    replacements: Iterable[tuple[str, str]] = (),
    allow_unicode: bool = False,
    lang: str | None = None,
    entities: bool = True,
    decimal: bool = True,
    hexadecimal: bool = True,
) -> str | list[str]:
    """Generate a URL-safe slug from Unicode text.

    Full pipeline: decode entities → transliterate → lowercase →
    strip non-alphanumeric → collapse separators → apply stopwords/max_length.

    Shares python-slugify's core keyword parameters (``separator``,
    ``max_length``, ``word_boundary``, ``save_order``, ``stopwords``,
    ``lowercase``, etc.), so ``slugify(text, ...)`` calls port directly. Note
    that translit makes every parameter past *text* keyword-only, whereas
    python-slugify accepts some positionally.

    Args:
        text: Input Unicode string.
        separator: Character(s) between slug words.
        lowercase: Convert to lowercase.
        max_length: Maximum slug length in bytes (0 = unlimited).
            With ``allow_unicode=True``, multi-byte characters count as
            2–4 bytes each — use :func:`grapheme_truncate` for
            character-aware limiting.
        word_boundary: When truncating via max_length, cut at word boundaries.
        save_order: Accepted for python-slugify compatibility but has no
            effect — word order is always preserved.
        stopwords: Words to remove from the slug.
        regex_pattern: Custom regex for stripping characters.
        replacements: Pre-transliteration (old, new) substitution pairs.
        allow_unicode: Keep non-ASCII letters instead of transliterating.
        lang: Language code for transliteration (e.g. "de", "ru", "auto").
        entities: Decode HTML entities before processing.
        decimal: Decode HTML decimal entities (&#123;).
        hexadecimal: Decode HTML hex entities (&#x7B;).

    Returns:
        URL-safe slug string.

    Raises:
        TranslitError: If an internal Rust error occurs.

    Examples:
        >>> slugify("Hello World!")
        'hello-world'
        >>> slugify("Straße nach München", lang="de")
        'strasse-nach-muenchen'
        >>> slugify("My Title", separator="_")
        'my_title'
        >>> slugify("The Big Fox", stopwords=["the"])
        'big-fox'
        >>> slugify("Very Long Title Here", max_length=10, word_boundary=True)
        'very-long'
    """
    _sw = stopwords if isinstance(stopwords, (tuple, list)) else list(stopwords)
    _rp = replacements if isinstance(replacements, (tuple, list)) else list(replacements)

    if isinstance(text, list):
        _validate_batch(text, "slugify")
        return _slugify_batch(
            text,
            separator=separator,
            lowercase=lowercase,
            max_length=max_length,
            word_boundary=word_boundary,
            save_order=save_order,
            stopwords=_sw,
            regex_pattern=regex_pattern,
            replacements=_rp,
            allow_unicode=allow_unicode,
            lang=lang,
            entities=entities,
            decimal=decimal,
            hexadecimal=hexadecimal,
        )

    if not isinstance(text, str):
        raise TypeError(f"slugify() expects str or list[str], got {type(text).__name__}")
    if max_length < 0:
        raise ValueError(f"max_length must be non-negative, got {max_length}")
    return _slugify(
        text,
        separator=separator,
        lowercase=lowercase,
        max_length=max_length,
        word_boundary=word_boundary,
        save_order=save_order,
        stopwords=_sw,
        regex_pattern=regex_pattern,
        replacements=_rp,
        allow_unicode=allow_unicode,
        lang=lang,
        entities=entities,
        decimal=decimal,
        hexadecimal=hexadecimal,
    )


@overload
def normalize(text: str, *, form: NormalizationForm = ...) -> str: ...


@overload
def normalize(text: list[str], *, form: NormalizationForm = ...) -> list[str]: ...


def normalize(
    text: str | list[str],
    *,
    form: NormalizationForm = "NFC",
) -> str | list[str]:
    """Unicode normalization.

    Accepts a single string or a list of strings.

    Args:
        text: Input string, or list of strings for batch processing.
        form: Normalization form — "NFC", "NFD", "NFKC", or "NFKD".

    Returns:
        Normalized string(s). Returns ``str`` when given ``str``,
        ``list[str]`` when given ``list[str]``.

    Examples:
        >>> normalize("e\u0301", form="NFC")
        'é'
        >>> normalize(["e\u0301", "n\u0303o"], form="NFC")
        ['é', 'ño']
    """
    # Validate the form enum before the ASCII fast-path / batch dispatch (#99):
    # otherwise a typo'd form silently no-ops on ASCII input.
    if form not in _VALID_NORM_FORMS:
        raise TranslitError(f"form must be 'NFC', 'NFD', 'NFKC', or 'NFKD', got {form!r}")
    if isinstance(text, list):
        _validate_batch(text, "normalize")
        return _normalize_batch(text, form=form)
    if not isinstance(text, str):
        raise TypeError(f"normalize() expects str or list[str], got {type(text).__name__}")
    if text.isascii():
        return text
    return _normalize(text, form=form)


def normalize_confusables(
    text: str,
    *,
    target_script: str = "latin",
) -> str:
    """Replace Unicode confusable homoglyphs with target-script equivalents.

    Uses Unicode TR39 confusables table. Characters without a confusable
    equivalent in the target script pass through unchanged (visual mapping
    only, not transliteration).

    Args:
        text: Input string potentially containing homoglyphs.
        target_script: Script to normalize toward. Supported values:
            ``"latin"`` (default, ~2,063 mappings) and ``"cyrillic"``
            (~1,369 mappings).

    Returns:
        String with confusable characters replaced by target-script equivalents.

    Raises:
        TranslitError: If *target_script* is not a supported value.

    Examples:
        >>> normalize_confusables("Ηello")  # Greek Η looks like Latin H
        'Hello'
        >>> normalize_confusables("раypal")  # Cyrillic р/а look like Latin p/a
        'paypal'
        >>> normalize_confusables("paypal", target_script="cyrillic")
        'раура\u04cf'
    """
    if not isinstance(text, str):
        raise TypeError(f"normalize_confusables() expects str, got {type(text).__name__}")
    return _normalize_confusables(text, target_script=target_script)


def sanitize_filename(
    text: str,
    *,
    separator: str = "_",
    max_length: int = 255,
    platform: Platform = "universal",
    lang: str | None = None,
    preserve_extension: bool = True,
    # pathvalidate compatibility aliases
    replacement_text: str | None = None,
    max_len: int | None = None,
) -> str:
    """Sanitize a string into a safe filename.

    Transliterate → strip OS-illegal chars → collapse separators →
    handle reserved names (CON, NUL, etc.) → truncate respecting extension.

    Args:
        text: Input string (title, user input, etc.).
        separator: Replacement for spaces and stripped characters.
            Also accepted as ``replacement_text`` (pathvalidate compatibility).
        max_length: Maximum filename length measured in **bytes** (UTF-8
            encoded), not characters. Default 255 matches the ext4/APFS/NTFS
            filesystem limit. Truncation always lands on a character boundary
            to avoid splitting multi-byte sequences.
            Also accepted as ``max_len`` (pathvalidate compatibility).
        platform: Target platform — ``"universal"``, ``"windows"``, or
            ``"posix"``.
        lang: Language code for transliteration (e.g. ``"de"``, ``"ja"``).
        preserve_extension: When ``True`` (default), the file extension is
            kept intact within *max_length*. If the extension alone (including
            the leading ``.``) is ≥ *max_length*, the extension is dropped and
            the whole result is truncated to *max_length* bytes. When
            ``False``, the entire string is truncated to *max_length* bytes
            without special treatment of the extension.

    Returns:
        Safe filename string.

    Raises:
        TranslitError: If an internal Rust error occurs.

    Examples:
        >>> sanitize_filename("My Report (final).pdf")
        'My_Report_(final).pdf'
        >>> sanitize_filename("CON.txt")  # reserved on Windows
        '_CON.txt'
        >>> sanitize_filename("résumé.docx", lang="fr")
        'resume.docx'
    """
    if not isinstance(text, str):
        raise TypeError(f"sanitize_filename() expects str, got {type(text).__name__}")
    # pathvalidate compatibility: replacement_text → separator
    if replacement_text is not None:
        separator = replacement_text
    # pathvalidate compatibility: max_len → max_length
    if max_len is not None:
        max_length = max_len
    if max_length < 0:
        raise ValueError(f"max_length must be non-negative, got {max_length}")
    return _sanitize_filename(
        text,
        separator=separator,
        max_length=max_length,
        platform=platform,
        lang=lang,
        preserve_extension=preserve_extension,
    )


@overload
def strip_accents(text: str) -> str: ...


@overload
def strip_accents(text: list[str]) -> list[str]: ...


def strip_accents(text: str | list[str]) -> str | list[str]:
    """Remove diacritical marks while preserving base characters.

    NFD decompose → strip combining marks → NFC recompose.
    Accepts a single string or a list of strings.

    Args:
        text: Input string, or list of strings for batch processing.

    Returns:
        String(s) with diacritical marks removed.

    Examples:
        >>> strip_accents("café résumé naïve")
        'cafe resume naive'
        >>> strip_accents(["café", "naïve"])
        ['cafe', 'naive']
    """
    if isinstance(text, list):
        _validate_batch(text, "strip_accents")
        return _strip_accents_batch(text)
    if not isinstance(text, str):
        raise TypeError(f"strip_accents() expects str or list[str], got {type(text).__name__}")
    if text.isascii():
        return text
    return _strip_accents(text)


#: Alias for :func:`strip_accents` — common name in sklearn and ML ecosystems.
remove_accents = strip_accents


def fold_case(text: str) -> str:
    """Full Unicode case folding per CaseFolding.txt (Unicode 16.0).

    Unlike ``str.lower()``, this implements the complete Unicode Case Folding
    algorithm with all 1,557 status-C and status-F mappings.  Covers Latin
    (ß→ss, ſ→s, İ→i̇), Greek (ς→σ, variant forms ϐ→β, ϑ→θ, ϕ→φ, ϖ→π,
    ϰ→κ, ϱ→ρ), Cyrillic, Armenian (ligature և→եւ), Georgian Mtavruli,
    Cherokee, Adlam, Deseret, Osage, Warang Citi, fullwidth Latin,
    and all Latin ligature expansions (ﬁ→fi, ﬂ→fl, ﬀ→ff, ﬃ→ffi,
    ﬄ→ffl, ﬅ→st, ﬆ→st).

    Equivalent to ``str.casefold()`` but executed in Rust via a
    compile-time PHF (perfect hash function) table.  Pure-ASCII strings
    take a branchless fast path with no table lookup.

    Args:
        text: Input string.

    Returns:
        Case-folded string.  Characters not in CaseFolding.txt map to
        themselves.  Output satisfies ``fold_case(fold_case(x)) == fold_case(x)``
        (idempotent).

    Examples:
        >>> fold_case("Straße")
        'strasse'
        >>> fold_case("ΣΟΦΙΑ")
        'σοφια'
        >>> fold_case("ﬁnd")
        'find'
    """
    if not isinstance(text, str):
        raise TypeError(f"fold_case() expects str, got {type(text).__name__}")
    if text.isascii():
        return text.lower()
    return _fold_case(text)


#: Alias for :func:`fold_case` — matches ``str.casefold()`` naming for drop-in use.
casefold = fold_case


def collapse_whitespace(
    text: str,
    *,
    strip_control: bool = True,
    strip_zero_width: bool = True,
) -> str:
    """Normalize all Unicode whitespace variants to single ASCII spaces.

    Optionally strip control characters and zero-width characters.

    Args:
        text: Input string.
        strip_control: Remove C0/C1 control characters (U+0000–U+001F,
            U+007F–U+009F) except tab and newline. Carriage return (``\\r``)
            is stripped, so Windows-style ``\\r\\n`` becomes ``\\n``.
        strip_zero_width: Remove zero-width space (U+200B), zero-width
            non-joiner (U+200C), zero-width joiner (U+200D), and
            word joiner (U+2060).

    Returns:
        String with whitespace collapsed and optionally cleaned.

    Examples:
        >>> collapse_whitespace("  hello   world  ")
        'hello world'
        >>> collapse_whitespace("tabs\\there\\ttoo")
        'tabs here too'
        >>> collapse_whitespace("a\\u200Bb\\u200Bc")  # zero-width spaces
        'abc'
    """
    if not isinstance(text, str):
        raise TypeError(f"collapse_whitespace() expects str, got {type(text).__name__}")
    return _collapse_whitespace(
        text, strip_control=strip_control, strip_zero_width=strip_zero_width
    )


def demojize(
    text: str,
    *,
    strip_modifiers: bool = False,
    errors: ErrorMode = "replace",
    replace_with: str = "[?]",
    provider: EmojiProvider | None = None,
    # emoji library compatibility
    delimiters: tuple[str, str] | None = None,
) -> str:
    """Expand emoji sequences to their CLDR short-name text descriptions.

    Output is always the bare CLDR short name as plain text.

    Args:
        text: Input string potentially containing emoji.
        strip_modifiers: If True, collapse skin tone and hair style variants
            to their base form (e.g. "woman raising hand" instead of
            "woman raising hand: medium-dark skin tone").
        errors: How to handle emoji not in the provider's data.
                "replace" — substitute with replace_with.
                "ignore" — silently drop.
                "preserve" — keep the original emoji.
        replace_with: Replacement string when errors="replace".
        provider: An object implementing the :class:`EmojiProvider` protocol.
            Overrides the global provider for this call.
            None uses the global provider or the built-in default.
        delimiters: ``emoji`` library compatibility — ignored with a
            ``DeprecationWarning``. translit always outputs bare CLDR
            short names without delimiters; wrap the result yourself if
            you need delimiters (e.g. ``f":{name}:"``).

    Returns:
        Text with emoji replaced by their descriptions.

    Raises:
        TranslitError: If an internal Rust error occurs.

    Warns:
        UserWarning: If the provider raises an exception or returns a
            non-string value. The built-in CLDR tables are used as a
            fallback for that sequence.

    Examples:
        >>> demojize("I ❤️ Python 🐍")
        'I red heart Python snake'
    """
    if not isinstance(text, str):
        raise TypeError(f"demojize() expects str, got {type(text).__name__}")
    if delimiters is not None:
        _warnings.warn(
            "The 'delimiters' parameter is not supported by translit.demojize(); "
            "translit always outputs bare CLDR short names. "
            "Wrap the result yourself if you need delimiters.",
            DeprecationWarning,
            stacklevel=2,
        )
    return _demojize(
        text,
        strip_modifiers=strip_modifiers,
        errors=errors,
        replace_with=replace_with,
        provider=provider,
    )


def set_emoji_provider(provider: EmojiProvider | None = None) -> None:
    """Set a global emoji provider for all demojize calls.

    The provider must implement the :class:`EmojiProvider` protocol.

    Pass None to reset to the built-in default (latest English CLDR).

    Args:
        provider: An object implementing the :class:`EmojiProvider` protocol,
            or None to reset to the built-in default.

    Examples:
        >>> set_emoji_provider(None)  # reset to default provider
    """
    if provider is not None and not callable(getattr(provider, "lookup", None)):
        raise TypeError(
            f"EmojiProvider must have a callable lookup() method; got {type(provider).__name__}"
        )
    _set_emoji_provider(provider)


# --- Precompiled pipelines ---


def security_clean(text: str) -> str:
    """Security-focused text canonicalization.

    Pipeline: NFKC → confusables → strip bidi/format → collapse_whitespace

    Collapses fullwidth bypasses, neutralizes homoglyph spoofing, strips
    dangerous bidi overrides and soft hyphens, then normalizes whitespace
    (collapsing runs, stripping control chars and zero-width injections).

    Args:
        text: Input string (user-submitted, network-received, etc.).

    Returns:
        Canonicalized string safe for security-sensitive comparisons.

    Examples:
        >>> security_clean("Ηello Ꮤorld")  # Greek Η + Cherokee Ꮤ → Latin
        'Hello World'
    """
    return _security_clean(text)


def ml_normalize(
    text: str,
    *,
    lang: str | None = None,
    emoji: str = "cldr",
) -> str:
    """ML/NLP text normalization pipeline.

    Pipeline: NFKC → emoji→text → [transliterate] → strip_accents →
              fold_case → collapse_whitespace

    Produces clean, accent-free, lowercased text suitable for tokenizers,
    embeddings, and feature extraction. Emoji are expanded to their CLDR
    short-name descriptions.

    Args:
        text: Input Unicode string.
        lang: Optional language code for transliteration (e.g. "de", "ja").
        emoji: Emoji handling mode.
               ``"cldr"`` — expand emoji to CLDR short names (default).
               ``"none"`` — leave emoji characters unchanged.

    Returns:
        Clean, accent-free, lowercased text.

    Raises:
        TranslitError: If *emoji* is not ``"cldr"`` or ``"none"``,
            or if an internal Rust error occurs.

    Examples:
        >>> ml_normalize("Café RÉSUMÉ")
        'cafe resume'
        >>> ml_normalize("München", lang="de")
        'muenchen'
    """
    return _ml_normalize(text, lang=lang, emoji_style=emoji)


def catalog_key(
    text: str,
    *,
    lang: str | None = None,
    strict_iso9: bool = False,
) -> str:
    """Library catalog key generation pipeline.

    Pipeline: NFKC → transliterate → confusables → strip_accents →
              fold_case → collapse_whitespace

    Produces a canonical deduplication key for bibliographic titles.

    Args:
        text: Input title or heading.
        lang: Language code for transliteration (e.g. "ru", "ja").
        strict_iso9: Use ISO 9:1995 scholarly transliteration for Cyrillic.

    Returns:
        Canonical deduplication key string.

    Raises:
        TranslitError: If an internal Rust error occurs.

    Examples:
        >>> catalog_key("  Café  RÉSUMÉ  ")
        'cafe resume'
        >>> catalog_key("ΩMEGA  café")
        'omega cafe'
    """
    return _catalog_key(text, lang=lang, strict_iso9=strict_iso9)


def display_clean(text: str) -> str:
    """Display-safe text cleaning pipeline.

    Pipeline: strip bidi/format → collapse_whitespace (strip control + strip zero-width)

    Lightweight cleanup for user-submitted content destined for rendering.
    Strips bidirectional overrides (which can visually reorder text to hide
    malicious content), soft hyphens, control characters, and zero-width
    injections, then collapses runs of whitespace to single spaces.

    Args:
        text: Input string (user-submitted content).

    Returns:
        Cleaned string safe for display rendering.

    Examples:
        >>> display_clean("hello\\x00world\\u200b!")
        'helloworld!'
        >>> display_clean("  spaced   out  ")
        'spaced out'
    """
    return _display_clean(text)


def search_key(
    text: str,
    *,
    lang: str | None = None,
) -> str:
    """Search index key generation pipeline.

    Pipeline: NFKC → transliterate → strip_accents → fold_case →
              collapse_whitespace

    Produces a case-insensitive, accent-insensitive, script-insensitive
    lookup key.  Like :func:`catalog_key` but without confusable
    normalization — lighter and faster for search indexes.

    Args:
        text: Input text to generate a search key from.
        lang: Language code for transliteration (e.g. "ru", "de").

    Returns:
        Normalized search key string.

    Examples:
        >>> search_key("  Café  RÉSUMÉ  ")
        'cafe resume'
        >>> search_key("Москва")
        'moskva'
        >>> search_key("Über allen Gipfeln")
        'uber allen gipfeln'
    """
    return _search_key(text, lang=lang)


def sort_key(
    text: str,
    *,
    lang: str | None = None,
) -> str:
    """Sort key generation pipeline.

    Pipeline: NFKC → strip_bidi → transliterate → fold_case → collapse_whitespace

    Produces a case-insensitive ASCII key for alphabetical ordering.
    Transliteration folds accented characters to their ASCII base (``é`` → ``e``,
    ``ü`` → ``u``), so the result is **accent-folded**, not accent-preserving.

    .. note::
        In practice this currently produces the same output as
        :func:`search_key`: ``search_key`` adds an explicit accent-strip pass,
        but transliteration has already removed accents by that point, so the
        two keys coincide for typical input. Use whichever name documents intent
        at the call site. (Distinct accent-preserving ordering is tracked for a
        future release.)

    Args:
        text: Input text to generate a sort key from.
        lang: Language code for transliteration (e.g. "ru", "de").

    Returns:
        Normalized sort key string.

    Examples:
        >>> sort_key("Война и мир")
        'voyna i mir'
        >>> sort_key("Über allen Gipfeln")
        'uber allen gipfeln'
        >>> sort_key("  Café  ")
        'cafe'
    """
    return _sort_key(text, lang=lang)


def strip_bidi(text: str) -> str:
    """Strip bidirectional override and formatting characters (UAX #9).

    Removes: soft hyphen (U+00AD), Arabic Letter Mark (U+061C),
    LRM/RLM (U+200E/F), bidi embeddings/overrides (U+202A–U+202E),
    bidi isolates (U+2066–U+2069).

    Args:
        text: Input string.

    Returns:
        String with bidi override and formatting characters removed.

    Examples:
        >>> strip_bidi("hello\\u200eworld")  # remove LRM
        'helloworld'
        >>> strip_bidi("hello\\u061cworld")  # remove Arabic Letter Mark
        'helloworld'
        >>> strip_bidi("safe text")  # no bidi chars → unchanged
        'safe text'
    """
    return _strip_bidi(text)


def sanitize_user_input(text: str) -> str:
    """Sanitize user-submitted input for web applications.

    Preserves the original script (no transliteration) while neutralizing
    common attack vectors: zalgo stacking, homoglyph spoofing, bidi
    overrides, zero-width injections, and control characters.

    Pipeline: ``NFKC → strip_bidi → strip_zero_width → strip_zalgo → confusables
    → collapse_whitespace`` (invisibles are stripped before zalgo-capping so they
    cannot split combining-mark runs, keeping the output idempotent)

    Args:
        text: User-submitted input string.

    Returns:
        Sanitized string safe for storage and display.

    Examples:
        >>> sanitize_user_input("Hello, world!")
        'Hello, world!'
        >>> sanitize_user_input("p\\u0430ypal")  # Cyrillic а → Latin a
        'paypal'
        >>> sanitize_user_input("admin\\u202euser")  # RLO stripped
        'adminuser'
    """
    return _sanitize_user_input(text)


def strip_obfuscation(text: str) -> str:
    """Maximum-strength text deobfuscation.

    Neutralizes homoglyph spoofing, zalgo abuse, invisible character
    injection, and bidi attacks. Uses TR39 confusable mapping (visual
    similarity) — Cyrillic р→p, с→c, В→B — not phonetic transliteration.

    **Does not transliterate.** Non-Latin scripts that have no Latin
    confusable equivalent pass through unchanged. Chain with
    ``transliterate()`` explicitly if you also need romanization.

    **Preserves case.** Case is not deception — proper nouns, acronyms,
    and sentence boundaries are meaningful. Chain with ``fold_case()``
    if lowercasing is also needed.

    Pipeline: ``NFKC → strip_zalgo(max_marks=0) → strip_bidi → strip_zero_width
    → demojize → confusables → strip_accents → collapse_whitespace``
    (confusables runs after demojize so typographic punctuation in emoji names is
    folded too, keeping the output idempotent)

    Args:
        text: Input text (user-generated, adversarial, multilingual).

    Returns:
        Deobfuscated string with homoglyphs resolved, zalgo stripped,
        invisible characters removed. Case is preserved.

    Examples:
        >>> strip_obfuscation("P\\u0430yP\\u0430l")  # Cyrillic а → Latin a
        'PayPal'
        >>> strip_obfuscation("\\u0420rodu\\u0441t")  # Cyrillic Р→P, с→c
        'Product'
        >>> strip_obfuscation("H\\u0338a\\u0338t\\u0338e\\u0338 speech")
        'Hate speech'
    """
    return _strip_obfuscation(text)


def is_zalgo(text: str, *, threshold: int = 3) -> bool:
    """Detect whether text contains zalgo-style combining mark abuse.

    Returns ``True`` if any base character has more than *threshold*
    consecutive combining marks in NFD decomposition.

    Args:
        text: Input string to check.
        threshold: Maximum allowed combining marks per base character
            (default: ``3``).  Vietnamese ``ệ`` has 2 marks in NFD —
            the default is safe for all legitimate scripts.

    Returns:
        ``True`` if zalgo-style stacking is detected.

    Examples:
        >>> is_zalgo("café")
        False
        >>> is_zalgo("Việt Nam")
        False
        >>> is_zalgo("ḧ̸̡̢̧̛̗̱̜̼̯̞̙́̑̾̊̿̏̒̓̕ě̵̢̧̛̗̱̜̼̯̞̙̈́̑̾̊̿̏̒̓̕l̸̡̢̧̛̗̱̜̼̯̞̙̈́̑̾̊̿̏̒̓̕l̸̡̢̧̛̗̱̜̼̯̞̙̈́̑̾̊̿̏̒̓̕ơ̵̢̧̗̱̜̼̯̞̙̈́̑̾̊̿̏̒̓̕")
        True
    """
    return _is_zalgo(text, threshold=threshold)


def strip_zalgo(text: str, *, max_marks: int = 2) -> str:
    """Strip excessive combining marks, preserving legitimate diacritics.

    Caps the number of combining marks per base character at *max_marks*.
    Operates in NFD space and recomposes to NFC.

    Args:
        text: Input string (may contain zalgo abuse).
        max_marks: Maximum combining marks to keep per base character
            (default: ``2``).  Set to ``0`` to strip all combining marks
            (equivalent to :func:`strip_accents`).

    Returns:
        String with excess combining marks removed.

    Examples:
        >>> strip_zalgo("café")  # 1 combining mark — preserved
        'café'
        >>> strip_zalgo("Việt Nam")  # 2 marks — preserved
        'Việt Nam'
    """
    return _strip_zalgo(text, max_marks=max_marks)


# --- Grapheme cluster functions ---


def grapheme_len(text: str) -> int:
    """Count the number of user-perceived characters (extended grapheme clusters).

    This is the correct answer to "how many characters does the user see?"
    A single grapheme cluster may span multiple codepoints (e.g., flag emoji,
    skin-toned emoji, Hangul syllables with combining jamo, Zalgo text).

    Args:
        text: Input string.

    Returns:
        Number of extended grapheme clusters.

    Examples:
        >>> grapheme_len("café")
        4
        >>> grapheme_len("👨‍👩‍👧‍👦")  # family emoji = 1 grapheme cluster
        1
    """
    return _grapheme_len(text)


def grapheme_split(text: str) -> list[str]:
    """Split text into a list of extended grapheme clusters.

    Each element is a user-perceived character.

    Args:
        text: Input string.

    Returns:
        List of grapheme cluster strings.

    Examples:
        >>> grapheme_split("café")
        ['c', 'a', 'f', 'é']
        >>> len(grapheme_split("👨‍👩‍👧‍👦!"))  # family emoji + "!"
        2
    """
    if len(text) > _MAX_GRAPHEME_SPLIT_INPUT:
        raise TranslitError(
            f"input too large ({len(text)} bytes); maximum for grapheme_split() "
            f"is {_MAX_GRAPHEME_SPLIT_INPUT} bytes"
        )
    return _grapheme_split(text)


def grapheme_truncate(text: str, max_graphemes: int) -> str:
    """Truncate text to at most max_graphemes user-perceived characters.

    Unlike byte-level or codepoint-level truncation, this never splits
    a grapheme cluster (which could corrupt emoji, combining sequences,
    or Hangul syllables).

    Args:
        text: Input string.
        max_graphemes: Maximum number of grapheme clusters to keep.

    Returns:
        Truncated string containing at most max_graphemes grapheme clusters.

    Examples:
        >>> grapheme_truncate("Hello World", 5)
        'Hello'
        >>> grapheme_truncate("café", 3)
        'caf'
    """
    if max_graphemes < 0:
        raise ValueError(f"max_graphemes must be non-negative, got {max_graphemes}")
    return _grapheme_truncate(text, max_graphemes)


# --- Hostname safety ---


def is_safe_hostname(hostname: str) -> tuple[bool, SafeHostnameDetails]:
    """Check if a hostname is safe from Unicode homoglyph attacks.

    Returns (is_safe, details) where details is a ``SafeHostnameDetails``
    with attributes:

    - ``safe``: bool — True if no homoglyph spoofing detected.
    - ``scripts``: list[str] — Unicode scripts found across all labels.
    - ``mixed_script``: bool — True if multiple scripts detected.
    - ``has_confusables``: bool — True if confusable homoglyphs found.
    - ``canonical``: str — Latin-normalized form of the hostname.

    A hostname is considered unsafe if it contains mixed high-risk scripts
    (Cyrillic+Latin, Greek+Latin) or confusable homoglyphs.

    Args:
        hostname: Hostname string to check (e.g. "example.com").

    Returns:
        Tuple of (is_safe, details) where details is a SafeHostnameDetails.

    Examples:
        >>> safe, details = is_safe_hostname("google.com")
        >>> safe
        True
        >>> details.canonical
        'google.com'
    """
    return _is_safe_hostname(hostname)


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


# --- Encoding detection ---


def detect_encoding(data: bytes) -> tuple[str, float]:
    """Detect the encoding of a byte sequence.

    Returns (encoding_name, confidence) where confidence is 0.0–1.0.
    Uses the chardetng algorithm (Firefox's encoding detector).

    Important: automatic encoding detection is inherently probabilistic.
    A high confidence score does NOT guarantee correctness. For critical
    pipelines, always prefer explicit encoding metadata over detection.

    Args:
        data: Raw byte sequence to analyze.

    Returns:
        Tuple of (encoding_name, confidence) where confidence is 0.0–1.0.

    Raises:
        TranslitError: If the byte sequence cannot be analyzed.

    Examples:
        >>> enc, conf = detect_encoding(b"Hello World")
        >>> enc
        'UTF-8'
    """
    return _detect_encoding(data)


def decode_to_utf8(
    data: bytes,
    encoding: str | None = None,
    *,
    min_confidence: float = 0.95,
) -> tuple[str, bool]:
    """Decode a byte sequence to UTF-8.

    Returns (decoded_text, had_errors) where had_errors is True if any
    characters were replaced during decoding (lossy conversion).

    If encoding is None, auto-detects the encoding using the chardetng
    algorithm. Use min_confidence to require a minimum detection quality
    and avoid silently decoding with a low-confidence guess.

    Supports all WHATWG encodings (UTF-8, windows-1252, ISO-8859-1,
    Shift_JIS, EUC-JP, EUC-KR, Big5, GB18030, etc.).

    Args:
        data: Raw byte sequence to decode.
        encoding: Encoding name (e.g. "windows-1252"). None to auto-detect.
        min_confidence: Minimum acceptable detection confidence (0.0–1.0)
            when auto-detecting. Raises TranslitError if the detected
            confidence is below this threshold. Has no effect when
            ``encoding`` is provided explicitly. Defaults to ``0.95``
            (secure-by-default): the detector only reports ``0.50`` (ambiguous)
            or ``0.95`` (confident), so a ``0.95`` default rejects the ambiguous
            guess while accepting a confident one. (The earlier ``0.5`` default
            was inert — ``0.50 < 0.50`` is false — so it never rejected; #103.)
            Pass ``min_confidence=0.0`` to accept any guess.

    Returns:
        Tuple of (decoded_text, had_errors) where had_errors is True if
        any characters were replaced during lossy conversion.

    Raises:
        TranslitError: If the encoding name is unknown, decoding fails,
            or auto-detection confidence is below min_confidence.

    Examples:
        >>> text, had_errors = decode_to_utf8(b"caf\\xe9", "windows-1252")
        >>> text
        'café'
        >>> had_errors
        False
    """
    if not (0.0 <= min_confidence <= 1.0):
        raise ValueError(f"min_confidence must be between 0.0 and 1.0, got {min_confidence}")
    return _decode_to_utf8(data, encoding=encoding, min_confidence=min_confidence)


# --- Predicates ---


# Cache mapping script name → Script enum member for O(1) lookup
# instead of O(N) enum scan on each call to detect_scripts().
_SCRIPT_BY_NAME: dict[str, Script] = {s.value: s for s in Script}


def detect_scripts(text: str) -> list[Script]:
    """Return the set of Unicode scripts present in text, in order of first appearance.

    Args:
        text: Input string.

    Returns:
        List of :class:`Script` enum values, ordered by first appearance.

    Examples:
        >>> detect_scripts("Hello")
        [Script.LATIN]
        >>> detect_scripts("Hello Мир")
        [Script.LATIN, Script.CYRILLIC]
    """
    raw = _detect_scripts(text)
    result = []
    for name in raw:
        script = _SCRIPT_BY_NAME.get(name)
        if script is not None:
            result.append(script)
        else:
            _warnings.warn(
                f"Rust detected script {name!r} which is not in the Script enum; "
                f"upgrade translit or report this as a bug",
                stacklevel=2,
            )
    return result


def inspect_auto_lang(text: str) -> dict[str, str | list[str] | None]:
    """Inspect how ``lang="auto"`` would resolve for the given text.

    Use this to audit or log the detection decision made by the three-stage
    auto-detection pipeline.

    Args:
        text: Input string.

    Returns:
        Dict with keys:

        - ``script``: primary non-Latin script name, or ``None``
        - ``chosen_lang``: resolved language code, or ``None``
        - ``reason``: one of ``"unambiguous_script"``,
          ``"discriminator"``, ``"script_default"``,
          ``"latin_discriminator"``, ``"no_detection"``
        - ``discriminators_hit``: list of discriminator characters found

    Examples:
        >>> inspect_auto_lang("Київ")["chosen_lang"]
        'uk'
        >>> inspect_auto_lang("Москва")["reason"]
        'script_default'
    """
    result: dict[str, str | list[str] | None] = _inspect_auto_lang(text)  # type: ignore[assignment]
    return result


def is_mixed_script(text: str) -> bool:
    """True if text contains characters from more than one Unicode script.

    Args:
        text: Input string.

    Returns:
        True if multiple scripts detected (excluding Common/Inherited).

    Examples:
        >>> is_mixed_script("Hello")
        False
        >>> is_mixed_script("Hello Мир")  # Latin + Cyrillic
        True
    """
    return _is_mixed_script(text)


def is_confusable(
    text: str,
    *,
    target_script: str = "latin",
    # confusable_homoglyphs compatibility
    greedy: bool | None = None,
    preferred_aliases: list[str] | None = None,
) -> bool:
    """True if text contains characters confusable with target-script characters.

    Args:
        text: Input string.
        target_script: Script to check confusability against. Currently only
            ``"latin"`` is supported; any other value raises ``TranslitError``.
        greedy: ``confusable_homoglyphs`` compatibility — ignored with a
            ``DeprecationWarning``. translit always checks all characters.
        preferred_aliases: ``confusable_homoglyphs`` compatibility — ignored
            with a ``DeprecationWarning``. translit uses its own script
            detection engine.

    Returns:
        True if any confusable homoglyphs are present.

    Raises:
        TranslitError: If *target_script* is not ``"latin"``.

    Examples:
        >>> is_confusable("pаypal")  # Cyrillic а looks like Latin a
        True
        >>> is_confusable("paypal")  # all genuine Latin
        False
    """
    if greedy is not None:
        _warnings.warn(
            "The 'greedy' parameter is not supported by translit.is_confusable(); "
            "translit always checks all characters.",
            DeprecationWarning,
            stacklevel=2,
        )
    if preferred_aliases is not None:
        _warnings.warn(
            "The 'preferred_aliases' parameter is not supported by "
            "translit.is_confusable(); translit uses its own script detection.",
            DeprecationWarning,
            stacklevel=2,
        )
    return _is_confusable(text, target_script=target_script)


def is_ascii(text: str) -> bool:
    """True if all characters are in U+0000–U+007F.

    Args:
        text: Input string.

    Returns:
        True if the string is pure ASCII.

    Examples:
        >>> is_ascii("hello 123")
        True
        >>> is_ascii("café")
        False
    """
    return _is_ascii(text)


def is_normalized(
    text: str,
    *,
    form: NormalizationForm = "NFC",
) -> bool:
    """True if text is already in the specified normalization form.

    Args:
        text: Input string.
        form: Normalization form — "NFC", "NFD", "NFKC", or "NFKD".

    Returns:
        True if the string is already normalized.

    Examples:
        >>> is_normalized("café")  # NFC by default
        True
        >>> is_normalized("e\\u0301", form="NFC")  # NFD decomposed
        False
    """
    return _is_normalized(text, form=form)


# --- Stateful objects ---


class Slugifier:
    """Reusable configured slugifier. Call instance as slugifier(text) -> str.

    Examples:
        >>> s = Slugifier(separator="_", lang="de")
        >>> s("Ärger im Büro")
        'aerger_im_buero'
    """

    def __init__(
        self,
        *,
        separator: str = "-",
        lowercase: bool = True,
        max_length: int = 0,
        word_boundary: bool = False,
        save_order: bool = False,
        stopwords: Iterable[str] = (),
        regex_pattern: str | None = None,
        replacements: Iterable[tuple[str, str]] = (),
        allow_unicode: bool = False,
        lang: str | None = None,
        entities: bool = True,
        decimal: bool = True,
        hexadecimal: bool = True,
    ) -> None:
        self._inner = _Slugifier(
            separator=separator,
            lowercase=lowercase,
            max_length=max_length,
            word_boundary=word_boundary,
            save_order=save_order,
            stopwords=tuple(stopwords),
            regex_pattern=regex_pattern,
            replacements=tuple(replacements),
            allow_unicode=allow_unicode,
            lang=lang,
            entities=entities,
            decimal=decimal,
            hexadecimal=hexadecimal,
        )

    def __call__(self, text: str) -> str:
        return self._inner.slugify(text)

    def __repr__(self) -> str:
        return f"Slugifier(separator={self._inner.separator!r}, lang={self._inner.lang!r})"


class UniqueSlugifier:
    """Stateful slugifier that tracks previously generated slugs.

    Appends incrementing suffixes for uniqueness.
    Optional check callback for external uniqueness (e.g. database lookup).

    Examples:
        >>> u = UniqueSlugifier()
        >>> u("My Post")
        'my-post'
        >>> u("My Post")
        'my-post-1'
    """

    def __init__(
        self,
        *,
        check: object | None = None,
        separator: str = "-",
        lowercase: bool = True,
        max_length: int = 0,
        word_boundary: bool = False,
        save_order: bool = False,
        stopwords: Iterable[str] = (),
        regex_pattern: str | None = None,
        replacements: Iterable[tuple[str, str]] = (),
        allow_unicode: bool = False,
        lang: str | None = None,
        entities: bool = True,
        decimal: bool = True,
        hexadecimal: bool = True,
    ) -> None:
        self._inner = _UniqueSlugifier(
            check=check,
            separator=separator,
            lowercase=lowercase,
            max_length=max_length,
            word_boundary=word_boundary,
            save_order=save_order,
            stopwords=tuple(stopwords),
            regex_pattern=regex_pattern,
            replacements=tuple(replacements),
            allow_unicode=allow_unicode,
            lang=lang,
            entities=entities,
            decimal=decimal,
            hexadecimal=hexadecimal,
        )

    def __call__(self, text: str) -> str:
        return self._inner.slugify(text)

    def reset(self) -> None:
        """Clear the internal set of seen slugs."""
        self._inner.reset()

    def __repr__(self) -> str:
        return "UniqueSlugifier()"


class TextPipeline:
    """Composable, pre-compiled text cleaning pipeline.

    Operations execute in fixed optimal order regardless of construction order.

    Examples:
        >>> pipe = TextPipeline(normalize="NFC", fold_case=True, collapse_whitespace=True)
        >>> pipe("  Héllo  WÖRLD  ")
        'héllo wörld'
    """

    def __init__(
        self,
        *,
        normalize: NormalizationForm | None = None,
        transliterate: bool = False,
        lang: str | None = None,
        strict_iso9: bool = False,
        gost7034: bool = False,
        confusables: bool = False,
        strip_accents: bool = False,
        fold_case: bool = False,
        collapse_whitespace: bool = False,
        strip_control: bool | None = None,
        strip_zero_width: bool | None = None,
        demojize: bool = False,
    ) -> None:
        self._inner = _TextPipeline(
            normalize=normalize,
            transliterate=transliterate,
            lang=lang,
            strict_iso9=strict_iso9,
            gost7034=gost7034,
            confusables=confusables,
            strip_accents=strip_accents,
            fold_case=fold_case,
            collapse_whitespace=collapse_whitespace,
            strip_control=strip_control,
            strip_zero_width=strip_zero_width,
            demojize=demojize,
        )

    def __call__(self, text: str) -> str:
        return self._inner.process(text)

    @property
    def steps(self) -> list[tuple[str, str | None]]:
        """Return the ordered list of active pipeline steps.

        Each entry is a ``(step_name, parameter)`` tuple.  Steps are listed
        in execution order.  ``parameter`` is ``None`` for parameterless
        steps (e.g. ``fold_case``), or a string value for steps that accept
        one (e.g. ``("normalize", "NFC")``).

        Examples:
            >>> pipe = TextPipeline(normalize="NFC", fold_case=True)
            >>> pipe.steps
            [('normalize', 'NFC'), ('fold_case', None)]
        """
        return self._inner.steps()

    def explain(self) -> str:
        """Return a human-readable description of the pipeline.

        Examples:
            >>> pipe = TextPipeline(normalize="NFC", fold_case=True)
            >>> print(pipe.explain())
            TextPipeline with 2 steps:
              1. normalize (NFC)
              2. fold_case
        """
        step_list = self.steps
        if not step_list:
            return "TextPipeline with 0 steps (passthrough)"
        lines = [f"TextPipeline with {len(step_list)} step{'s' if len(step_list) != 1 else ''}:"]
        for i, (name, param) in enumerate(step_list, 1):
            if param is not None:
                lines.append(f"  {i}. {name} ({param})")
            else:
                lines.append(f"  {i}. {name}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return repr(self._inner)


# --- Preset pipeline metadata ---

PRESETS: dict[str, list[tuple[str, str | None]]] = {
    "security_clean": [
        ("normalize", "NFKC"),
        ("confusables", "latin"),
        ("strip_bidi", None),
        ("collapse_whitespace", None),
    ],
    "ml_normalize": [
        ("normalize", "NFKC"),
        ("demojize", "cldr"),
        ("strip_accents", None),
        ("fold_case", None),
        ("collapse_whitespace", None),
    ],
    "catalog_key": [
        ("normalize", "NFKC"),
        ("strip_bidi", None),
        ("transliterate", None),
        ("confusables", "latin"),
        ("strip_accents", None),
        ("fold_case", None),
        ("collapse_whitespace", None),
    ],
    "display_clean": [
        ("strip_bidi", None),
        ("collapse_whitespace", None),
    ],
    "search_key": [
        ("normalize", "NFKC"),
        ("strip_bidi", None),
        ("transliterate", None),
        ("strip_accents", None),
        ("fold_case", None),
        ("collapse_whitespace", None),
    ],
    "sort_key": [
        ("normalize", "NFKC"),
        ("strip_bidi", None),
        ("transliterate", None),
        ("fold_case", None),
        ("collapse_whitespace", None),
    ],
    "sanitize_user_input": [
        ("normalize", "NFKC"),
        ("strip_zalgo", None),
        ("confusables", "latin"),
        ("strip_bidi", None),
        ("collapse_whitespace", None),
    ],
    "strip_obfuscation": [
        ("normalize", "NFKC"),
        ("strip_zalgo", "max_marks=0"),
        ("confusables", "latin"),
        ("strip_bidi", None),
        ("strip_zero_width", None),
        ("demojize", "cldr"),
        ("strip_accents", None),
        ("collapse_whitespace", None),
    ],
}
"""Named preset pipelines and their ordered steps.

Each key is a preset function name; each value is a list of
``(step_name, parameter)`` tuples in execution order.  Use this to
audit exactly which transforms a preset applies.
"""


# --- Policy profiles ---

_POLICY_PROFILES: dict[str, dict[str, Any]] = {
    "scholarly_cyrillic_iso9": dict(
        normalize="NFKC",
        transliterate=True,
        strict_iso9=True,
        fold_case=True,
        collapse_whitespace=True,
    ),
    "library_catalog_key_eu": dict(
        normalize="NFKC",
        transliterate=True,
        confusables=True,
        strip_accents=True,
        fold_case=True,
        collapse_whitespace=True,
    ),
    "web_input_sanitize": dict(
        normalize="NFKC",
        confusables=True,
        collapse_whitespace=True,
    ),
    "ml_corpus_normalize": dict(
        normalize="NFKC",
        demojize=True,
        strip_accents=True,
        fold_case=True,
        collapse_whitespace=True,
    ),
    "search_index": dict(
        normalize="NFKC",
        transliterate=True,
        strip_accents=True,
        fold_case=True,
        collapse_whitespace=True,
    ),
}


def get_pipeline(profile: str) -> TextPipeline:
    """Return a TextPipeline configured for a named policy profile.

    Policy profiles are pre-defined parameter sets for common institutional
    and application workflows.  Each call returns a fresh ``TextPipeline``
    instance.

    Args:
        profile: Profile name (see :func:`list_profiles`).

    Returns:
        A configured ``TextPipeline``.

    Raises:
        TranslitError: If *profile* is not a known profile name.

    Examples:
        >>> pipe = get_pipeline("scholarly_cyrillic_iso9")
        >>> pipe("Москва")  # doctest: +SKIP
        'moskva'
    """
    try:
        kwargs = _POLICY_PROFILES[profile]
    except KeyError:
        avail = ", ".join(sorted(_POLICY_PROFILES))
        raise TranslitError(f"Unknown profile {profile!r}; available: {avail}") from None
    return TextPipeline(**kwargs)


def list_profiles() -> list[str]:
    """Return sorted names of available policy profiles.

    Returns:
        Sorted list of profile name strings.

    Examples:
        >>> "scholarly_cyrillic_iso9" in list_profiles()
        True
    """
    return sorted(_POLICY_PROFILES)


# --- Language profiles ---


def list_langs() -> list[str]:
    """Return available language codes for transliteration.

    Returns:
        Sorted list of language code strings (e.g. ["ar", "bg", "de", ...]).

    Raises:
        TranslitError: If the language table lock is poisoned.

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

    These languages benefit from ``context=True`` in :func:`transliterate`.
    Each entry has a ``context`` field in its :func:`lang_info` metadata
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
        Dict with ``name``, ``script``, and ``region`` keys.

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
        script: Script name (e.g. ``"Coptic"``) or :class:`Script` enum value.

    Returns:
        Dict with ``name``, ``default_lang``, and ``example`` keys.

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


# Incremented whenever the global transliteration tables change, so caches built
# by make_cached_transliterator can detect staleness and self-invalidate.
_mutation_generation: int = 0

# Conservative gate for the pure-ASCII fast path in transliterate(): False means
# *definitely no* global replacements are registered (so an ASCII string can be
# returned without crossing into Rust); True means there *may* be some, so the
# call must go through Rust where apply_replacements() runs. clear_replacements()
# resets it to False; remove_replacement() leaves it True (we can't cheaply tell
# from Python whether the table is now empty — staying True only costs a Rust
# round-trip that finds an empty table, never correctness).
_has_global_replacements: bool = False


def _bump_mutation_generation() -> None:
    global _mutation_generation
    _mutation_generation += 1


def register_lang(code: str, mappings: dict[str, str]) -> None:
    """Register or override a transliteration mapping for a language code.

    .. warning::
        This mutates **process-global** state consulted by every
        ``transliterate``/``slugify``/``catalog_key``/… call in the interpreter.
        Treat it as startup-only / single-writer configuration: do **not** call
        it from request-handling or library code in a multi-tenant process, where
        it would silently alter every other caller's output. Call
        :func:`seal_registrations` after startup to make further changes raise.

    Args:
        code: Language code string (e.g. "xx", "custom").
        mappings: Dict of source→replacement character mappings.

    Raises:
        TranslitError: If registrations are sealed, the language table lock is
            poisoned, or the mapping cannot be stored.

    Examples:
        >>> register_lang("xx", {"Ä": "Ae", "ä": "ae", "Ö": "Oe", "ö": "oe"})
        >>> transliterate("Ärger", lang="xx")
        'Aerger'
    """
    _register_lang(code, mappings)
    _bump_mutation_generation()


def register_replacements(replacements: dict[str, str]) -> None:
    """Register global pre-transliteration replacements.

    New entries are merged into the existing table. Existing keys are
    silently overwritten. Use :func:`clear_replacements` to wipe the
    table, or :func:`remove_replacement` to remove a single key.

    Replacements are applied to the input as a left-to-right pre-pass *before*
    the main transliteration tables, using longest-match-at-each-position
    semantics (the longest registered key matching at a position wins, and its
    output is not re-scanned, so replacements never cascade). Keys may be
    multi-character and may be ASCII.

    .. warning::
        Like :func:`register_lang`, this mutates **process-global** state shared
        by every caller. Treat it as startup-only / single-writer configuration
        and call :func:`seal_registrations` afterwards in multi-tenant processes.

    Args:
        replacements: Dict of source→replacement string mappings, applied
            before the main transliteration tables.

    Examples:
        >>> register_replacements({"™": "(tm)"})
        >>> transliterate("hello™")
        'hello(tm)'
        >>> clear_replacements()
    """
    global _has_global_replacements
    _register_replacements(replacements)
    if replacements:
        _has_global_replacements = True
    _bump_mutation_generation()


def remove_replacement(key: str) -> bool:
    """Remove a single global pre-transliteration replacement by key.

    Args:
        key: The source string to remove from the replacement table.

    Returns:
        True if the key was present and removed, False otherwise.

    Examples:
        >>> register_replacements({"©": "(c)"})
        >>> remove_replacement("©")
        True
        >>> remove_replacement("©")
        False
    """
    result = _remove_replacement(key)
    if result:  # only a real removal changes the tables
        _bump_mutation_generation()
    return result


def clear_replacements() -> None:
    """Clear all global pre-transliteration replacements.

    Examples:
        >>> register_replacements({"©": "(c)", "®": "(r)"})
        >>> clear_replacements()
    """
    global _has_global_replacements
    _clear_replacements()
    _has_global_replacements = False
    _bump_mutation_generation()


def seal_registrations() -> None:
    """Freeze the global registration tables (languages + replacements).

    After this is called, :func:`register_lang`, :func:`register_replacements`,
    :func:`remove_replacement`, and :func:`clear_replacements` raise
    :class:`TranslitError`. This is a one-way security latch (#64): the
    registration APIs mutate **process-global** state that every
    ``transliterate``/``slugify``/``catalog_key``/... call shares, so in a
    multi-tenant or web context an imported library or request handler could
    otherwise silently alter everyone's canonicalization. Configure your
    registrations at startup, then call ``seal_registrations()``.

    Examples:
        >>> register_lang("xx", {"Ä": "Ae"})
        >>> seal_registrations()
        >>> register_lang("yy", {"Ö": "Oe"})  # doctest: +SKIP
        Traceback (most recent call last):
        translit.TranslitError: register_lang: registration tables are sealed ...
    """
    _seal_registrations()


def registrations_sealed() -> bool:
    """Return True if :func:`seal_registrations` has been called."""
    return _registrations_sealed()


# --- Bulk / caching helpers (opt-in) -------------------------------------


def dedup_batch(
    texts: list[str],
    *,
    lang: str | None = None,
    target: str | None = None,
    errors: ErrorMode = "replace",
    replace_with: str = "[?]",
    strict_iso9: bool = False,
    gost7034: bool = False,
    tones: bool = False,
    context: bool = False,
) -> list[str]:
    """Transliterate a list, processing each *distinct* value only once.

    Equivalent in result to ``transliterate(texts, ...)`` but each unique input
    crosses into Rust a single time and the result is mapped back. This is a
    large win when values repeat — categorical columns such as city, author,
    publisher, or country — and is **stateless**: it holds no cache, so there is
    nothing to invalidate and every call reflects the *current* global tables.
    (Its output still depends on :func:`register_lang` /
    :func:`register_replacements` like any call — it simply cannot go stale.)

    Unique values are batched in chunks of 100,000 (the batch-size cap), so this
    also works for unique sets larger than a single ``transliterate`` call allows.

    Args:
        texts: List of input strings (repeats expected). Order is preserved.
        lang, target, errors, replace_with, strict_iso9, gost7034, tones,
            context: Same meaning as :func:`transliterate`; applied to every value.

    Returns:
        List of transliterations aligned 1:1 with *texts*.

    Examples:
        >>> dedup_batch(["café", "café", "naïve"])
        ['cafe', 'cafe', 'naive']
        >>> dedup_batch([])
        []
    """
    uniq = list(dict.fromkeys(texts))
    out: list[str] = []
    for i in range(0, len(uniq), _MAX_BATCH_SIZE):
        out.extend(
            transliterate(
                uniq[i : i + _MAX_BATCH_SIZE],
                lang=lang,
                target=target,
                errors=errors,
                replace_with=replace_with,
                strict_iso9=strict_iso9,
                gost7034=gost7034,
                tones=tones,
                context=context,
            )
        )
    mapping = dict(zip(uniq, out))
    return [mapping[t] for t in texts]


class CachedTransliterator(Protocol):
    """A cached single-string transliterator (the result of
    :func:`make_cached_transliterator`) that also exposes the underlying
    ``functools.lru_cache`` controls."""

    def __call__(self, text: str) -> str: ...

    def cache_clear(self) -> None:
        """Empty the cache."""
        ...

    def cache_info(self) -> Any:
        """Return the underlying ``functools.lru_cache`` ``CacheInfo``."""
        ...


def make_cached_transliterator(
    maxsize: int | None = 4096,
    *,
    lang: str | None = None,
    target: str | None = None,
    errors: ErrorMode = "replace",
    replace_with: str = "[?]",
    strict_iso9: bool = False,
    gost7034: bool = False,
    tones: bool = False,
    context: bool = False,
) -> CachedTransliterator:
    """Return an opt-in, LRU-cached single-string transliterator (fixed options).

    The returned callable takes one string and caches its result (bounded by
    *maxsize*; ``None`` = unbounded). Use it for a long-running process that
    transliterates many *repeated* single values over time with the same options
    — i.e. when you do **not** have the full list up front (otherwise prefer
    :func:`dedup_batch`, which is stateless and faster for bulk).

    The cache **self-invalidates**: the next call after any
    :func:`register_lang`, :func:`register_replacements`,
    :func:`remove_replacement`, or :func:`clear_replacements` clears it, so it
    never serves results that pre-date a table change.

    Transliteration options are fixed at construction time (build one cached
    transliterator per option set). The underlying ``functools.lru_cache``
    ``.cache_clear()`` and ``.cache_info()`` are exposed on the returned callable.

    Caching is a win only when inputs repeat; on unique-heavy input it adds
    overhead with no benefit. It is never enabled by default.

    Examples:
        >>> t = make_cached_transliterator()
        >>> t("café"), t("café")
        ('cafe', 'cafe')
    """

    @lru_cache(maxsize=maxsize)
    def _cached(text: str) -> str:
        return transliterate(
            text,
            lang=lang,
            target=target,
            errors=errors,
            replace_with=replace_with,
            strict_iso9=strict_iso9,
            gost7034=gost7034,
            tones=tones,
            context=context,
        )

    seen_generation = _mutation_generation

    @wraps(_cached)
    def cached(text: str) -> str:
        nonlocal seen_generation
        if _mutation_generation != seen_generation:
            _cached.cache_clear()
            seen_generation = _mutation_generation
        return _cached(text)

    cached.cache_clear = _cached.cache_clear  # type: ignore[attr-defined]
    cached.cache_info = _cached.cache_info  # type: ignore[attr-defined]
    return cast(CachedTransliterator, cached)


# --- Compatibility aliases ---

from translit._compat import (  # noqa: E402, F401  # noqa: E402, F401
    Slugify,
    UniqueSlugify,
    ascii_fold,
    slugify_de,
    slugify_el,
    slugify_filename,
    slugify_ru,
    slugify_unicode,
    slugify_url,
    unidecode,
)
from translit._text import Text  # noqa: E402

# --- Public API ---

__all__ = [
    # Transforms
    "transliterate",
    "dedup_batch",
    "make_cached_transliterator",
    "CachedTransliterator",
    "slugify",
    "normalize",
    "normalize_confusables",
    "sanitize_filename",
    "strip_accents",
    "fold_case",
    "collapse_whitespace",
    "demojize",
    "set_emoji_provider",
    # Precompiled pipelines
    "security_clean",
    "ml_normalize",
    "catalog_key",
    "display_clean",
    "search_key",
    "sort_key",
    "strip_bidi",
    "sanitize_user_input",
    "strip_obfuscation",
    # Zalgo detection and stripping
    "is_zalgo",
    "strip_zalgo",
    # Grapheme clusters
    "grapheme_len",
    "grapheme_split",
    "grapheme_truncate",
    # Hostname safety
    "is_safe_hostname",
    "SafeHostnameDetails",
    # Reverse transliteration
    "reverse_langs",
    # Encoding detection
    "detect_encoding",
    "decode_to_utf8",
    # Predicates
    "detect_scripts",
    "inspect_auto_lang",
    "is_mixed_script",
    "is_confusable",
    "is_ascii",
    "is_normalized",
    # Preset metadata
    "PRESETS",
    # Policy profiles
    "get_pipeline",
    "list_profiles",
    # Stateful / builders
    "Text",
    "Slugifier",
    "UniqueSlugifier",
    "TextPipeline",
    # Language profiles
    "list_langs",
    "list_scripts",
    "list_context_langs",
    "lang_info",
    "script_info",
    "LANG_META",
    "SCRIPT_META",
    "LangMeta",
    "ScriptMeta",
    "register_lang",
    "register_replacements",
    "remove_replacement",
    "clear_replacements",
    "seal_registrations",
    "registrations_sealed",
    # Enums, protocols & constants
    "EmojiProvider",
    "NF",
    "Script",
    "LANG_AM",
    "LANG_AR",
    "LANG_AS",
    "LANG_BAN",
    "LANG_BAX",
    "LANG_BG",
    "LANG_BN",
    "LANG_BO",
    "LANG_BUG",
    "LANG_CA",
    "LANG_CHR",
    "LANG_CJM",
    "LANG_COP",
    "LANG_CS",
    "LANG_CY",
    "LANG_DA",
    "LANG_DE",
    "LANG_DV",
    "LANG_EL",
    "LANG_ES",
    "LANG_ET",
    "LANG_FA",
    "LANG_FI",
    "LANG_FR",
    "LANG_GA",
    "LANG_GU",
    "LANG_HE",
    "LANG_HI",
    "LANG_HR",
    "LANG_HU",
    "LANG_HY",
    "LANG_IS",
    "LANG_IT",
    "LANG_JA",
    "LANG_JV",
    "LANG_KA",
    "LANG_KHB",
    "LANG_KM",
    "LANG_KN",
    "LANG_KO",
    "LANG_LIS",
    "LANG_LO",
    "LANG_LT",
    "LANG_LV",
    "LANG_ML",
    "LANG_MN",
    "LANG_MNI",
    "LANG_MR",
    "LANG_MT",
    "LANG_MY",
    "LANG_NE",
    "LANG_NL",
    "LANG_NO",
    "LANG_NOD",
    "LANG_NQO",
    "LANG_OR",
    "LANG_PA",
    "LANG_PL",
    "LANG_PT",
    "LANG_RO",
    "LANG_RU",
    "LANG_SA",
    "LANG_SAT",
    "LANG_SI",
    "LANG_SK",
    "LANG_SL",
    "LANG_SQ",
    "LANG_SR",
    "LANG_SU",
    "LANG_SV",
    "LANG_SYR",
    "LANG_TA",
    "LANG_TDD",
    "LANG_TE",
    "LANG_TH",
    "LANG_TL",
    "LANG_TR",
    "LANG_TZM",
    "LANG_UK",
    "LANG_VAI",
    "LANG_VI",
    "LANG_ZH",
    # Drop-in compatibility aliases
    "casefold",
    "remove_accents",
    # Compatibility aliases (Unidecode)
    "unidecode",
    "ascii_fold",
    # Compatibility aliases (awesome-slugify)
    "Slugify",
    "UniqueSlugify",
    "slugify_url",
    "slugify_filename",
    "slugify_unicode",
    "slugify_ru",
    "slugify_de",
    "slugify_el",
    # Exception
    "TranslitError",
]

# ---------------------------------------------------------------------------
# Make the module itself callable: import translit; translit("Москва")
# ---------------------------------------------------------------------------


class _CallableModule(_stdlib_types.ModuleType):
    """Make ``import translit; translit(...)`` a shorthand for ``transliterate()``."""

    def __call__(self, text: str, **kwargs: Any) -> str:
        return transliterate(text, **kwargs)

    def __repr__(self) -> str:
        return f"<module {self.__name__!r} (callable) from {self.__file__!r}>"


# Mutate the existing module's __class__ in-place so that __dict__ (and
# therefore functions' __globals__) stays identical.  This keeps
# unittest.mock.patch working correctly.
_sys.modules[__name__].__class__ = _CallableModule
