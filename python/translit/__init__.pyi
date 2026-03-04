"""Type stubs for unirust."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Literal, final

from unirust._enums import Script as Script
from unirust._text import Text as Text
from unirust._types import EmojiProvider as EmojiProvider
from unirust._types import NF as NF
from unirust._enums import LANG_BG as LANG_BG
from unirust._enums import LANG_CA as LANG_CA
from unirust._enums import LANG_CS as LANG_CS
from unirust._enums import LANG_CY as LANG_CY
from unirust._enums import LANG_DA as LANG_DA
from unirust._enums import LANG_DE as LANG_DE
from unirust._enums import LANG_EL as LANG_EL
from unirust._enums import LANG_ES as LANG_ES
from unirust._enums import LANG_ET as LANG_ET
from unirust._enums import LANG_FI as LANG_FI
from unirust._enums import LANG_FR as LANG_FR
from unirust._enums import LANG_GA as LANG_GA
from unirust._enums import LANG_HR as LANG_HR
from unirust._enums import LANG_HU as LANG_HU
from unirust._enums import LANG_IS as LANG_IS
from unirust._enums import LANG_IT as LANG_IT
from unirust._enums import LANG_LT as LANG_LT
from unirust._enums import LANG_LV as LANG_LV
from unirust._enums import LANG_MT as LANG_MT
from unirust._enums import LANG_NL as LANG_NL
from unirust._enums import LANG_NO as LANG_NO
from unirust._enums import LANG_PL as LANG_PL
from unirust._enums import LANG_PT as LANG_PT
from unirust._enums import LANG_RO as LANG_RO
from unirust._enums import LANG_SK as LANG_SK
from unirust._enums import LANG_SL as LANG_SL
from unirust._enums import LANG_SQ as LANG_SQ
from unirust._enums import LANG_SR as LANG_SR
from unirust._enums import LANG_SV as LANG_SV
from unirust._enums import LANG_TR as LANG_TR
from unirust._enums import LANG_UK as LANG_UK
from unirust._enums import LANG_VI as LANG_VI
from unirust._enums import LANG_AR as LANG_AR
from unirust._enums import LANG_JA as LANG_JA
from unirust._enums import LANG_KO as LANG_KO
from unirust._enums import LANG_RU as LANG_RU
from unirust._enums import LANG_ZH as LANG_ZH

# --- Core transforms ---

def transliterate(
    text: str,
    *,
    lang: str | None = None,
    errors: Literal["replace", "ignore", "preserve"] = "replace",
    replace_with: str = "[?]",
    strict_iso9: bool = False,
) -> str:
    """Unicode → ASCII transliteration."""
    ...

def slugify(
    text: str,
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
) -> str:
    """Generate a URL-safe slug from Unicode text."""
    ...

def normalize(
    text: str,
    *,
    form: Literal["NFC", "NFD", "NFKC", "NFKD"] = "NFC",
) -> str:
    """Unicode normalization (NFC, NFD, NFKC, NFKD)."""
    ...

def normalize_confusables(
    text: str,
    *,
    target_script: str = "latin",
) -> str:
    """Replace Unicode confusable homoglyphs with target-script equivalents."""
    ...

def sanitize_filename(
    text: str,
    *,
    separator: str = "_",
    max_length: int = 255,
    platform: Literal["universal", "windows", "posix"] = "universal",
    lang: str | None = None,
    preserve_extension: bool = True,
) -> str:
    """Sanitize a string into a safe filename."""
    ...

def strip_accents(text: str) -> str:
    """Remove diacritical marks while preserving base characters."""
    ...

def fold_case(text: str) -> str:
    """Full Unicode case folding per CaseFolding.txt (Unicode 16.0).

    All 1,557 status-C and status-F mappings: Latin (ß→ss, ſ→s, İ→i̇),
    Greek (ς→σ, variant forms), Cyrillic, Armenian, Georgian Mtavruli,
    Cherokee, Adlam, Deseret, Osage, Warang Citi, fullwidth Latin,
    and all Latin ligature expansions.  Pure-ASCII fast path.
    """
    ...

def collapse_whitespace(
    text: str,
    *,
    strip_control: bool = True,
    strip_zero_width: bool = True,
) -> str:
    """Normalize all Unicode whitespace variants to single ASCII spaces."""
    ...

def demojize(
    text: str,
    *,
    strip_modifiers: bool = False,
    errors: Literal["replace", "ignore", "preserve"] = "replace",
    replace_with: str = "[?]",
    provider: EmojiProvider | None = None,
) -> str:
    """Expand emoji sequences to their CLDR short-name text descriptions."""
    ...

def set_emoji_provider(provider: EmojiProvider | None = None) -> None:
    """Set a global emoji provider for all demojize calls."""
    ...

# Batch APIs

def transliterate_batch(
    texts: list[str],
    *,
    lang: str | None = None,
    errors: Literal["replace", "ignore", "preserve"] = "replace",
    replace_with: str = "[?]",
    strict_iso9: bool = False,
) -> list[str]:
    """Batch Unicode → ASCII transliteration in a single Rust call."""
    ...

def slugify_batch(
    texts: list[str],
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
) -> list[str]:
    """Batch URL-safe slug generation in a single Rust call."""
    ...

def normalize_batch(
    texts: list[str],
    *,
    form: Literal["NFC", "NFD", "NFKC", "NFKD"] = "NFC",
) -> list[str]:
    """Batch Unicode normalization in a single Rust call."""
    ...

def strip_accents_batch(texts: list[str]) -> list[str]:
    """Batch accent stripping in a single Rust call."""
    ...

# --- Precompiled pipelines ---

def security_clean(text: str) -> str:
    """Security-focused text canonicalization (NFKC → confusables → whitespace → bidi)."""
    ...

def ml_normalize(
    text: str,
    *,
    lang: str | None = None,
    emoji: str = "cldr",
) -> str:
    """ML/NLP normalization pipeline producing clean lowercased text."""
    ...

def catalog_key(
    text: str,
    *,
    lang: str | None = None,
    strict_iso9: bool = False,
) -> str:
    """Library catalog key generation for bibliographic deduplication."""
    ...

def display_clean(text: str) -> str:
    """Display-safe text cleaning (collapse whitespace, strip control chars)."""
    ...

def strip_bidi(text: str) -> str:
    """Strip bidirectional override and formatting characters."""
    ...

# --- Grapheme cluster functions ---

def grapheme_len(text: str) -> int:
    """Count user-perceived characters (extended grapheme clusters)."""
    ...

def grapheme_split(text: str) -> list[str]:
    """Split text into a list of extended grapheme clusters."""
    ...

def grapheme_truncate(text: str, max_graphemes: int) -> str:
    """Truncate text to at most max_graphemes grapheme clusters."""
    ...

# --- Hostname safety ---

@final
class SafeHostnameDetails:
    """Details from hostname safety check.

    Attributes:
        safe: True if no homoglyph spoofing detected.
        scripts: Unicode scripts found across all labels.
        mixed_script: True if multiple scripts detected.
        has_confusables: True if confusable homoglyphs found.
        canonical: Latin-normalized form of the hostname.
    """

    safe: bool
    scripts: list[str]
    mixed_script: bool
    has_confusables: bool
    canonical: str

def is_safe_hostname(hostname: str) -> tuple[bool, SafeHostnameDetails]:
    """Check if a hostname is safe from Unicode homoglyph attacks."""
    ...

# --- Encoding detection ---

def detect_encoding(data: bytes) -> tuple[str, float]:
    """Detect the encoding of a byte sequence (returns encoding, confidence)."""
    ...

def decode_to_utf8(
    data: bytes,
    encoding: str | None = None,
) -> tuple[str, bool]:
    """Decode bytes to UTF-8 (returns decoded_text, had_errors)."""
    ...

# --- Predicates ---

def detect_scripts(text: str) -> list[Script]:
    """Return Unicode scripts present in text, in order of first appearance."""
    ...

def is_mixed_script(text: str) -> bool:
    """True if text contains characters from more than one Unicode script."""
    ...

def is_confusable(
    text: str,
    *,
    target_script: str = "latin",
) -> bool:
    """True if text contains characters confusable with target-script characters."""
    ...

def is_ascii(text: str) -> bool:
    """True if all characters are in U+0000–U+007F."""
    ...

def is_normalized(
    text: str,
    *,
    form: Literal["NFC", "NFD", "NFKC", "NFKD"] = "NFC",
) -> bool:
    """True if text is already in the specified normalization form."""
    ...

# --- Stateful objects ---

@final
class Slugifier:
    """Reusable configured slugifier. Call as slugifier(text) → str."""

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
    ) -> None: ...
    def __call__(self, text: str) -> str: ...
    def __repr__(self) -> str: ...

@final
class UniqueSlugifier:
    """Stateful slugifier that appends incrementing suffixes for uniqueness."""

    def __init__(
        self,
        *,
        check: Callable[[str], bool] | None = None,
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
    ) -> None: ...
    def __call__(self, text: str) -> str: ...
    def reset(self) -> None:
        """Clear the internal set of seen slugs."""
        ...
    def __repr__(self) -> str: ...

@final
class TextPipeline:
    """Composable, pre-compiled text cleaning pipeline."""

    def __init__(
        self,
        *,
        normalize: Literal["NFC", "NFD", "NFKC", "NFKD"] | None = None,
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
    def __call__(self, text: str) -> str: ...
    def __repr__(self) -> str: ...

# --- Language profiles ---

def list_langs() -> list[str]:
    """Return available language codes for transliteration."""
    ...

def register_lang(code: str, mappings: dict[str, str]) -> None:
    """Register or override a transliteration mapping for a language code."""
    ...

def register_replacements(replacements: dict[str, str]) -> None:
    """Register global pre-transliteration replacements."""
    ...

def remove_replacement(key: str) -> bool:
    """Remove a single global pre-transliteration replacement by key."""
    ...

def clear_replacements() -> None:
    """Clear all global pre-transliteration replacements."""
    ...

# --- Compatibility aliases ---

def unidecode(text: str) -> str:
    """Drop-in replacement for Unidecode's unidecode()."""
    ...

def ascii_fold(text: str) -> str:
    """Alias for strip_accents (Elasticsearch/Solr terminology)."""
    ...

# --- Exception ---

class UnirustError(ValueError):
    """Base exception for unirust errors."""

    ...
