"""Public API: transform functions, stateful classes, and registration helpers.

This module holds the implementation of every public name re-exported from the
``disarm`` package root (see ``disarm/__init__.py``).  The precompiled
pipeline presets live in ``disarm._presets``.
"""

from __future__ import annotations

import warnings as _warnings
from collections.abc import Iterable
from functools import lru_cache, wraps
from typing import TYPE_CHECKING, Any, Protocol, cast, overload

from disarm._core import (
    # Resource limit — read from the Rust single source of truth, never
    # re-declared, to prevent silent drift (#200).
    _MAX_BATCH_SIZE,
    AnomalyReport,
    HostnameAnalysis,
    # Exception hierarchy (#183): base + categorised subclasses
    InvalidArgumentError,
    # Reusable anomaly lexicon handle (HAI-SDLC 6.1)
    Lexicon,
    ResourceLimitError,
    _clear_replacements,
    _collapse_whitespace,
    _decode_to_utf8,
    _demojize,
    # Encoding detection
    _detect_encoding,
    # Predicates
    _detect_scripts,
    _escape_html,
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
    _inspect_anomalies,
    _inspect_anomalies_lex,
    _inspect_auto_lang,
    _is_ascii,
    _is_confusable,
    _is_mixed_script,
    _is_normalized,
    # Hostname safety
    _is_suspicious_hostname,
    # Language profiles
    _list_langs,
    _normalize,  # noqa: F401  (used by normalize() and internal pipelines)
    _normalize_batch,
    _normalize_confusables,
    _percent_encode,
    _register_lang,
    _register_replacements,
    _registrations_sealed,
    _remove_replacement,
    # Reverse transliteration
    _reverse_langs,
    _reverse_transliterate,
    _sanitize_filename,
    _seal_registrations,
    # Emoji provider
    _set_emoji_provider,
    _set_transliterate_fallback,
    # Stateful
    _Slugifier,
    _slugify,
    _slugify_batch,
    _strip_accents,
    _strip_accents_batch,
    _strip_log_injection,
    _terminal_width,
    _TextPipeline,
    # Core transforms (Rust implementations)
    _transliterate,
    # Batch APIs (single PyO3 boundary crossing for N strings)
    _transliterate_batch,
    _transliterate_context,
    _transliterate_entry,
    _UniqueSlugifier,
    # Semantic argument-combination validation (single source of truth, #231)
    _validate_transliterate_args,
)
from disarm._enums import (
    LANG_META,
    SCRIPT_META,
    Component,
    LangMeta,
    Script,
    ScriptMeta,
)
from disarm._types import (
    EmojiProvider,
    ErrorMode,
    NormalizationForm,
    Platform,
    TransliterateErrorMode,
)

# --- Resource limits ---
# _MAX_BATCH_SIZE is imported from the Rust extension above (single source of
# truth, #200). _MAX_GRAPHEME_SPLIT_INPUT has no Rust counterpart — the
# grapheme_split() size guard is enforced only on the Python side — so it is
# defined here (in characters/codepoints, see grapheme_split()).
_MAX_GRAPHEME_SPLIT_INPUT: int = 10 * 1024 * 1024  # ~10.5M characters (codepoints)

# The `errors=` / `form=` enum values are validated once, in the Rust core (#185),
# which raises InvalidArgumentError with the canonical message. The Python wrapper
# no longer keeps a hand-synced copy of those sets — that drift hazard scaled per
# binding. Only *combinations* of otherwise-valid kwargs are checked here (#69).


# Upper bound of the Rust `i64` that `max_length`/`max_graphemes` cross into.
# A larger value can't reach the core — PyO3 raises a bare `OverflowError` at
# extraction, outside the DisarmError hierarchy — so reject it here as
# InvalidArgumentError, consistently with the core's negative-value check (#255).
# This is the one bound the core provably cannot enforce (the value never arrives).
_MAX_I64: int = 2**63 - 1


def _checked_i64_max(value: int, name: str) -> int:
    """Reject a max-bound too large for the Rust i64 boundary (#255)."""
    if value > _MAX_I64:
        raise InvalidArgumentError(f"{name} too large: {value} exceeds the maximum {_MAX_I64}")
    return value


def _validate_batch(texts: object, func_name: str) -> None:
    """Validate that texts is a list[str] within batch size limits."""
    if not isinstance(texts, list):
        raise TypeError(f"{func_name}() expects list[str], got {type(texts).__name__}")
    if len(texts) > _MAX_BATCH_SIZE:
        raise ResourceLimitError(
            f"batch too large ({len(texts)} items); maximum is {_MAX_BATCH_SIZE} items"
        )
    for i, t in enumerate(texts):
        if not isinstance(t, str):
            raise TypeError(f"{func_name}() element {i} must be str, got {type(t).__name__}")


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
    ``р`` → ``p``), use :func:`normalize_confusables` or :func:`strip_obfuscation`
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
                *lang*. Use :func:`reverse_langs` to list supported languages.
        errors: How to handle untransliterable characters.
                "replace" — substitute with *replace_with*.
                "ignore" — silently drop.
                "preserve" — keep the original character.
                "strict" — raise ``DisarmError`` on the first untranslatable
                character, reporting it and its byte offset (#184). Forward-only:
                not supported with ``context=True`` or ``target=...``. Use
                :func:`find_untranslatable` to get *all* of them without raising.
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
    appearance — the exact set that :func:`transliterate` would replace, drop,
    or preserve (and that ``errors="strict"`` raises on the first of). Pure-ASCII
    input, or input that fully transliterates, returns an empty list.

    Global :func:`register_replacements` are applied first (so a replaced
    character is not reported), so the offsets are relative to the
    post-replacement text.

    Args:
        text: Input Unicode string.
        lang: Language code (same meaning as in :func:`transliterate`).
        strict_iso9: Use the scholarly ASCII Cyrillic table.
        gost7034: Use GOST R 7.0.34 transliteration.
        tones: Consider toned-pinyin coverage for CJK characters.

    Returns:
        List of ``(char, byte_offset)`` for each untranslatable character.

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
        separator: Character(s) between slug words.
        lowercase: Convert to lowercase.
        max_length: Maximum slug length in bytes (0 = unlimited).
            With ``allow_unicode=True``, multi-byte characters count as
            2–4 bytes each — use :func:`grapheme_truncate` for
            character-aware limiting.
        word_boundary: When truncating via max_length, cut at word boundaries.
        save_order: When ``True``, only leading and trailing stopwords are
            removed; interior stopwords are kept so relative word order is
            preserved (python-slugify compatible). When ``False`` (default),
            all matching stopwords are removed wherever they appear. (#118)
        stopwords: Words to remove from the slug.
        regex_pattern: Custom regex for stripping characters.
        replacements: Pre-transliteration (old, new) substitution pairs.
        allow_unicode: Keep non-ASCII letters instead of transliterating.
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
        DisarmError: If an internal Rust error occurs (e.g. an invalid
            ``regex_pattern`` or unknown ``lang`` code).

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
    # `form` is validated once in the Rust core (#185), which also has its own
    # ASCII fast path (ASCII is invariant under all four forms) — so there is no
    # binding-side form check or ASCII short-circuit left to keep in sync.
    if isinstance(text, list):
        _validate_batch(text, "normalize")
        return _normalize_batch(text, form=form)
    if not isinstance(text, str):
        raise TypeError(f"normalize() expects str or list[str], got {type(text).__name__}")
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
        DisarmError: If *target_script* is not a supported value.

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
        DisarmError: If an internal Rust error occurs.

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
    # max_length's non-negative contract is enforced by the Rust core (#231).
    return _sanitize_filename(
        text,
        separator=separator,
        max_length=_checked_i64_max(max_length, "max_length"),  # #255
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
            ``DeprecationWarning``. disarm always outputs bare CLDR
            short names without delimiters; wrap the result yourself if
            you need delimiters (e.g. ``f":{name}:"``).

    Returns:
        Text with emoji replaced by their descriptions.

    Raises:
        DisarmError: If an internal Rust error occurs.

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
            "The 'delimiters' parameter is not supported by disarm.demojize(); "
            "disarm always outputs bare CLDR short names. "
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

    .. note::
        **Sequence-length cap (#199).** The provider's ``lookup()`` is offered a
        look-ahead window of at most **9 codepoints** — the length of the longest
        built-in CLDR emoji sequence. A provider cannot match a sequence longer
        than 9 codepoints: the extra codepoints fall through to the built-in
        tables / per-codepoint handling. This cap is fixed (it sizes a
        stack-allocated scan window, so widening it would cost every ``demojize``
        call); design custom mappings to key on ≤ 9 codepoints. Skin-tone and
        variation-selector modifiers trailing a matched sequence are consumed
        separately and do not count toward the 9.

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
    # `len(text)` counts codepoints, not bytes; the guard and message both speak
    # in characters so the reported unit matches what is measured (#200). (An
    # O(1) codepoint count, rather than encoding the whole string to count bytes.)
    if len(text) > _MAX_GRAPHEME_SPLIT_INPUT:
        raise ResourceLimitError(
            f"input too large ({len(text)} characters); maximum for grapheme_split() "
            f"is {_MAX_GRAPHEME_SPLIT_INPUT} characters"
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
    # max_graphemes's non-negative contract is enforced by the Rust core (#231).
    return _grapheme_truncate(text, _checked_i64_max(max_graphemes, "max_graphemes"))  # #255


def terminal_width(text: str, *, ambiguous_wide: bool = False) -> int:
    """Total terminal column width of ``text``, summed over grapheme clusters.

    Measures **terminal cells** (UAX #11 East Asian Width per UAX #29 cluster),
    not pixels or font metrics. Wide/fullwidth characters and emoji-presented
    clusters are 2 columns; combining marks, controls, and zero-width characters
    are 0 — including tab (U+0009) and other C0/C1 control characters, which each
    contribute **0 columns** (they are not expanded to tab stops). Newlines are
    not modelled either; layout that depends on tab stops or wrapping is the
    caller's responsibility.

    Args:
        text: Input string.
        ambiguous_wide: Treat East Asian *Ambiguous* characters as 2 columns
            (for legacy double-width CJK terminals). Default ``False`` (1 column),
            matching modern UTF-8 terminals.

    Returns:
        Non-negative column count.

    Examples:
        >>> terminal_width("hello")
        5
        >>> terminal_width("世界")  # two wide CJK characters
        4
        >>> terminal_width("a😀")  # ASCII + emoji (2 cells)
        3
    """
    return _terminal_width(text, ambiguous_wide=ambiguous_wide)


def grapheme_width(cluster: str, *, ambiguous_wide: bool = False) -> int:
    """Column width of a single grapheme cluster (see :func:`terminal_width`).

    Pass a single grapheme cluster. The width is that of the **first scalar**
    (the base): 0 for a combining/zero-width base, 2 for a wide or
    emoji-presentation base, otherwise 1. Trailing scalars are then inspected for
    presentation selectors that adjust this — a variation selector U+FE0F (or a
    keycap ``U+20E3`` on a ``0``–``9``/``#``/``*`` base) forces emoji
    presentation (width 2), and U+FE0E forces text presentation (width 1 for an
    emoji base).

    It does **not** segment or sum grapheme clusters. If ``cluster`` contains
    more than the leading cluster, the extra scalars are *not* added to the
    width — but they are not blindly discarded either: a trailing presentation
    selector or keycap anywhere in the argument still affects the result per the
    rule above. For arbitrary (multi-cluster) strings use :func:`terminal_width`.

    Args:
        cluster: A single grapheme cluster.
        ambiguous_wide: Treat East Asian *Ambiguous* characters as 2 columns.

    Returns:
        Non-negative column count.

    Examples:
        >>> grapheme_width("A")
        1
        >>> grapheme_width("世")
        2
        >>> grapheme_width("👨‍👩‍👧‍👦")  # ZWJ family emoji = 1 cluster, 2 cells
        2
    """
    return _grapheme_width(cluster, ambiguous_wide=ambiguous_wide)


# --- Hostname safety ---


def is_suspicious_hostname(hostname: str) -> tuple[bool, HostnameAnalysis]:
    """Flag a hostname as *suspicious* for Unicode homoglyph spoofing.

    Returns ``(suspicious, analysis)`` where ``analysis`` is a
    ``HostnameAnalysis`` with attributes:

    - ``suspicious``: bool — True if a problem was detected (mixed-script or a
      bundled-table confusable).
    - ``scripts``: list[str] — Unicode scripts found across all labels.
    - ``mixed_script``: bool — True if any single label contains more than one script.
    - ``has_confusables``: bool — True if confusable homoglyphs found.
    - ``canonical``: str — Latin-normalized form of the hostname.

    A hostname is flagged suspicious if any single label is mixed-script
    (draws on more than one Unicode script, excluding Common/Inherited) or
    contains confusable homoglyphs. The mixed-script rule is conservative and
    fails closed: it flags benign combinations such as Latin+CJK as well as
    spoofing ones, so a caller wanting a more permissive policy can inspect the
    ``mixed_script`` and ``scripts`` fields and decide for itself.

    **A ``False`` (not-suspicious) result is not a safety guarantee.** It means
    only that no mixed-script label and no confusable *from the bundled TR39
    table* was found. Whole-script spoofs that use no bundled-table confusable,
    and confusables outside the bundled table, are out of scope (see the Threat
    Model) and report not-suspicious. Base allow/deny decisions on the granular
    findings plus your own policy — a detector can attest the presence of a
    problem, never the absence of all problems.

    Args:
        hostname: Hostname string to check (e.g. "example.com").

    Returns:
        Tuple of (suspicious, analysis) where analysis is a HostnameAnalysis.

    Examples:
        >>> suspicious, analysis = is_suspicious_hostname("google.com")
        >>> suspicious
        False
        >>> analysis.canonical
        'google.com'
    """
    return _is_suspicious_hostname(hostname)


# --- Anomaly detection (#389) ---


def has_anomalies(text: str, lexicon: Iterable[str] | Lexicon | None = None) -> bool:
    """Whether any whitespace token carries out-of-place characters that disguise a real word.

    Reports a *technical fact* — a cross-script homoglyph, leet, segmentation, a
    zero-width / bidi control, or zalgo — and leaves the malicious-or-not judgement
    to the caller, exactly as :func:`is_suspicious_hostname` does for hostnames.

    ``lexicon`` is a set of common words for the language being protected; it is
    used only by the leet and segmentation branches.  The invisible, bidi, zalgo,
    and mixed-script branches are script-agnostic and **need no lexicon** — calling
    ``has_anomalies(text)`` with no lexicon (or ``lexicon=None``) is valid and will
    still catch those classes of anomaly.  Pass a lexicon if you also want leet and
    segmentation detection.

    **Reusing a large lexicon (HAI-SDLC 6.1).** Passing a raw collection rebuilds
    an internal set on every call. When calling this in a loop with a large
    lexicon, build a :class:`Lexicon` once and pass it instead — the set is built
    a single time and reused across calls, with identical results.

    Args:
        text: Input text.
        lexicon: Common-word collection (set, list, …) for the target language,
            *or* a prebuilt :class:`Lexicon` handle, used only by the leet and
            segmentation branches.  When ``None`` (the default) or an empty
            iterable, those two branches are effectively disabled; all other
            branches still run.

    Returns:
        True if any token tripped a detector.

    Examples:
        >>> has_anomalies("get fr33 stuff", {"free"})
        True
        >>> has_anomalies("a perfectly ordinary sentence")
        False
        >>> has_anomalies("paypаl")  # Cyrillic а — mixed-script, no lexicon needed
        True
        >>> lex = Lexicon({"free"})  # build once, reuse across calls
        >>> has_anomalies("get fr33 stuff", lex)
        True
    """
    if isinstance(lexicon, Lexicon):
        return _has_anomalies_lex(text, lexicon)
    return _has_anomalies(text, set(lexicon) if lexicon is not None else None)


def inspect_anomalies(text: str, lexicon: Iterable[str] | Lexicon | None = None) -> AnomalyReport:
    """Full anomaly analysis: every finding with its span and a plain-language reason.

    Parallel to :func:`is_suspicious_hostname`'s ``HostnameAnalysis``. Returns an
    ``AnomalyReport`` with attributes:

    - ``anomalous``: bool — the same value :func:`has_anomalies` returns.
    - ``kinds``: list[str] — the anomaly kinds that fired, in first-appearance
      order (``"invisible"``, ``"bidi"``, ``"zalgo"``, ``"mixed_script"``,
      ``"leet"``, ``"segmentation"``).
    - ``findings``: list[Finding] — each with ``kind``, ``token``, ``start``/``end``
      (byte offsets), ``detail``, and a plain-language ``reason``.
    - ``reason``: str | None — the first finding's reason.

    The ``lexicon`` is optional (see :func:`has_anomalies`).  When omitted, the
    invisible, bidi, zalgo, and mixed-script branches still run; only leet and
    segmentation detection requires a lexicon.

    **Reusing a large lexicon (HAI-SDLC 6.1).** As with :func:`has_anomalies`,
    pass a prebuilt :class:`Lexicon` to avoid rebuilding the internal set on every
    call when looping over a large lexicon.

    Args:
        text: Input text.
        lexicon: Common-word collection (set, list, …) *or* a prebuilt
            :class:`Lexicon` handle (see :func:`has_anomalies`).
            Defaults to ``None`` (empty — leet/segmentation branches disabled).

    Returns:
        An ``AnomalyReport``.

    Examples:
        >>> r = inspect_anomalies("get fr33", {"free"})
        >>> r.anomalous, r.kinds
        (True, ['leet'])
        >>> r.findings[0].detail
        'free'
        >>> inspect_anomalies("clean text").anomalous
        False
    """
    if isinstance(lexicon, Lexicon):
        return _inspect_anomalies_lex(text, lexicon)
    return _inspect_anomalies(text, set(lexicon) if lexicon is not None else None)


# --- Output encoders (terminal, context-explicit — NOT pipeline steps) ---


def escape_html(text: str) -> str:
    """Escape the five HTML metacharacters for element/quoted-attribute context.

    ``&`` -> ``&amp;``, ``<`` -> ``&lt;``, ``>`` -> ``&gt;``, ``"`` -> ``&quot;``,
    ``'`` -> ``&#x27;``. Everything else passes through unchanged.

    Correct for HTML **element-body and quoted-attribute** context. It is **not**
    correct inside ``<script>``/``<style>``, unquoted attributes, URL/``href``/
    ``src`` attributes, or HTML comments -- there, entity escaping is insufficient
    or corrupting. This is a terminal output encoder: apply it at the sink,
    exactly once. It is **not** idempotent (encoding twice double-encodes ``&``),
    and disarm is not an XSS framework -- see the Threat Model.

    Args:
        text: The string to escape.

    Returns:
        The escaped string (the original object when nothing needs escaping).

    Examples:
        >>> escape_html("<b>a & b</b>")
        '&lt;b&gt;a &amp; b&lt;/b&gt;'
        >>> escape_html("plain text")
        'plain text'
    """
    return _escape_html(text)


def percent_encode(text: str, *, component: Component) -> str:
    """RFC 3986 percent-encode ``text`` for a named URL ``component``.

    The input is UTF-8 encoded first, then every byte outside the component's
    safe set becomes ``%XX`` (``e`` with an accent -> ``%C3%A9``); the output is
    pure ASCII. ``component`` is required because the safe set depends on where
    the value is placed (:class:`Component`: ``PATH``/``SEGMENT``/``QUERY``/
    ``FORM``; ``FORM`` uses ``application/x-www-form-urlencoded`` space -> ``+``).

    Percent-encoding is **not** a defense against ``javascript:``/``data:``
    scheme injection or open redirects -- those are URL-*construction* concerns,
    out of scope. Apply at the output sink, exactly once.

    Args:
        text: The string to encode.
        component: Which URL component the value will be placed in.

    Returns:
        The percent-encoded ASCII string.

    Examples:
        >>> from disarm import Component
        >>> percent_encode("a b&c", component=Component.QUERY)
        'a%20b%26c'
        >>> percent_encode("a b&c", component=Component.FORM)
        'a+b%26c'
    """
    # Accept a Component (the typed contract) but pass a bare string straight
    # through so a stringly-typed caller gets the core's clear
    # InvalidArgumentError rather than an AttributeError on ``.value``.
    value = component.value if isinstance(component, Component) else component
    return _percent_encode(text, component=value)


def strip_log_injection(text: str, *, replacement: str = "\ufffd", keep_tab: bool = False) -> str:
    """Neutralize log-injection / terminal-control characters in ``text``.

    Replaces -- rather than dropping, so a redaction stays visible -- every CR,
    LF, NEL (U+0085), LS (U+2028), PS (U+2029), NUL, C0/C1 control, ESC, and DEL
    with ``replacement`` (default U+FFFD; pass ``replacement=""`` to drop). ``\t`` is **also** neutralized by
    default (``keep_tab=False``): a tab is a field separator in TSV/logfmt logs,
    so keeping it permits column injection; pass ``keep_tab=True`` for
    human-readable tabular logs. ANSI escape sequences are neutralized by
    replacing their introducer (``ESC``), leaving the inert ``[31m`` residue.

    Idempotent; the output never contains a raw CR/LF/ESC. This makes a log line
    safe to *write*, not safe to later *render as HTML*: it is **not** an
    HTML/SQL output sanitizer (it preserves ``< > &`` -- encode those at the log
    *viewer* with :func:`escape_html`), and **not** a defense against
    logging-framework interpolation (log4shell). See the Threat Model.

    Args:
        text: The (untrusted) string destined for a log line.
        replacement: String substituted for each neutralized character (``""``
            drops them). Must not itself contain a neutralized character (else
            ``DisarmError``).
        keep_tab: Keep ``\t`` instead of neutralizing it.

    Returns:
        The neutralized string (the original object when nothing needs it).

    Examples:
        >>> strip_log_injection("user=admin\nFAKE LOG ENTRY")
        'user=admin\ufffdFAKE LOG ENTRY'
        >>> strip_log_injection("a\x1b[31mb")
        'a\ufffd[31mb'
    """
    return _strip_log_injection(text, replacement=replacement, keep_tab=keep_tab)


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

    Note (#194): chardetng (since the 1.0 migration, #164) does not expose a
    graded score — it reports a fixed confidence of ``0.95`` for every
    successful detection. The float is kept for API stability and to align with
    chardet-style ranges, but callers cannot use it to rank detection quality.

    Important: automatic encoding detection is inherently probabilistic.
    A high confidence score does NOT guarantee correctness. For critical
    pipelines, always prefer explicit encoding metadata over detection.

    Args:
        data: Raw byte sequence to analyze.

    Returns:
        Tuple of (encoding_name, confidence) where confidence is 0.0–1.0.

    Raises:
        DisarmError: If the byte sequence cannot be analyzed.

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
    strict: bool = False,
) -> tuple[str, bool]:
    """Decode a byte sequence to UTF-8.

    Returns (decoded_text, had_errors) where had_errors is True if a U+FFFD
    replacement character was inserted during decoding.

    ``had_errors=False`` is **not** a fidelity guarantee: single-byte encodings
    such as windows-1252 map every byte to some codepoint without ever inserting
    U+FFFD, so a wrong-encoding decode can produce mojibake with
    ``had_errors=False`` and no exception. For critical data, prefer explicit
    encoding metadata over auto-detection (and see ``strict`` below).

    If encoding is None, auto-detects using the chardetng algorithm. Note that
    ``min_confidence`` is effectively a binary accept/reject knob (see #194 and
    the argument docs below), not a quality grade.

    Supports all WHATWG encodings (UTF-8, windows-1252, ISO-8859-1,
    Shift_JIS, EUC-JP, EUC-KR, Big5, GB18030, etc.).

    Args:
        data: Raw byte sequence to decode.
        encoding: Encoding name (e.g. "windows-1252"). None to auto-detect.
        min_confidence: Confidence threshold (0.0–1.0) applied when
            auto-detecting; raises DisarmError if the detected confidence is
            below it. When ``encoding`` is given explicitly the confidence gate
            is bypassed (nothing is detected), but the value is still
            range-validated — an out-of-range ``min_confidence`` raises
            regardless (#217). Defaults to ``0.95``.

            **Effectively a binary knob (#194).** Since the chardetng 1.0
            migration (#164) the detector reports a fixed ``0.95`` for every
            successful detection, so ``min_confidence`` cannot grade detection
            quality: any value ``<= 0.95`` (including the ``0.95`` default)
            accepts every guess, and any value ``> 0.95`` (e.g. ``1.0``) rejects
            auto-detection outright. The default therefore does **not** reject
            low-quality detections — to require high-quality input, pass the
            encoding explicitly rather than relying on this threshold. Pass
            ``0.0`` to be explicit about accepting any guess.
        strict: When ``True``, raise :class:`DisarmError` instead of silently
            returning ``had_errors=True`` if the input contains byte sequences
            that decode to the U+FFFD replacement character (#189). Use this to
            turn lossy decodes — a common silent-data-loss source — into a hard
            failure. Note ``had_errors`` is a *replacement-character* flag, not a
            full fidelity guarantee (see the module docs), so ``strict`` catches
            malformed input, not every lossy remapping.

    Returns:
        Tuple of (decoded_text, had_errors). With ``strict=True`` the second
        element is always ``False`` (any error raises instead).

    Raises:
        DisarmError: If the encoding name is unknown, decoding fails,
            auto-detection confidence is below min_confidence, or
            ``strict=True`` and the decode was lossy.

    Examples:
        >>> text, had_errors = decode_to_utf8(b"caf\\xe9", "windows-1252")
        >>> text
        'café'
        >>> had_errors
        False
    """
    # The [0.0, 1.0] range check lives in the Rust core (decode_to_utf8_impl),
    # the single source of truth every caller crosses — no Python-side duplicate.
    return _decode_to_utf8(data, encoding=encoding, min_confidence=min_confidence, strict=strict)


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
                f"upgrade disarm or report this as a bug",
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
        - ``reason``: one of ``"unambiguous_script"``, ``"discriminator"``, ``"script_default"``, ``"latin_discriminator"``, ``"no_detection"``
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
            ``"latin"`` is supported; any other value raises ``DisarmError``.
        greedy: ``confusable_homoglyphs`` compatibility — ignored with a
            ``DeprecationWarning``. disarm always checks all characters.
        preferred_aliases: ``confusable_homoglyphs`` compatibility — ignored
            with a ``DeprecationWarning``. disarm uses its own script
            detection engine.

    Returns:
        True if any confusable homoglyphs are present.

    Raises:
        DisarmError: If *target_script* is not ``"latin"``.

    Examples:
        >>> is_confusable("pаypal")  # Cyrillic а looks like Latin a
        True
        >>> is_confusable("paypal")  # all genuine Latin
        False
    """
    if greedy is not None:
        _warnings.warn(
            "The 'greedy' parameter is not supported by disarm.is_confusable(); "
            "disarm always checks all characters.",
            DeprecationWarning,
            stacklevel=2,
        )
    if preferred_aliases is not None:
        _warnings.warn(
            "The 'preferred_aliases' parameter is not supported by "
            "disarm.is_confusable(); disarm uses its own script detection.",
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
        self._default: str | None = self._inner.slugify(default) if default is not None else None

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
        self._default: str | None = default
        self._probe: Slugifier | None = (
            Slugifier(**_cfg) if default is not None else None  # type: ignore[arg-type]
        )

    def __call__(self, text: str) -> str:
        probe = self._probe
        if probe is not None and self._default is not None and not probe(text):
            return self._inner.slugify(self._default)
        return self._inner.slugify(text)

    def reset(self) -> None:
        """Clear the internal set of seen slugs."""
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

    This constructor takes individual step flags only; there is **no**
    ``preset=`` argument. To obtain a pre-configured pipeline for a named policy
    profile (e.g. ``scholarly_cyrillic_iso9``), call :func:`get_pipeline`
    instead — it returns a ready-to-use ``TextPipeline``.

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
        strip_bidi: bool = False,
        strip_zalgo: int | None = None,
    ) -> None:
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
            strip_bidi=strip_bidi,
            strip_zalgo=strip_zalgo,
        )

    @classmethod
    def _from_inner(cls, inner: _TextPipeline) -> TextPipeline:
        """Wrap a core-built `_TextPipeline` (used by `get_pipeline`)."""
        self = cls.__new__(cls)
        self._inner = inner
        return self

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
        A :class:`LangMeta` dict with ``name``, ``script``, ``region``, and
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
        script: Script name (e.g. ``"Coptic"``) or :class:`Script` enum value.

    Returns:
        A :class:`ScriptMeta` dict with ``name``, ``default_lang``, ``example``,
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

    .. warning::
        This mutates **process-global** state consulted by every
        ``transliterate``/``slugify``/``catalog_key``/… call in the interpreter.
        Treat it as startup-only / single-writer configuration: do **not** call
        it from request-handling or library code in a multi-tenant process, where
        it would silently alter every other caller's output. Call
        :func:`seal_registrations` after startup to make further changes raise.

    .. note::
        Mappings keyed on **ASCII** characters do not apply to pure-ASCII input.
        The core takes a fast path that returns all-ASCII text unchanged before
        consulting language tables (ASCII is the transliteration *target*, so it
        is normally identity). Language profiles are meant for non-ASCII source
        characters (e.g. ``ä``→``ae``). To remap an ASCII character, use
        :func:`register_replacements` instead — its keys run as a pre-pass that
        executes ahead of the ASCII fast path and therefore do apply.

    Args:
        code: Language code string (e.g. "xx", "custom").
        mappings: Dict of source→replacement character mappings.

    Raises:
        DisarmError: If registrations are sealed, the language table lock is
            poisoned, or the mapping cannot be stored.

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

    After this is called, :func:`register_lang`, :func:`register_replacements`,
    :func:`remove_replacement`, and :func:`clear_replacements` raise
    :class:`DisarmError`. This is a one-way security latch (#64): the
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
        disarm.DisarmError: register_lang: registration tables are sealed ...

    Note: the example is ``+SKIP``-ped because sealing is a one-way,
    process-global latch — executing it in the doctest run would seal the shared
    interpreter and make every later registration/provider doctest fail.
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
    # strict=True (3.10+): lengths are equal by construction — every uniq chunk
    # round-trips through transliterate(); a mismatch would mean a dropped or
    # duplicated batch item and should fail loudly, not silently mis-map.
    mapping = dict(zip(uniq, out, strict=True))
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

    seen_generation = _registration_generation

    @wraps(_cached)
    def cached(text: str) -> str:
        nonlocal seen_generation
        if _registration_generation != seen_generation:
            _cached.cache_clear()
            seen_generation = _registration_generation
        return _cached(text)

    cached.cache_clear = _cached.cache_clear  # type: ignore[attr-defined]
    cached.cache_info = _cached.cache_info  # type: ignore[attr-defined]
    return cast(CachedTransliterator, cached)
