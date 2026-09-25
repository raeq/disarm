"""Public API: transform functions, stateful classes, and registration helpers.

This module holds the implementation of every public name re-exported from the
``disarm`` package root (see ``disarm/__init__.py``).  The precompiled
pipeline presets live in ``disarm._presets``.
"""

# The implementation is split by concern across the private `_api_*` modules. This
# module keeps the functions with `@overload` stubs (`typing.get_overloads` finds
# them by their declaring module) and the stateful surface (the classes, the
# registration tables and the cache that watches them), and re-exports everything
# else under the names it always had, so every import from `disarm._api` still
# resolves. The imports below are this module's namespace as much as its
# dependencies, hence the file-wide F401 waiver.
# ruff: noqa: F401

from __future__ import annotations

import threading
import warnings as _warnings
from collections.abc import Iterable
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Protocol, cast, overload

from disarm._api_common import _MAX_GRAPHEME_SPLIT_INPUT as _MAX_GRAPHEME_SPLIT_INPUT
from disarm._api_common import _MAX_I64 as _MAX_I64
from disarm._api_common import _checked_i64_max as _checked_i64_max
from disarm._api_common import _norm_form as _norm_form
from disarm._api_common import _target_script as _target_script
from disarm._api_common import _validate_batch as _validate_batch
from disarm._api_confusables import confusable_coverage as confusable_coverage
from disarm._api_confusables import decode_smuggled as decode_smuggled
from disarm._api_confusables import edit_distance as edit_distance
from disarm._api_confusables import find_confusables as find_confusables
from disarm._api_confusables import find_key_collisions as find_key_collisions
from disarm._api_confusables import find_unmapped_confusables as find_unmapped_confusables
from disarm._api_confusables import is_confusable as is_confusable
from disarm._api_confusables import nearest_match as nearest_match
from disarm._api_confusables import unmapped_confusables as unmapped_confusables
from disarm._api_emoji import demojize as demojize
from disarm._api_emoji import replace_emoji as replace_emoji
from disarm._api_emoji import set_emoji_provider as set_emoji_provider
from disarm._api_encoding import decode_to_utf8 as decode_to_utf8
from disarm._api_encoding import detect_encoding as detect_encoding
from disarm._api_encoding import escape_html as escape_html
from disarm._api_encoding import percent_encode as percent_encode
from disarm._api_encoding import strip_log_injection as strip_log_injection
from disarm._api_graphemes import grapheme_len as grapheme_len
from disarm._api_graphemes import grapheme_split as grapheme_split
from disarm._api_graphemes import grapheme_truncate as grapheme_truncate
from disarm._api_graphemes import grapheme_width as grapheme_width
from disarm._api_graphemes import terminal_width as terminal_width
from disarm._api_scripts import _SCRIPT_BY_NAME as _SCRIPT_BY_NAME
from disarm._api_scripts import detect_scripts as detect_scripts
from disarm._api_scripts import has_bidi_conflict as has_bidi_conflict
from disarm._api_scripts import has_bidi_control as has_bidi_control
from disarm._api_scripts import inspect_auto_lang as inspect_auto_lang
from disarm._api_scripts import is_mixed_script as is_mixed_script
from disarm._api_security import has_anomalies as has_anomalies
from disarm._api_security import inspect_anomalies as inspect_anomalies
from disarm._api_security import is_suspicious_hostname as is_suspicious_hostname
from disarm._api_text import casefold as casefold
from disarm._api_text import collapse_whitespace as collapse_whitespace
from disarm._api_text import fold_case as fold_case
from disarm._api_text import is_ascii as is_ascii
from disarm._api_text import is_canonical as is_canonical
from disarm._api_text import is_case_fold_stable as is_case_fold_stable
from disarm._api_text import is_normalized as is_normalized
from disarm._api_text import is_normalized_stream_safe as is_normalized_stream_safe
from disarm._api_text import normalize_confusables as normalize_confusables
from disarm._api_text import sanitize_filename as sanitize_filename
from disarm._api_text import stream_safe as stream_safe
from disarm._api_text import strip_control_chars as strip_control_chars
from disarm._api_text import strip_zero_width_chars as strip_zero_width_chars
from disarm._api_translit import _build_slug_kwargs as _build_slug_kwargs
from disarm._api_translit import find_untranslatable as find_untranslatable
from disarm._api_translit import lang_info as lang_info
from disarm._api_translit import list_context_langs as list_context_langs
from disarm._api_translit import list_langs as list_langs
from disarm._api_translit import list_scripts as list_scripts
from disarm._api_translit import reverse_langs as reverse_langs
from disarm._api_translit import script_info as script_info
from disarm._boundary import (
    # Resource limit — read from the Rust single source of truth, never
    # re-declared, to prevent silent drift (#200).
    _MAX_BATCH_SIZE,
    AnomalyReport,
    HostnameAnalysis,
    # Exception hierarchy (#183): base + categorised subclasses
    InvalidArgumentError,
    # Collision report object (#620)
    KeyCollision,
    # Reusable anomaly lexicon handle (HAI-SDLC 6.1)
    Lexicon,
    NearestMatch,
    ResourceLimitError,
    SmuggledPayload,
    _clear_replacements,
    _collapse_whitespace,
    # Encoding detection
    _confusable_coverage,
    _decode_smuggled,
    _decode_to_utf8,
    _demojize,
    _detect_encoding,
    # Predicates
    _detect_scripts,
    _edit_distance,
    _escape_html,
    _find_confusables,
    _find_key_collisions,
    _find_unmapped_confusables,
    # Untranslatable scan (#184)
    _find_untranslatable,
    _fold_case,
    # Grapheme cluster functions
    _grapheme_len,
    _grapheme_split,
    _grapheme_truncate,
    _grapheme_width,
    # Anomaly detection (#389)
    _has_anomalies,
    _has_anomalies_lex,
    _has_bidi_conflict,
    _has_bidi_control,
    _inspect_anomalies,
    _inspect_anomalies_lex,
    _inspect_auto_lang,
    _is_ascii,
    _is_canonical,
    _is_case_fold_stable,
    _is_confusable,
    _is_mixed_script,
    _is_normalized,
    _is_normalized_stream_safe,
    # Hostname safety
    _is_suspicious_hostname,
    # Language profiles
    _list_langs,
    _nearest_match,
    _normalize,  # noqa: F401  (used by normalize() and internal pipelines)
    _normalize_batch,
    _normalize_confusables,
    _percent_encode,
    _register_lang,
    _register_replacements,
    _registrations_sealed,
    _remove_replacement,
    _replace_emoji,
    # Reverse transliteration
    _reverse_langs,
    _reverse_transliterate,
    _sanitize_filename,
    # WTF-8 -> UTF-8 scrub for surrogate-laced constructor inputs (#476 follow-up)
    _scrub,
    _seal_registrations,
    # Emoji provider
    _set_emoji_provider,
    _set_transliterate_fallback,
    # Stateful
    _Slugifier,
    _slugify,
    _slugify_batch,
    _stream_safe,
    _strip_accents,
    _strip_accents_batch,
    _strip_control_chars,
    _strip_log_injection,
    _strip_zero_width_chars,
    # #476: the surrogate-boundary guard, for the class-based entrypoints (the module
    # loop in _boundary wraps only free functions, not class methods).
    _surrogate_safe,
    _terminal_width,
    _TextPipeline,
    # Core transforms (Rust implementations)
    _transliterate,
    # Batch APIs (single PyO3 boundary crossing for N strings)
    _transliterate_batch,
    _transliterate_context,
    _transliterate_entry,
    _UniqueSlugifier,
    _unmapped_confusables,
    # Semantic argument-combination validation (single source of truth, #231)
    _validate_transliterate_args,
)
from disarm._enums import (
    LANG_META,
    SCRIPT_META,
    Component,
    ConfusableCoverage,
    LangMeta,
    Script,
    ScriptMeta,
)
from disarm._types import (
    NF,
    EmojiProvider,
    ErrorMode,
    NormalizationForm,
    Platform,
    TransliterateErrorMode,
)

# The module-level constants the modules above define, restated so that this
# module's `__annotations__` still lists them. A bare annotation binds nothing: the
# value is the import's, and mypy's no-redef is about the restatement, not a rebind.
_MAX_GRAPHEME_SPLIT_INPUT: int  # type: ignore[no-redef]
_MAX_I64: int  # type: ignore[no-redef]
_SCRIPT_BY_NAME: dict[str, Script]  # type: ignore[no-redef]


# --- Core transforms ---


@overload
def _transliterate_dispatch(
    text: str,
    *,
    lang: str | None = ...,
    target: str | None = ...,
    errors: TransliterateErrorMode = ...,
    replace_with: str = ...,
    strict_iso9: bool = ...,
    gost7034: bool = ...,
    tones: bool = ...,
    context: bool = ...,
) -> str: ...


@overload
def _transliterate_dispatch(
    text: list[str],
    *,
    lang: str | None = ...,
    target: str | None = ...,
    errors: TransliterateErrorMode = ...,
    replace_with: str = ...,
    strict_iso9: bool = ...,
    gost7034: bool = ...,
    tones: bool = ...,
    context: bool = ...,
) -> list[str]: ...


def _transliterate_dispatch(
    text: str | list[str],
    *,
    lang: str | None = None,
    target: str | None = None,
    errors: TransliterateErrorMode = "replace",
    replace_with: str = "[?]",
    strict_iso9: bool = False,
    gost7034: bool = False,
    tones: bool = False,
    context: bool = False,
) -> str | list[str]:
    """Phonetic, standards-based romanization (Unicode → ASCII transliteration).

    This is **not** TR39 *visual* confusable mapping. ``transliterate`` romanizes
    by sound/standard (Cyrillic ``р`` → ``r``, BGN/PCGN by default), so it will
    *not* reverse a homoglyph spoof — it leaves a look-alike substitution
    readable. To fold visual look-alikes for homoglyph defense (Cyrillic
    ``р`` → ``p``), use `normalize_confusables` or `strip_obfuscation`
    instead.

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
                *lang*. Use `reverse_langs` to list supported languages.
        errors: How to handle untransliterable characters.
                "replace" — substitute with *replace_with*.
                "ignore" — silently drop.
                "preserve" — keep the original character.
                "strict" — raise ``DisarmError`` on the first untranslatable
                character, reporting it and its byte offset (#184). Forward-only:
                not supported with ``context=True`` or ``target=...``. Use
                `find_untranslatable` to get *all* of them without raising.
        replace_with: Replacement string when errors="replace". An empty string
                      (``""``) is equivalent to ``errors="ignore"`` — the
                      character is silently dropped. This matches the behaviour
                      of the Unidecode library.
        strict_iso9: Use a scholarly **ASCII** Cyrillic transliteration with
                     consistent 1:1-style overrides (e.g. й→j, ю→ju, я→ja).
                     NOTE: this is *not* the diacritic ISO 9:1995 standard
                     (which uses ž, č, š, ŝ, h). disarm's tables are ASCII-only
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
                 dictionaries (see ``bootstrap_dicts.sh`` / ``DISARM_DICT_DIR``).
                 Forward-only: mutually exclusive with *target*, and cannot be
                 combined with *tones*.

    Returns:
        ASCII transliteration of the input. Returns ``str`` when given ``str``,
        ``list[str]`` when given ``list[str]``.

    Raises:
        DisarmError: If an internal Rust error occurs (e.g. invalid
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
    # Hot path (#277 lever 4): scalar str, no reverse/context dispatch. The
    # conflict-matrix validation below is a provable no-op when `target` and
    # `context` are both absent (every branch requires one of them), and every
    # remaining check (lang, errors, strict_iso9 × gost7034) runs inside
    # `_transliterate` itself (#130) — so jumping straight to the binding is
    # behavior-identical. `type(text) is str` (not isinstance) keeps str
    # subclasses on the general path below, which handles them as before.
    if type(text) is str and target is None and not context:
        return _transliterate(text, lang, errors, replace_with, strict_iso9, gost7034, tones)

    # Resolve conflicting kwargs once, before the str/list dispatch, so scalar
    # and batch inputs behave identically (#69). The conflict matrix lives in
    # the Rust core (single source of truth, #231); this is a thin call into it.
    #
    # contract: this validation MUST run before any dispatch onto a path that
    # uses `target` or `context`. The `cast(ErrorMode, errors)` calls on the
    # context paths are sound *only* because this call has already rejected the
    # strict+context combination (#184); reordering or skipping it on those
    # paths would make those casts unsound.
    #
    # perf (#277): the call is gated — every branch of the Rust conflict matrix
    # requires `target` or `context`, so when both are absent the validator is
    # a provable no-op and the extra PyO3 crossing is pure overhead. The hot
    # forward path's own validation (lang, errors, strict_iso9 × gost7034)
    # lives inside `_transliterate` itself (#130) and still runs on every call.
    if target is not None or context:
        _validate_transliterate_args(
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
                    # not "strict" here (conflict matrix rejects strict+context, #184)
                    errors=cast(ErrorMode, errors),
                    replace_with=replace_with,
                    strict_iso9=strict_iso9,
                    gost7034=gost7034,
                )
                for t in text
            ]
        if target is not None:
            return [_reverse_transliterate(t, lang=target) for t in text]
        # Positional call into the private binding (#277): PyO3 kwarg parsing is
        # measurably slower than positional extraction. Order matches the Rust
        # signature: (texts, lang, errors, replace_with, strict_iso9, gost7034, tones).
        return _transliterate_batch(text, lang, errors, replace_with, strict_iso9, gost7034, tones)

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
            # errors is provably not "strict" here — _check_transliterate_conflicts
            # rejects errors="strict" with context=True (#184).
            errors=cast(ErrorMode, errors),
            replace_with=replace_with,
            strict_iso9=strict_iso9,
            gost7034=gost7034,
        )

    # No Python-side ASCII short-circuit (#197): the Rust core validates `lang`
    # first and has its own borrowed ASCII fast-path (`Cow::Borrowed`), so every
    # call goes through it. A binding-side fast-path here skipped that validation
    # (a typo'd `lang` was silently accepted on ASCII input, re-opening #68) and
    # duplicated the core's own optimization — a per-binding drift liability.
    # Positional call into the private binding (#277) — see batch path note.
    return _transliterate(text, lang, errors, replace_with, strict_iso9, gost7034, tones)


# ── #277 Phase B: single-crossing public entry point ──
# At runtime `transliterate` is the Rust fastcall entry: the common shape
# (exact str, forward, no context) runs with ONE Python→native call and
# Rust-side keyword defaults (zero extraction cost on bare calls). Every other
# shape (list batch, str subclass, target=, context=True, type errors)
# delegates back to _transliterate_dispatch above, which is unchanged.
# Type checkers see the overloaded Python signature as the source of truth;
# mypy treats the `else` branch as unreachable under TYPE_CHECKING.
_set_transliterate_fallback(_transliterate_dispatch)
if TYPE_CHECKING:
    transliterate = _transliterate_dispatch
else:
    transliterate = _transliterate_entry


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
    default: str | None = ...,
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
    default: str | None = ...,
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
    default: str | None = None,
) -> str | list[str]:
    """Generate a URL-safe slug from Unicode text.

    Full pipeline: decode entities → transliterate → lowercase →
    strip non-alphanumeric → collapse separators → apply stopwords/max_length.

    Shares python-slugify's core keyword parameters (``separator``,
    ``max_length``, ``word_boundary``, ``save_order``, ``stopwords``,
    ``lowercase``, etc.), so ``slugify(text, ...)`` calls port directly. Note
    that disarm makes every parameter past *text* keyword-only, whereas
    python-slugify accepts some positionally.

    Args:
        text: Input Unicode string.
        separator: Character(s) between slug words, inserted as given: the words
            are screened and the separator is not.
        lowercase: Convert to lowercase.
        max_length: Maximum slug length in **bytes** (0 = unlimited). The unit is
            right for the filesystem and URL limits it exists for; use
            `grapheme_truncate` when you want a character count instead.

            With ``allow_unicode=True`` the cut lands on a **grapheme-cluster**
            boundary, so it never splits a cluster: a Devanagari conjunct or a
            Hangul syllable is kept whole or dropped whole. A budget too small
            for the first cluster therefore yields an empty slug — handle it the
            same way you handle an all-stopword input, or pass ``default``.

            A cut never leaves a trailing separator, whole or partial, or a
            trailing ZWJ or ZWNJ.
        word_boundary: When truncating via max_length, cut at word boundaries:
            the slug keeps the whole words that fit, up to the first that does
            not. When not even the first word fits, it is cut as if
            ``word_boundary`` were off.
        save_order: When ``True``, only leading and trailing stopwords are
            removed; interior stopwords are kept so relative word order is
            preserved (python-slugify compatible). When ``False`` (default),
            all matching stopwords are removed wherever they appear. (#118)
        stopwords: Words to remove from the slug, compared case-insensitively
            whether or not ``lowercase`` is set. With ``separator=""`` the slug
            has no words, and nothing is removed.
        regex_pattern: Custom regex for stripping characters.
        replacements: Pre-transliteration (old, new) substitution pairs.
        allow_unicode: Keep non-ASCII **letters, digits and combining marks**
            instead of transliterating to ASCII. Everything else is a separator,
            as it is on the ASCII path: format characters (bidi controls, ZWSP,
            ZWNBSP, soft hyphen, the tag block), private use, noncharacters,
            surrogates, punctuation, symbols and emoji. That includes the
            letter-like symbols such as the circled Latin letters (U+24B6),
            which are ``So`` although Unicode calls them alphabetic. This matches
            ``django.utils.text.slugify(allow_unicode=True)``, which keeps
            ``\\w`` — with two deliberate additions Django does not make:

            * **Combining marks** (``M*``) are kept, capped at two per base
              character. Django drops them, which breaks Devanagari and Arabic;
              two is the cap the ``strip_zalgo`` presets use and what Vietnamese
              ``ệ`` needs. The cap counts the base's own marks, over its
              decomposition: ``à`` takes one more. A precomposed character that
              already carries more than two, such as polytonic Greek U+1F82
              with three, is kept whole and takes none.
            * **ZWJ and ZWNJ** are kept *between* two other kept characters.
              Both are orthographically required — ZWNJ separates a Persian
              ``می`` prefix from its verb, ZWJ forms a Devanagari conjunct — so
              dropping them changes the word. They are never emitted at the start
              or end of a token, where they would be invisible padding.
        lang: Language code for transliteration (e.g. "de", "ru", "auto").
        entities: Decode HTML entities before processing.
        decimal: Decode HTML decimal entities (&#123;).
        hexadecimal: Decode HTML hex entities (&#x7B;).
        default: Fallback when the slug would be empty — i.e. the input has no
            sluggable characters (emoji, punctuation, or zero-width only). The
            value is itself run through the same slug pipeline (#193), so it is
            sanitized to a URL-safe slug and is subject to the same
            ``max_length`` truncation as normal output; a ``default`` that has no
            sluggable characters therefore yields the empty string. When ``None``
            (the default), the empty string is returned, preserving prior
            behaviour. Use this to avoid the routing hazard of empty slugs
            colliding on one URL (#97).

    Returns:
        URL-safe slug string (or the sanitized ``default`` when it would
        otherwise be empty). Returns ``list[str]`` when given ``list[str]``.

    Raises:
        ValueError: If ``max_length`` is negative (validated for both scalar and
            list input, #193).
        TypeError: If ``text`` is neither ``str`` nor ``list[str]``.
        InvalidArgumentError: If ``lang`` is not a known language code (#68,
            #257), as in every binding.
        DisarmError: If an internal Rust error occurs (e.g. an invalid
            ``regex_pattern``).

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
        >>> slugify("🔥🔥🔥")
        ''
        >>> slugify("🔥🔥🔥", default="n-a")
        'n-a'
        >>> slugify("🔥", default="N/A")  # default is sanitized, not returned raw
        'n-a'

    **The output can be the empty string (#728).**

    Measured at Unicode 15.0.0, **243,370** single
    characters reduce to ``""`` here (105,902 excluding the Private Use
    Area), and so does every string built from them. A caller keying a table
    on this has all of them, plus "no value", competing for one slot.

    There is no ``on_empty`` here: this returns text rather than a key. The
    four key builders take one.
    """
    _sw = stopwords if isinstance(stopwords, (tuple, list)) else list(stopwords)
    _rp = replacements if isinstance(replacements, (tuple, list)) else list(replacements)
    # #120: shared kwargs dict avoids repeating 13 keyword arguments twice.
    _kw = _build_slug_kwargs(
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

    # max_length's non-negative contract is enforced by the Rust core (#231):
    # both the scalar (`_slugify`) and batch (`_slugify_batch`) entrypoints accept
    # a signed integer and raise InvalidArgumentError, so the two paths behave
    # identically without a duplicate Python check.

    # Sanitize the empty-slug fallback through the *same* slug pipeline (#193).
    # `default` is documented as a slug, so a caller-derived value (e.g. a
    # username or filename) must not smuggle path-traversal or `?#/` into output
    # that callers assume is URL-safe. Running it through `_kw` also applies
    # `max_length`, so the length guarantee holds for the fallback too. Computed
    # once here (not per empty batch element); it may itself be empty if
    # `default` has no sluggable characters.
    sanitized_default = (
        _slugify(default, **_kw) if default is not None else None  # type: ignore[arg-type]
    )

    if isinstance(text, list):
        _validate_batch(text, "slugify")
        result = _slugify_batch(text, **_kw)  # type: ignore[arg-type]
        if sanitized_default is not None:
            return [s if s else sanitized_default for s in result]
        return result

    if not isinstance(text, str):
        raise TypeError(f"slugify() expects str or list[str], got {type(text).__name__}")
    slug = _slugify(text, **_kw)  # type: ignore[arg-type]
    if sanitized_default is not None and not slug:
        return sanitized_default
    return slug


@overload
def normalize(text: str, *, form: NormalizationForm = ...) -> str: ...


@overload
def normalize(text: list[str], *, form: NormalizationForm = ...) -> list[str]: ...


def normalize(
    text: str | list[str],
    *,
    form: NormalizationForm | NF = "NFC",
) -> str | list[str]:
    """Unicode normalization.

    Accepts a single string or a list of strings.

    Note:
        **Unicode version.** disarm implements **UCD 17.0.0**. Results differ from
        the standard library's ``unicodedata.normalize`` for code points assigned
        after the *host interpreter's* ``unicodedata.unidata_version`` — one code
        point on a UCD 16.0.0 host, more on an older one. Every divergence is
        disarm being more current, never wrong, but a pipeline that canonicalizes
        with one and validates with the other will disagree about which strings are
        normalized. `disarm.UNICODE_VERSION` reports which UCD this build normalizes
        against (#645), so the comparison against ``unicodedata.unidata_version``
        can be made at runtime rather than inferred from behaviour.

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
    # `form` is validated once in the Rust core (#185), which also has its own
    # ASCII fast path (ASCII is invariant under all four forms) — so there is no
    # binding-side form check or ASCII short-circuit left to keep in sync.
    if isinstance(text, list):
        _validate_batch(text, "normalize")
        return _normalize_batch(text, form=_norm_form(form))
    if not isinstance(text, str):
        raise TypeError(f"normalize() expects str or list[str], got {type(text).__name__}")
    return _normalize(text, form=_norm_form(form))


@overload
def strip_accents(text: str) -> str: ...


@overload
def strip_accents(text: list[str]) -> list[str]: ...


def strip_accents(text: str | list[str]) -> str | list[str]:
    """Remove diacritical marks while preserving base characters.

    NFD decompose → strip combining marks → NFC recompose.
    Accepts a single string or a list of strings.

    **Destructive wherever a combining mark carries meaning, which is not only the
    Indic scripts** (#624, #761). A Latin acute and a Devanagari vowel sign are both
    general category ``Mn``, so both are removed — but in Latin an ``Mn`` is
    decoration and elsewhere it is part of the letter. ``José`` → ``Jose`` is
    readable. These are not::

        বাংলা      → বল        Bengali, the vowel signs carry the word
        हिन्दी      → हनद        Devanagari
        မြန်မာ      → မနမ        Myanmar
        かばん      → かはん      Japanese: the dakuten is the difference between
                                 ば /ba/ and は /ha/, so this is a different word
        Чайковский → Чаиковскии  Russian: й is a letter, not и with a mark; ё → е

    Kana and Cyrillic are the two an "Indic scripts" warning sends a reader past.
    In kana the dakuten and handakuten are voicing, not decoration; in Cyrillic
    ``й`` and ``ё`` are letters of the alphabet that happen to decompose.

    Use this for identifiers, filenames and search keys — where a deliberate
    many-to-one collapse is the point — and not for body text in any script whose
    marks are load-bearing. See `Limitations` (docs/limitations.md).

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


#: Alias for `strip_accents` — common name in sklearn and ML ecosystems.
remove_accents = strip_accents


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
        default: str | None = None,
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
        # Empty-slug fallback, threaded through the stateful forms too (#193):
        # the routing hazard #97 fixed on the function form was still present on
        # the classes, the typical choice for long-lived web handlers. Sanitize
        # it once here through this slugifier's own config (separator, lang,
        # max_length, …) so it is URL-safe and length-bounded like real output.
        # `_scrub` first (#476 follow-up): the boundary contract says no public
        # entrypoint raises on a lone surrogate, and `default=` crosses to Rust here in
        # `__init__` — outside the `@_surrogate_safe`-guarded `__call__`.
        self._default: str | None = (
            self._inner.slugify(_scrub(default)) if default is not None else None
        )

    @_surrogate_safe
    def __call__(self, text: str) -> str:
        slug: str = self._inner.slugify(text)
        if self._default is not None and not slug:
            return self._default
        return slug

    def __repr__(self) -> str:
        return f"Slugifier(separator={self._inner.separator!r}, lang={self._inner.lang!r})"


class UniqueSlugifier:
    """Stateful slugifier that tracks previously generated slugs.

    Appends incrementing suffixes for uniqueness.
    Optional check callback for external uniqueness (e.g. database lookup).

    With ``max_length`` set, a suffixed slug is cut to fit by shortening the
    base, never the suffix, and the cut is the slug's own: no trailing
    separator or joiner is left before the suffix, and at least one character
    of the base is kept. When the suffix leaves no room for one,
    ``InvalidArgumentError`` is raised rather than returning ``-1``.

    An input with nothing sluggable gives the empty slug, every time: it is
    not suffixed, not recorded, and ``check`` is not called for it. Pass
    ``default`` to get a unique fallback instead.

    One instance can be shared between threads: calls are serialised, so each
    waits for the one in progress, ``check`` included. ``check`` must not call
    the same instance; that raises ``RuntimeError``.

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
        default: str | None = None,
    ) -> None:
        _cfg = dict(
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
        self._inner = _UniqueSlugifier(check=check, **_cfg)  # type: ignore[arg-type]
        # Empty-slug fallback for the stateful unique form (#193). When an input
        # has no sluggable characters we route to `default` *through the inner
        # slugifier*, so it is both sanitized (URL-safe, length-bounded) AND made
        # unique — two unsluggable inputs become e.g. "n-a", "n-a-1" rather than
        # colliding on one default, the routing hazard #97 addressed.
        #
        # Emptiness is detected with a stateless companion (`_probe`) configured
        # identically: calling the unique `_inner` on the empty input would itself
        # consume a uniqueness slot and suffix the empty slug to "-1" (truthy),
        # masking the fallback. The probe sees the raw empty slug without mutating
        # the unique state, so `_inner` is fed exactly once per call.
        # The default is slugified lazily through `_inner` in `__call__` (eager
        # slugification here would consume a uniqueness slot), so `_scrub` the raw
        # surrogate-laced form now — `@_surrogate_safe` on `__call__` only scrubs its
        # `text` argument, not this stored attribute (#476 follow-up).
        self._default: str | None = _scrub(default) if default is not None else None
        self._probe: Slugifier | None = (
            Slugifier(**_cfg) if default is not None else None  # type: ignore[arg-type]
        )
        # The inner object holds PyO3's exclusive borrow while it calls `check`, and a
        # `check` doing I/O gives up the GIL, so a second thread found it borrowed and
        # raised `RuntimeError: Already borrowed` (F6 of the TLA+ model in
        # formal/tla/Concurrency). Calls are serialised here instead, which uniqueness
        # needs anyway. Reentrant so that a `check` calling back in still gets that
        # RuntimeError rather than deadlocking on this lock.
        self._lock = threading.RLock()

    @_surrogate_safe
    def __call__(self, text: str) -> str:
        with self._lock:
            probe = self._probe
            if probe is not None and self._default is not None and not probe(text):
                return self._inner.slugify(self._default)
            return self._inner.slugify(text)

    def reset(self) -> None:
        """Clear the internal set of seen slugs."""
        with self._lock:
            self._inner.reset()

    def __repr__(self) -> str:
        return "UniqueSlugifier()"


class TextPipeline:
    """Composable, pre-compiled text cleaning pipeline.

    Operations execute in fixed optimal order regardless of construction order.

    Two security-focused steps run early in the order: ``strip_zalgo`` caps
    excessive combining marks (``strip_zalgo=max_marks``), and ``strip_bidi``
    removes bidirectional override/format characters. Both run right after
    ``normalize`` and before ``demojize``.

    ``strip_zalgo`` is the one flag here whose off switch is not ``False``, and
    ``0`` is not it (#958). The value is a **cap** on combining marks per base
    character, so ``strip_zalgo=0`` permits none and removes every diacritic in the
    text — ``café`` leaves as ``cafe``. Off is ``None``, the default, which omits
    the step from the compiled pipeline entirely. A threshold that leaves ordinary
    accented text alone and still cuts a zalgo stack is a small positive number,
    which is what the bare `strip_zalgo` function defaults to. The same literal
    reads the other way in `PRESETS`: ``("strip_zalgo", None)`` there names a step
    that **runs**, at that default cap.

    This constructor takes individual step flags only; there is **no**
    ``preset=`` argument. To obtain a pre-configured pipeline for a named policy
    profile (e.g. ``scholarly_cyrillic_iso9``), call `get_pipeline`
    instead — it returns a ready-to-use ``TextPipeline``. A profile runs its steps
    again until the output stops changing; a pipeline built here runs them once, as
    composed, so the two agree wherever one pass is already a fixed point.

    ``digit_policy`` is the policy the ``confusables`` step folds digits under
    (``"numeric"``, ``"tr39"`` or ``"preserve"``), fixed here at construction the way
    `get_pipeline` fixes it for a profile (#646). It is rejected, not ignored, unless
    ``confusables=True``: a setting that would never run is refused rather than kept.

    Examples:
        >>> pipe = TextPipeline(normalize="NFC", fold_case=True, collapse_whitespace=True)
        >>> pipe("  Héllo  WÖRLD  ")
        'héllo wörld'
        >>> TextPipeline(confusables=True, digit_policy="tr39")("g੦ogle")
        'google'
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
        demojize: bool | str = False,
        strip_bidi: bool = False,
        strip_zalgo: int | None = None,
        strip_pua: bool = False,
        strip_plane14: bool = False,
        resolve_deletions: bool = False,
        resolve_cr: bool = False,
        digit_policy: str = "numeric",
    ) -> None:
        # #972: `demojize` is the one flag with three settings, so the union is split
        # here rather than at the FFI boundary. `True` names, a string replaces, `False`
        # omits the step. `True` is checked with `is` because a string is truthy: a bare
        # `if demojize` would read `demojize=""` as off and silently drop the step the
        # caller asked for.
        demojize_replacement: str | None = None
        if isinstance(demojize, str):
            demojize_replacement = demojize
            demojize = False
        elif not isinstance(demojize, bool):
            raise TypeError(
                f"TextPipeline() demojize must be bool or str, got {type(demojize).__name__}"
            )

        # Validation (e.g. strip_zalgo >= 0) lives in the Rust core's
        # _TextPipeline constructor, the single source of truth for every
        # caller — no Python-side duplicate to drift from it.
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
            demojize_replacement=demojize_replacement,
            strip_bidi=strip_bidi,
            strip_zalgo=strip_zalgo,
            strip_pua=strip_pua,
            strip_plane14=strip_plane14,
            resolve_deletions=resolve_deletions,
            resolve_cr=resolve_cr,
            digit_policy=digit_policy,
        )

    @classmethod
    def _from_inner(cls, inner: _TextPipeline) -> TextPipeline:
        """Wrap a core-built `_TextPipeline` (used by `get_pipeline`)."""
        self = cls.__new__(cls)
        self._inner = inner
        return self

    @_surrogate_safe
    def __call__(self, text: str) -> str:
        return self._inner.process(text)

    @property
    def purpose(self) -> str | None:
        """What this profile is *for*, in one sentence — or ``None`` if hand-built (#860).

        `list_profiles` returns names and `steps` says what a pipeline *does*; neither says
        what it is for, which made the profiles the one part of the public surface a reader
        could not evaluate without leaving the REPL. It matters most where two profiles look
        alike and are not: ``rag_ingest`` has no confusables step — its recovery is
        transliteration — so a Cyrillic look-alike of ``paypal`` romanizes to ``raural``,
        where ``llm_guardrail`` folds it to ``paypal``. Choosing wrong there fails silently
        and in the unsafe direction.

        A ``TextPipeline`` assembled from flags returns ``None``: the caller composed it and
        knows why.

        Examples:
            >>> get_pipeline("rag_ingest").purpose
            'Normalizing retrieved documents for a RAG index, romanizing legitimate non-Latin text rather than folding homoglyphs onto Latin.'
            >>> TextPipeline(fold_case=True).purpose is None
            True

            The list-with-purposes case is one line:

            >>> {p: get_pipeline(p).purpose for p in list_profiles()}  # doctest: +ELLIPSIS
            {'code_context': ...}
        """
        return self._inner.purpose()

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


# Incremented whenever the global registration tables (languages or replacements)
# change, so caches built by make_cached_transliterator can detect staleness and
# self-invalidate. (#128: renamed from _mutation_generation)
_registration_generation: int = 0


def _bump_registration_generation() -> None:
    # #128: renamed from _bump_mutation_generation for clarity.
    global _registration_generation
    _registration_generation += 1


def register_lang(code: str, mappings: dict[str, str]) -> None:
    """Register or override a transliteration mapping for a language code.

    Warning:
        This mutates **process-global** state consulted by every
        ``transliterate``/``slugify``/``catalog_key``/… call in the interpreter.
        Treat it as startup-only / single-writer configuration: do **not** call
        it from request-handling or library code in a multi-tenant process, where
        it would silently alter every other caller's output. Call
        `seal_registrations` after startup to make further changes raise.

        A call already running when this one returns is not guaranteed a single
        table: a batch ``transliterate(list)`` releases the GIL and reads the
        table per character, so its items, and even one long string, can mix
        the old mappings with the new. Calls that start afterwards see only the
        new ones.

    Note:
        Mappings keyed on **ASCII** characters do not apply to pure-ASCII input.
        The core takes a fast path that returns all-ASCII text unchanged before
        consulting language tables (ASCII is the transliteration *target*, so it
        is normally identity). Language profiles are meant for non-ASCII source
        characters (e.g. ``ä``→``ae``). To remap an ASCII character, use
        `register_replacements` instead — its keys run as a pre-pass that
        executes ahead of the ASCII fast path and therefore do apply.

    Args:
        code: Language code string (e.g. "xx", "custom").
        mappings: Dict of source→replacement character mappings.

    Raises:
        UnsupportedError: If registrations are sealed (a `DisarmError`).
        DisarmError: If the language table lock is poisoned, or the mapping cannot
            be stored.

    Examples:
        >>> register_lang("xx", {"Ä": "Ae", "ä": "ae", "Ö": "Oe", "ö": "oe"})
        >>> transliterate("Ärger", lang="xx")
        'Aerger'
    """
    _register_lang(code, mappings)
    _bump_registration_generation()


def register_replacements(replacements: dict[str, str]) -> None:
    """Register global pre-transliteration replacements.

    New entries are merged into the existing table. Existing keys are
    silently overwritten. Use `clear_replacements` to wipe the
    table, or `remove_replacement` to remove a single key.

    Replacements are applied to the input as a left-to-right pre-pass *before*
    the main transliteration tables, using longest-match-at-each-position
    semantics (the longest registered key matching at a position wins, and its
    output is not re-scanned, so replacements never cascade). Keys may be
    multi-character and may be ASCII.

    Warning:
        Like `register_lang`, this mutates **process-global** state shared
        by every caller. Treat it as startup-only / single-writer configuration
        and call `seal_registrations` afterwards in multi-tenant processes. As
        there, a batch call already in progress can apply the old table to some
        items and the new one to others.

    Args:
        replacements: Dict of source→replacement string mappings, applied
            before the main transliteration tables.

    Examples:
        >>> register_replacements({"™": "(tm)"})
        >>> transliterate("hello™")
        'hello(tm)'
        >>> clear_replacements()
    """
    _register_replacements(replacements)
    _bump_registration_generation()


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
        _bump_registration_generation()
    return result


def clear_replacements() -> None:
    """Clear all global pre-transliteration replacements.

    Examples:
        >>> register_replacements({"©": "(c)", "®": "(r)"})
        >>> clear_replacements()
    """
    _clear_replacements()
    _bump_registration_generation()


def seal_registrations() -> None:
    """Freeze the global registration tables (languages + replacements).

    After this is called, `register_lang`, `register_replacements`,
    `remove_replacement`, and `clear_replacements` raise
    `UnsupportedError` (a `DisarmError`). This is a one-way security latch (#64): the
    registration APIs mutate **process-global** state that every
    ``transliterate``/``slugify``/``catalog_key``/... call shares, so in a
    multi-tenant or web context an imported library or request handler could
    otherwise silently alter everyone's canonicalization. Configure your
    registrations at startup, then call ``seal_registrations()``.

    Examples:
        >>> register_lang("xx", {"Ä": "Ae"})  # doctest: +SKIP
        >>> seal_registrations()  # doctest: +SKIP
        >>> register_lang("yy", {"Ö": "Oe"})  # doctest: +SKIP
        Traceback (most recent call last):
        disarm.UnsupportedError: register_lang: registration tables are sealed ...

    Note: the example is ``+SKIP``-ped because sealing is a one-way,
    process-global latch — executing it in the doctest run would seal the shared
    interpreter and make every later registration/provider doctest fail.
    """
    _seal_registrations()


def registrations_sealed() -> bool:
    """Return True if `seal_registrations` has been called."""
    return _registrations_sealed()


# --- Bulk / caching helpers (opt-in) -------------------------------------


def dedup_batch(
    texts: list[str],
    *,
    lang: str | None = None,
    target: str | None = None,
    errors: TransliterateErrorMode = "replace",
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
    (Its output still depends on `register_lang` /
    `register_replacements` like any call — it simply cannot go stale.)

    Unique values are batched in chunks of 100,000 (the batch-size cap), so this
    also works for unique sets larger than a single ``transliterate`` call allows.

    Args:
        texts: List of input strings (repeats expected). Order is preserved.
        lang, target, errors, replace_with, strict_iso9, gost7034, tones,
            context: Same meaning as `transliterate`; applied to every value.

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
    # strict=True (3.10+): lengths are equal by construction — every uniq chunk
    # round-trips through transliterate(); a mismatch would mean a dropped or
    # duplicated batch item and should fail loudly, not silently mis-map.
    mapping = dict(zip(uniq, out, strict=True))
    return [mapping[t] for t in texts]


class CachedTransliterator(Protocol):
    """A cached single-string transliterator (the result of
    `make_cached_transliterator`) that also exposes the underlying
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
    errors: TransliterateErrorMode = "replace",
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
    `dedup_batch`, which is stateless and faster for bulk).

    The cache **self-invalidates**: the next call after any
    `register_lang`, `register_replacements`,
    `remove_replacement`, or `clear_replacements` clears it, so it
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

    # The generation is part of the key. It used to be checked beside the cache, which
    # left a window a TLA+ model found (formal/tla/Concurrency): a call reads the old
    # generation and computes with the old table, another call sees the new generation
    # and clears the cache, and the first then stores its old result into the fresh
    # cache, to be served from then on. Keyed by the generation the call *started*
    # under, such a result lands under a key no later call asks for. Every register_*
    # bumps the generation after changing the table, so once it returns no call can
    # read a result computed before it.
    @lru_cache(maxsize=maxsize)
    def _cached(text: str, _generation: int) -> str:
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

    seen_generation = _registration_generation

    # Not @wraps(_cached): inspect.signature follows __wrapped__ and would report the
    # private generation argument as part of the public one-string signature.
    def cached(text: str) -> str:
        nonlocal seen_generation
        generation = _registration_generation
        if generation != seen_generation:
            # Only to free memory now: entries from an older generation are never
            # looked up again, whatever this clear races with.
            _cached.cache_clear()
            seen_generation = generation
        return _cached(text, generation)

    cached.cache_clear = _cached.cache_clear  # type: ignore[attr-defined]
    cached.cache_info = _cached.cache_info  # type: ignore[attr-defined]
    return cast(CachedTransliterator, cached)


# The functions re-exported above keep naming this module as their home, as they did
# when they were defined here: `help()`, pickling and `inspect.getmodule` read `__module__`.
for _obj in list(globals().values()):
    if getattr(_obj, "__module__", "").startswith("disarm._api_"):
        _obj.__module__ = __name__
del _obj
