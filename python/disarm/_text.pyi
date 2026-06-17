"""Type stubs for disarm.Text fluent builder."""

from collections.abc import Iterable

from disarm._enums import Script
from disarm._types import EmojiProvider, ErrorMode, NormalizationForm, Platform

class Text:
    """Immutable wrapper for fluent Unicode text processing."""

    def __init__(self, text: str) -> None: ...
    @property
    def value(self) -> str:
        """Return the underlying string."""
        ...
    def __str__(self) -> str: ...
    def __repr__(self) -> str: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...
    def __len__(self) -> int: ...
    def __bool__(self) -> bool: ...

    # Chainable transforms
    def normalize(self, *, form: NormalizationForm = "NFC") -> Text:
        """Unicode normalization (NFC, NFD, NFKC, NFKD)."""
        ...
    def normalize_confusables(self, *, target_script: str = "latin") -> Text:
        """Replace confusable homoglyphs with target-script equivalents."""
        ...
    def strip_accents(self) -> Text:
        """Remove diacritical marks, preserving base characters."""
        ...
    def transliterate(
        self,
        *,
        lang: str | None = None,
        target: str | None = None,
        errors: ErrorMode = "replace",
        replace_with: str = "[?]",
        strict_iso9: bool = False,
        gost7034: bool = False,
        tones: bool = False,
        context: bool = False,
    ) -> Text:
        """Unicode → ASCII transliteration."""
        ...
    def fold_case(self) -> Text:
        """Full Unicode case folding (1,557 mappings from CaseFolding.txt)."""
        ...
    def collapse_whitespace(
        self,
        *,
        strip_control: bool = True,
        strip_zero_width: bool = True,
    ) -> Text:
        """Normalize whitespace to single ASCII spaces."""
        ...
    def slugify(
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
    ) -> Text:
        """Generate a URL-safe slug."""
        ...
    def sanitize_filename(
        self,
        *,
        separator: str = "_",
        max_length: int = 255,
        platform: Platform = "universal",
        lang: str | None = None,
        preserve_extension: bool = True,
    ) -> Text:
        """Sanitize into a safe filename."""
        ...
    def demojize(
        self,
        *,
        strip_modifiers: bool = False,
        errors: ErrorMode = "replace",
        replace_with: str = "[?]",
        provider: EmojiProvider | None = None,
    ) -> Text:
        """Expand emoji to CLDR short-name text descriptions."""
        ...
    def strip_bidi(self) -> Text:
        """Strip bidirectional override and formatting characters."""
        ...
    def security_clean(self) -> Text:
        """Apply the security_clean pipeline (NFKC → confusables → bidi → whitespace)."""
        ...
    def ml_normalize(
        self,
        *,
        lang: str | None = None,
        emoji: str = "cldr",
    ) -> Text:
        """Apply the ML/NLP normalization pipeline."""
        ...
    def display_clean(self) -> Text:
        """Apply display-safe text cleaning."""
        ...

    # Non-chaining predicates
    def is_ascii(self) -> bool:
        """True if all characters are U+0000–U+007F."""
        ...
    def is_normalized(self, *, form: NormalizationForm = "NFC") -> bool:
        """True if already in the specified normalization form."""
        ...
    def is_confusable(self, *, target_script: str = "latin") -> bool:
        """True if text contains confusable homoglyphs."""
        ...
    def is_mixed_script(self) -> bool:
        """True if text contains characters from multiple Unicode scripts."""
        ...
    def has_bidi_conflict(self) -> bool:
        """True if text mixes strong left-to-right and right-to-left characters."""
        ...
    def detect_scripts(self) -> list[Script]:
        """Return Unicode scripts present, in order of first appearance."""
        ...
    def grapheme_len(self) -> int:
        """Count user-perceived characters (extended grapheme clusters)."""
        ...
    def grapheme_split(self) -> list[str]:
        """Split into extended grapheme clusters."""
        ...
    def grapheme_truncate(self, max_graphemes: int) -> Text:
        """Truncate to at most *max_graphemes* grapheme clusters."""
        ...
    def catalog_key(
        self,
        *,
        lang: str | None = None,
        strict_iso9: bool = False,
    ) -> Text:
        """Library catalog key generation for bibliographic deduplication."""
        ...
