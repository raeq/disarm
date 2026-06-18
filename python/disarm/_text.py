"""Fluent text-processing builder for disarm.

Usage::

    from disarm import Text

    result = (Text("  Héllo   Straße  ")
        .normalize(form="NFC")
        .transliterate(lang="de")
        .fold_case()
        .collapse_whitespace()
        .value)

Each transform method returns a **new** ``Text`` instance (immutable
semantics, matching Python ``str``).  Predicates return their native
type (``bool``, ``list``) and do not chain.
"""

from __future__ import annotations

import importlib
import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from disarm._enums import Script
    from disarm._types import (
        EmojiProvider,
        ErrorMode,
        NormalizationForm,
        Platform,
        TransliterateErrorMode,
    )


def _get_translit():
    """Lazy-load the disarm module once, then cache on the class.

    The import is deferred rather than top-level to avoid a circular dependency:
    ``disarm.__init__`` imports ``Text`` from this module (``disarm._text``),
    so importing ``disarm`` at module-load time here would create a circular
    import.  (#127)
    """
    return importlib.import_module("disarm")


class Text:
    """Immutable wrapper for fluent Unicode text processing.

    Wrap a string, chain transforms in any order, extract with ``.value``
    or ``str()``.

    Examples:
        >>> from disarm import Text
        >>> Text("Straße").fold_case().value
        'strasse'
        >>> Text("  hello   world  ").collapse_whitespace().value
        'hello world'
        >>> str(Text("café").strip_accents())
        'cafe'
    """

    __slots__ = ("_value",)

    # Module reference cached on the class after first access.
    _mod = None

    @classmethod
    def _t(cls):
        if cls._mod is None:
            cls._mod = _get_translit()
        return cls._mod

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
        return Text(self._t().normalize(self._value, form=form))

    def normalize_confusables(self, *, target_script: str = "latin") -> Text:
        """Replace confusable homoglyphs with target-script equivalents."""
        return Text(self._t().normalize_confusables(self._value, target_script=target_script))

    def strip_accents(self) -> Text:
        """Remove diacritical marks, preserving base characters."""
        return Text(self._t().strip_accents(self._value))

    def transliterate(
        self,
        *,
        lang: str | None = None,
        target: str | None = None,
        errors: TransliterateErrorMode = "replace",
        replace_with: str = "[?]",
        strict_iso9: bool = False,
        gost7034: bool = False,
        tones: bool = False,
        context: bool = False,
    ) -> Text:
        """Unicode → ASCII transliteration."""
        # #129: tones and context are forwarded to the underlying transliterate()
        return Text(
            self._t().transliterate(
                self._value,
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

    def fold_case(self) -> Text:
        """Full Unicode case folding per CaseFolding.txt (1,557 mappings).

        Covers Latin, Greek, Cyrillic, Armenian, Georgian, Cherokee,
        Adlam, Deseret, Osage, Warang Citi, fullwidth Latin, and all
        ligature expansions.  Equivalent to ``str.casefold()``.
        """
        return Text(self._t().fold_case(self._value))

    def collapse_whitespace(self) -> Text:
        """Fold whitespace runs to single ASCII spaces, trimming the ends (#433).

        Folds whitespace only — it does not delete control or zero-width
        characters. The line controls (CR/VT/FF/NEL/…) fold to a space rather
        than being deleted, so ``"a\\rb"`` becomes ``"a b"``."""
        return Text(self._t().collapse_whitespace(self._value))

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
        """Generate a URL-safe slug.

        ``default`` is the fallback when the slug would be empty; it is
        sanitized through the same slug pipeline before being returned (#169,
        #193). See :func:`disarm.slugify`.
        """
        return Text(
            self._t().slugify(
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
                default=default,
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
        return Text(
            self._t().sanitize_filename(
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
        return Text(
            self._t().demojize(
                self._value,
                strip_modifiers=strip_modifiers,
                errors=errors,
                replace_with=replace_with,
                provider=provider,
            )
        )

    def strip_bidi(self) -> Text:
        """Strip bidirectional override and formatting characters."""
        return Text(self._t().strip_bidi(self._value))

    def canonicalize(self) -> Text:
        """Apply the canonicalize precompiled pipeline.

        NFKC → strip bidi/format → strip invisibles (#413) → strip control →
        strip zero-width → collapse whitespace → cap combining marks
        (anti-zalgo, #429) → NFC → confusables → NFC (the confusable fold is
        NFC-sandwiched and iterated to a fixed point for idempotency, #416/#434).
        """
        return Text(self._t().canonicalize(self._value))

    def security_clean(self) -> Text:
        """Deprecated alias for :meth:`canonicalize` (#430); removed in 1.0."""
        warnings.warn(
            "Text.security_clean is deprecated; use Text.canonicalize (removed in 1.0)",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.canonicalize()

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
        return Text(self._t().ml_normalize(self._value, lang=lang, emoji=emoji))

    def strip_format(self) -> Text:
        """Apply the strip_format precompiled pipeline.

        Strip bidi/format and invisibles, collapse whitespace, strip control
        and zero-width characters.
        """
        return Text(self._t().strip_format(self._value))

    def display_clean(self) -> Text:
        """Deprecated alias for :meth:`strip_format` (#430); removed in 1.0."""
        warnings.warn(
            "Text.display_clean is deprecated; use Text.strip_format (removed in 1.0)",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.strip_format()

    # ── Non-chaining predicates ──────────────────────────────────

    def is_ascii(self) -> bool:
        """True if all characters are U+0000–U+007F."""
        return self._t().is_ascii(self._value)

    def is_normalized(self, *, form: NormalizationForm = "NFC") -> bool:
        """True if already in the specified normalization form."""
        return self._t().is_normalized(self._value, form=form)

    def is_confusable(self, *, target_script: str = "latin") -> bool:
        """True if text contains confusable homoglyphs."""
        return self._t().is_confusable(self._value, target_script=target_script)

    def is_mixed_script(self) -> bool:
        """True if text contains characters from multiple Unicode scripts."""
        return self._t().is_mixed_script(self._value)

    def has_bidi_conflict(self) -> bool:
        """True if text mixes strong left-to-right and strong right-to-left characters."""
        return self._t().has_bidi_conflict(self._value)

    def detect_scripts(self) -> list[Script]:
        """Return Unicode scripts present, in order of first appearance."""
        return self._t().detect_scripts(self._value)

    def grapheme_len(self) -> int:
        """Count user-perceived characters (extended grapheme clusters)."""
        return self._t().grapheme_len(self._value)

    def grapheme_split(self) -> list[str]:
        """Split into extended grapheme clusters."""
        return self._t().grapheme_split(self._value)

    def grapheme_truncate(self, max_graphemes: int) -> Text:
        """Truncate to at most *max_graphemes* grapheme clusters."""
        return Text(self._t().grapheme_truncate(self._value, max_graphemes))

    def catalog_key(
        self,
        *,
        lang: str | None = None,
        strict_iso9: bool = False,
    ) -> Text:
        """Library catalog key generation for bibliographic deduplication."""
        return Text(self._t().catalog_key(self._value, lang=lang, strict_iso9=strict_iso9))
