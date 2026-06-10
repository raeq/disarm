"""Type stubs for the _translit Rust extension module (PyO3)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

# Imported from the single source of truth so the stub cannot drift from the
# authoritative alias definitions in translit._types (#200).
from translit._types import (
    ErrorMode,
    NormalizationForm,
    Platform,
    TransliterateErrorMode,
)

# Resource limits exposed by the Rust module (#200).
_MAX_BATCH_SIZE: int

class TranslitError(ValueError): ...
class InvalidArgumentError(TranslitError): ...
class ResourceLimitError(TranslitError): ...
class UnsupportedError(TranslitError): ...

class SafeHostnameDetails:
    safe: bool
    scripts: list[str]
    mixed_script: bool
    has_confusables: bool
    canonical: str

class _Slugifier:
    separator: str
    lang: str | None

    def __init__(
        self,
        *,
        separator: str = "-",
        lowercase: bool = True,
        max_length: int = 0,
        word_boundary: bool = False,
        save_order: bool = False,
        stopwords: tuple[str, ...] = (),
        regex_pattern: str | None = None,
        replacements: tuple[tuple[str, str], ...] = (),
        allow_unicode: bool = False,
        lang: str | None = None,
        entities: bool = True,
        decimal: bool = True,
        hexadecimal: bool = True,
        safe_chars: str = "",
    ) -> None: ...
    def slugify(self, text: str) -> str: ...

class _UniqueSlugifier:
    def __init__(
        self,
        *,
        check: object | None = None,
        separator: str = "-",
        lowercase: bool = True,
        max_length: int = 0,
        word_boundary: bool = False,
        save_order: bool = False,
        stopwords: tuple[str, ...] = (),
        regex_pattern: str | None = None,
        replacements: tuple[tuple[str, str], ...] = (),
        allow_unicode: bool = False,
        lang: str | None = None,
        entities: bool = True,
        decimal: bool = True,
        hexadecimal: bool = True,
        safe_chars: str = "",
    ) -> None: ...
    def slugify(self, text: str) -> str: ...
    def reset(self) -> None: ...

class _TextPipeline:
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
    ) -> None: ...
    def process(self, text: str) -> str: ...
    def steps(self) -> list[tuple[str, str | None]]: ...

def _transliterate(
    text: str,
    lang: str | None = None,
    errors: TransliterateErrorMode = ...,
    replace_with: str = ...,
    strict_iso9: bool = ...,
    gost7034: bool = ...,
    tones: bool = ...,
) -> str: ...
def _validate_transliterate_args(
    *,
    lang: str | None = None,
    target: str | None = None,
    errors: TransliterateErrorMode = ...,
    replace_with: str = ...,
    strict_iso9: bool = ...,
    gost7034: bool = ...,
    tones: bool = ...,
    context: bool = ...,
) -> None: ...
def _find_untranslatable(
    text: str,
    *,
    lang: str | None = None,
    strict_iso9: bool = ...,
    gost7034: bool = ...,
    tones: bool = ...,
) -> list[tuple[str, int]]: ...
def _transliterate_context(
    text: str,
    *,
    lang: str | None = None,
    errors: ErrorMode = ...,
    replace_with: str = ...,
    strict_iso9: bool = ...,
    gost7034: bool = ...,
) -> str: ...
def _set_transliterate_fallback(f: Callable[..., Any]) -> None: ...
def _transliterate_entry(
    text: Any,
    *,
    lang: str | None = None,
    target: str | None = None,
    errors: ErrorMode = ...,
    replace_with: str = ...,
    strict_iso9: bool = ...,
    gost7034: bool = ...,
    tones: bool = ...,
    context: bool = ...,
) -> Any: ...
def _slugify(
    text: str,
    *,
    separator: str = "-",
    lowercase: bool = True,
    max_length: int = 0,
    word_boundary: bool = False,
    save_order: bool = False,
    stopwords: Sequence[str] = ...,
    regex_pattern: str | None = None,
    replacements: Sequence[tuple[str, str]] = ...,
    allow_unicode: bool = False,
    lang: str | None = None,
    entities: bool = True,
    decimal: bool = True,
    hexadecimal: bool = True,
) -> str: ...
def _normalize(text: str, *, form: NormalizationForm = ...) -> str: ...
def _normalize_confusables(text: str, *, target_script: str = ...) -> str: ...
def _sanitize_filename(
    text: str,
    *,
    separator: str = "_",
    max_length: int = 255,
    platform: Platform = ...,
    lang: str | None = None,
    preserve_extension: bool = True,
) -> str: ...
def _strip_accents(text: str) -> str: ...
def _fold_case(text: str) -> str: ...
def _collapse_whitespace(
    text: str,
    *,
    strip_control: bool = True,
    strip_zero_width: bool = True,
) -> str: ...
def _demojize(
    text: str,
    *,
    strip_modifiers: bool = False,
    errors: ErrorMode = ...,
    replace_with: str = ...,
    provider: object | None = None,
) -> str: ...
def _security_clean(text: str) -> str: ...
def _ml_normalize(
    text: str,
    *,
    lang: str | None = None,
    emoji_style: str = ...,
) -> str: ...
def _catalog_key(
    text: str,
    *,
    lang: str | None = None,
    strict_iso9: bool = False,
) -> str: ...
def _display_clean(text: str) -> str: ...
def _search_key(text: str, *, lang: str | None = None) -> str: ...
def _sort_key(text: str, *, lang: str | None = None) -> str: ...
def _strip_bidi(text: str) -> str: ...
def _sanitize_user_input(text: str) -> str: ...
def _strip_obfuscation(text: str) -> str: ...
def _get_pipeline(profile: str) -> _TextPipeline: ...
def _list_profiles() -> list[str]: ...
def _is_zalgo(text: str, *, threshold: int = 3) -> bool: ...
def _strip_zalgo(text: str, *, max_marks: int = 2) -> str: ...
def _grapheme_len(text: str) -> int: ...
def _grapheme_split(text: str) -> list[str]: ...
def _grapheme_truncate(text: str, max_graphemes: int) -> str: ...
def _terminal_width(text: str, *, ambiguous_wide: bool = False) -> int: ...
def _grapheme_width(cluster: str, *, ambiguous_wide: bool = False) -> int: ...
def _is_safe_hostname(hostname: str) -> tuple[bool, SafeHostnameDetails]: ...
def _detect_encoding(data: bytes) -> tuple[str, float]: ...
def _decode_to_utf8(
    data: bytes,
    encoding: str | None = None,
    min_confidence: float = 0.95,
    strict: bool = False,
) -> tuple[str, bool]: ...
def _detect_scripts(text: str) -> list[str]: ...
def _is_mixed_script(text: str) -> bool: ...
def _inspect_auto_lang(text: str) -> dict[str, object]: ...
def _is_confusable(text: str, *, target_script: str = ...) -> bool: ...
def _is_ascii(text: str) -> bool: ...
def _is_normalized(text: str, *, form: NormalizationForm = ...) -> bool: ...
def _list_langs() -> list[str]: ...
def _register_lang(code: str, mappings: dict[str, str]) -> None: ...
def _register_replacements(replacements: dict[str, str]) -> None: ...
def _remove_replacement(key: str) -> bool: ...
def _clear_replacements() -> None: ...
def _seal_registrations() -> None: ...
def _registrations_sealed() -> bool: ...
def _transliterate_batch(
    texts: list[str],
    lang: str | None = None,
    errors: TransliterateErrorMode = ...,
    replace_with: str = ...,
    strict_iso9: bool = ...,
    gost7034: bool = ...,
    tones: bool = ...,
) -> list[str]: ...
def _slugify_batch(
    texts: list[str],
    *,
    separator: str = "-",
    lowercase: bool = True,
    max_length: int = 0,
    word_boundary: bool = False,
    save_order: bool = False,
    stopwords: Sequence[str] = ...,
    regex_pattern: str | None = None,
    replacements: Sequence[tuple[str, str]] = ...,
    allow_unicode: bool = False,
    lang: str | None = None,
    entities: bool = True,
    decimal: bool = True,
    hexadecimal: bool = True,
) -> list[str]: ...
def _normalize_batch(texts: list[str], *, form: NormalizationForm = ...) -> list[str]: ...
def _strip_accents_batch(texts: list[str]) -> list[str]: ...
def _set_emoji_provider(provider: object | None = None) -> None: ...
def _reverse_transliterate(text: str, *, lang: str) -> str: ...
def _reverse_langs() -> list[str]: ...
