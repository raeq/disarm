"""Fluent text-processing builder for translit.

Usage::

    from translit import Text

    result = (Text("  Héllo   Straße  ")
        .normalize("NFC")
        .transliterate(lang="de")
        .fold_case()
        .collapse_whitespace()
        .value)

Each transform method returns a **new** ``Text`` instance (immutable
semantics, matching Python ``str``).  Predicates return their native
type (``bool``, ``list``) and do not chain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from translit._enums import Script
    from translit._types import EmojiProvider, ErrorMode, NormalizationForm, Platform


class Text:
    """Immutable wrapper for fluent Unicode text processing.

    Wrap a string, chain transforms in any order, extract with ``.value``
    or ``str()``.

    Examples:
        >>> from translit import Text
        >>> Text("Straße").fold_case().value
        'strasse'
        >>> Text("  hello   world  ").collapse_whitespace().value
        'hello world'
        >>> str(Text("café").strip_accents())
        'cafe'
    """

    __slots__ = ("_value",)

    def __init__(self, text: str) -> None:
        self._value = str(text)

    # ── Result extraction ────────────────────────────────────────

    @property
    def value(self) -> str:
        """Return the underlying string."""
        return self._value

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        v = self._value
        if len(v) > 40:
            v = v[:40] + "..."
        return f"Text({v!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Text):
            return self._value == other._value
        if isinstance(other, str):
            return self._value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)

    def __len__(self) -> int:
        return len(self._value)

    def __bool__(self) -> bool:
        return bool(self._value)

    # ── Chainable transforms (each returns a new Text) ───────────

    def normalize(self, *, form: NormalizationForm = "NFC") -> Text:
        """Unicode normalization (NFC, NFD, NFKC, NFKD)."""
        from translit import normalize as _normalize

        return Text(_normalize(self._value, form=form))

    def normalize_confusables(self, *, target_script: str = "latin") -> Text:
        """Replace confusable homoglyphs with target-script equivalents."""
        from translit import normalize_confusables as _normalize_confusables

        return Text(_normalize_confusables(self._value, target_script=target_script))

    def strip_accents(self) -> Text:
        """Remove diacritical marks, preserving base characters."""
        from translit import strip_accents as _strip_accents

        return Text(_strip_accents(self._value))

    def transliterate(
        self,
        *,
        lang: str | None = None,
        errors: ErrorMode = "replace",
        replace_with: str = "[?]",
        strict_iso9: bool = False,
    ) -> Text:
        """Unicode → ASCII transliteration."""
        from translit import transliterate as _transliterate

        return Text(
            _transliterate(
                self._value,
                lang=lang,
                errors=errors,
                replace_with=replace_with,
                strict_iso9=strict_iso9,
            )
        )

    def fold_case(self) -> Text:
        """Full Unicode case folding per CaseFolding.txt (1,557 mappings).

        Covers Latin, Greek, Cyrillic, Armenian, Georgian, Cherokee,
        Adlam, Deseret, Osage, Warang Citi, fullwidth Latin, and all
        ligature expansions.  Equivalent to ``str.casefold()``.
        """
        from translit import fold_case as _fold_case

        return Text(_fold_case(self._value))

    def collapse_whitespace(
        self,
        *,
        strip_control: bool = True,
        strip_zero_width: bool = True,
    ) -> Text:
        """Normalize whitespace to single ASCII spaces; optionally strip
        control characters and zero-width characters."""
        from translit import collapse_whitespace as _collapse_whitespace

        return Text(
            _collapse_whitespace(
                self._value,
                strip_control=strip_control,
                strip_zero_width=strip_zero_width,
            )
        )

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
    ) -> Text:
        """Generate a URL-safe slug."""
        from translit import slugify as _slugify

        return Text(
            _slugify(
                self._value,
                separator=separator,
                lowercase=lowercase,
                max_length=max_length,
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
        )

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
        from translit import sanitize_filename as _sanitize_filename

        return Text(
            _sanitize_filename(
                self._value,
                separator=separator,
                max_length=max_length,
                platform=platform,
                lang=lang,
                preserve_extension=preserve_extension,
            )
        )

    def demojize(
        self,
        *,
        strip_modifiers: bool = False,
        errors: ErrorMode = "replace",
        replace_with: str = "[?]",
        provider: EmojiProvider | None = None,
    ) -> Text:
        """Expand emoji to CLDR short-name text descriptions."""
        from translit import demojize as _demojize

        return Text(
            _demojize(
                self._value,
                strip_modifiers=strip_modifiers,
                errors=errors,
                replace_with=replace_with,
                provider=provider,
            )
        )

    def strip_bidi(self) -> Text:
        """Strip bidirectional override and formatting characters."""
        from translit import strip_bidi as _strip_bidi

        return Text(_strip_bidi(self._value))

    def security_clean(self) -> Text:
        """Apply the security_clean precompiled pipeline.

        NFKC → confusables → collapse_whitespace → strip bidi/format.
        """
        from translit import security_clean as _security_clean

        return Text(_security_clean(self._value))

    def ml_normalize(
        self,
        *,
        lang: str | None = None,
        emoji: str = "cldr",
    ) -> Text:
        """Apply the ml_normalize precompiled pipeline.

        NFKC → emoji→text → [transliterate] → strip_accents →
        fold_case → collapse_whitespace.
        """
        from translit import ml_normalize as _ml_normalize

        return Text(_ml_normalize(self._value, lang=lang, emoji=emoji))

    def display_clean(self) -> Text:
        """Apply the display_clean precompiled pipeline.

        Collapse whitespace, strip control and zero-width characters.
        """
        from translit import display_clean as _display_clean

        return Text(_display_clean(self._value))

    # ── Non-chaining predicates ──────────────────────────────────

    def is_ascii(self) -> bool:
        """True if all characters are U+0000–U+007F."""
        from translit import is_ascii as _is_ascii

        return _is_ascii(self._value)

    def is_normalized(self, *, form: NormalizationForm = "NFC") -> bool:
        """True if already in the specified normalization form."""
        from translit import is_normalized as _is_normalized

        return _is_normalized(self._value, form=form)

    def is_confusable(self, *, target_script: str = "latin") -> bool:
        """True if text contains confusable homoglyphs."""
        from translit import is_confusable as _is_confusable

        return _is_confusable(self._value, target_script=target_script)

    def is_mixed_script(self) -> bool:
        """True if text contains characters from multiple Unicode scripts."""
        from translit import is_mixed_script as _is_mixed_script

        return _is_mixed_script(self._value)

    def detect_scripts(self) -> list[Script]:
        """Return Unicode scripts present, in order of first appearance."""
        from translit import detect_scripts as _detect_scripts

        return _detect_scripts(self._value)

    def grapheme_len(self) -> int:
        """Count user-perceived characters (extended grapheme clusters)."""
        from translit import grapheme_len as _grapheme_len

        return _grapheme_len(self._value)

    def grapheme_split(self) -> list[str]:
        """Split into extended grapheme clusters."""
        from translit import grapheme_split as _grapheme_split

        return _grapheme_split(self._value)

    def grapheme_truncate(self, max_graphemes: int) -> Text:
        """Truncate to at most *max_graphemes* grapheme clusters."""
        from translit import grapheme_truncate as _grapheme_truncate

        return Text(_grapheme_truncate(self._value, max_graphemes))

    def catalog_key(
        self,
        *,
        lang: str | None = None,
        strict_iso9: bool = False,
    ) -> Text:
        """Library catalog key generation for bibliographic deduplication."""
        from translit import catalog_key as _catalog_key

        return Text(_catalog_key(self._value, lang=lang, strict_iso9=strict_iso9))
