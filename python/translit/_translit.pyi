"""Type stubs for the _translit Rust extension module (PyO3)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

ErrorMode = Literal["replace", "ignore", "preserve"]
Platform = Literal["universal", "windows", "posix"]
NormalizationForm = Literal["NFC", "NFD", "NFKC", "NFKD"]

class TranslitError(Exception): ...

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
        confusables: bool = False,
        strip_accents: bool = False,
        fold_case: bool = False,
        collapse_whitespace: bool = False,
        strip_control: bool = True,
        strip_zero_width: bool = True,
        demojize: bool = False,
    ) -> None: ...
    def process(self, text: str) -> str: ...
    def steps(self) -> list[tuple[str, str | None]]: ...

def _transliterate(
    text: str,
    *,
    lang: str | None,
    errors: ErrorMode,
    replace_with: str,
    strict_iso9: bool,
) -> str: ...
def _slugify(
    text: str,
    *,
    separator: str,
    lowercase: bool,
    max_length: int,
    word_boundary: bool,
    save_order: bool,
    stopwords: Sequence[str],
    regex_pattern: str | None,
    replacements: Sequence[tuple[str, str]],
    allow_unicode: bool,
    lang: str | None,
    entities: bool,
    decimal: bool,
    hexadecimal: bool,
) -> str: ...
def _normalize(text: str, form: NormalizationForm) -> str: ...
def _normalize_confusables(text: str, *, target_script: str) -> str: ...
def _sanitize_filename(
    text: str,
    *,
    separator: str,
    max_length: int,
    platform: Platform,
    lang: str | None,
    preserve_extension: bool,
) -> str: ...
def _strip_accents(text: str) -> str: ...
def _fold_case(text: str) -> str: ...
def _collapse_whitespace(
    text: str,
    *,
    strip_control: bool,
    strip_zero_width: bool,
) -> str: ...
def _demojize(
    text: str,
    *,
    strip_modifiers: bool,
    errors: ErrorMode,
    replace_with: str,
    provider: object | None,
) -> str: ...
def _security_clean(text: str) -> str: ...
def _ml_normalize(
    text: str,
    *,
    lang: str | None,
    emoji_style: str,
) -> str: ...
def _catalog_key(
    text: str,
    *,
    lang: str | None,
    strict_iso9: bool,
) -> str: ...
def _display_clean(text: str) -> str: ...
def _strip_bidi(text: str) -> str: ...
def _grapheme_len(text: str) -> int: ...
def _grapheme_split(text: str) -> list[str]: ...
def _grapheme_truncate(text: str, max_graphemes: int) -> str: ...
def _is_safe_hostname(hostname: str) -> tuple[bool, SafeHostnameDetails]: ...
def _detect_encoding(data: bytes) -> tuple[str, float]: ...
def _decode_to_utf8(
    data: bytes, *, encoding: str | None, min_confidence: float = 0.0
) -> tuple[str, bool]: ...
def _detect_scripts(text: str) -> list[str]: ...
def _is_mixed_script(text: str) -> bool: ...
def _is_confusable(text: str, *, target_script: str) -> bool: ...
def _is_ascii(text: str) -> bool: ...
def _is_normalized(text: str, *, form: NormalizationForm) -> bool: ...
def _list_langs() -> list[str]: ...
def _register_lang(code: str, mappings: dict[str, str]) -> None: ...
def _register_replacements(replacements: dict[str, str]) -> None: ...
def _remove_replacement(key: str) -> bool: ...
def _clear_replacements() -> None: ...
def _transliterate_batch(
    texts: list[str],
    *,
    lang: str | None,
    errors: ErrorMode,
    replace_with: str,
    strict_iso9: bool,
) -> list[str]: ...
def _slugify_batch(
    texts: list[str],
    *,
    separator: str,
    lowercase: bool,
    max_length: int,
    word_boundary: bool,
    save_order: bool,
    stopwords: Sequence[str],
    regex_pattern: str | None,
    replacements: Sequence[tuple[str, str]],
    allow_unicode: bool,
    lang: str | None,
    entities: bool,
    decimal: bool,
    hexadecimal: bool,
) -> list[str]: ...
def _normalize_batch(texts: list[str], *, form: NormalizationForm) -> list[str]: ...
def _strip_accents_batch(texts: list[str]) -> list[str]: ...
def _set_emoji_provider(provider: object | None) -> None: ...
