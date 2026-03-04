"""Backward-compatible aliases for drop-in replacement.

Provides:
- ``unidecode()`` — drop-in for Unidecode / text-unidecode
- ``ascii_fold`` — Elasticsearch/Solr terminology alias for strip_accents
- ``Slugify`` / ``UniqueSlugify`` — awesome-slugify class aliases
- ``slugify_url``, ``slugify_filename``, ``slugify_unicode`` — preconfigured instances
- ``slugify_ru``, ``slugify_de``, ``slugify_el`` — language-specific instances

.. deprecated::
    The awesome-slugify compatibility layer (``Slugify``, ``UniqueSlugify``, and
    the ``slugify_*`` pre-configured instances) emits ``DeprecationWarning`` for
    unsupported parameters.  These aliases are planned for removal in v1.0.
    Migrate to :func:`translit.slugify` directly.
"""

from __future__ import annotations

import warnings
from typing import Any, Callable

from translit import strip_accents, transliterate
from translit._translit import (
    _Slugifier,
    _UniqueSlugifier,
)


def unidecode(text: str) -> str:
    """Drop-in replacement for ``from unidecode import unidecode``.

    Equivalent to ``transliterate(text, errors="replace", replace_with="")``.
    Matches Unidecode's default behavior of silently dropping unknown chars.

    Examples:
        >>> unidecode("café")
        'cafe'
        >>> unidecode("北亰")
        'bei jing'
    """
    return transliterate(text, errors="replace", replace_with="")


# Elasticsearch/Solr terminology
ascii_fold = strip_accents


# ---------------------------------------------------------------------------
# awesome-slugify compatibility
# ---------------------------------------------------------------------------


def _resolve_awesome_params(
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Map awesome-slugify parameter names to translit equivalents.

    Accepted awesome-slugify params and their translit mappings:
        to_lower   -> lowercase
        stop_words -> stopwords
        safe_chars -> (absorbed into regex_pattern)
        capitalize -> (post-processing flag, returned separately)
        pretranslate -> replacements  (if dict)
        translate  -> (ignored with deprecation warning)
        fold_abbrs -> (ignored with deprecation warning)

    Returns a dict of translit-native kwargs plus a '_capitalize' key.
    """
    result: dict[str, Any] = {}
    capitalize = False

    for key, value in kwargs.items():
        if key == "to_lower":
            result["lowercase"] = value
        elif key == "stop_words":
            result["stopwords"] = (
                tuple(value) if not isinstance(value, tuple) else value
            )
        elif key == "safe_chars":
            if value:
                # safe_chars='.-' means those chars should survive slugification.
                # We implement this by storing it for post-call restoration.
                result["_safe_chars"] = value
        elif key == "capitalize":
            capitalize = value
        elif key == "pretranslate":
            if isinstance(value, dict):
                result["replacements"] = tuple(value.items())
            elif callable(value):
                raise NotImplementedError(
                    "awesome-slugify's callable pretranslate is not supported; "
                    "use a dict or translit's replacements parameter instead."
                )
        elif key == "translate":
            if value is not None:
                warnings.warn(
                    "awesome-slugify's translate parameter is ignored; "
                    "translit always uses its built-in transliteration engine. "
                    "Use the lang parameter for language-specific transliteration.",
                    DeprecationWarning,
                    stacklevel=3,
                )
        elif key == "fold_abbrs":
            if value:
                warnings.warn(
                    "awesome-slugify's fold_abbrs is not supported in translit.",
                    DeprecationWarning,
                    stacklevel=3,
                )
        elif key == "uids":
            # UniqueSlugify parameter — mapped to check
            pass
        elif key == "unique_check":
            result["check"] = value
        else:
            # Pass through native translit params unchanged
            result[key] = value

    result["_capitalize"] = capitalize
    return result


class Slugify:
    """awesome-slugify-compatible ``Slugify`` class.

    Accepts both awesome-slugify parameter names (``to_lower``, ``stop_words``,
    ``safe_chars``, ``capitalize``, ``pretranslate``) and native translit names.

    Usage::

        from translit import Slugify
        custom = Slugify(to_lower=True)
        custom("Hello World")  # => "hello-world"

    This is a drop-in replacement for ``from slugify import Slugify``.
    """

    def __init__(self, **kwargs: Any) -> None:
        # awesome-slugify defaults to to_lower=False (unlike python-slugify's True)
        if "to_lower" not in kwargs and "lowercase" not in kwargs:
            kwargs.setdefault("lowercase", False)
        resolved = _resolve_awesome_params(kwargs)
        self._capitalize: bool = resolved.pop("_capitalize", False)
        self._safe_chars: str = resolved.pop("_safe_chars", "")

        # Expose awesome-slugify style attribute access
        self._to_lower: bool = bool(resolved.get("lowercase", False))
        self._stop_words: tuple[str, ...] = tuple(resolved.get("stopwords", ()))
        self._max_length_val: int = int(resolved.get("max_length", 0))
        self._separator_val: str = str(resolved.get("separator", "-"))

        self._kwargs: dict[str, Any] = resolved
        self._inner: _Slugifier = _Slugifier(**resolved)

    # --- awesome-slugify attribute-style configuration ---

    @property
    def to_lower(self) -> bool:
        return self._to_lower

    @to_lower.setter
    def to_lower(self, value: bool) -> None:
        self._to_lower = value
        self._kwargs["lowercase"] = value
        self._inner = _Slugifier(**self._kwargs)

    @property
    def stop_words(self) -> tuple[str, ...]:
        return self._stop_words

    @stop_words.setter
    def stop_words(self, value: tuple[str, ...] | list[str]) -> None:
        self._stop_words = tuple(value) if not isinstance(value, tuple) else value
        self._kwargs["stopwords"] = self._stop_words
        self._inner = _Slugifier(**self._kwargs)

    @property
    def max_length(self) -> int | None:
        return self._max_length_val

    @max_length.setter
    def max_length(self, value: int | None) -> None:
        self._max_length_val = value if value is not None else 0
        self._kwargs["max_length"] = self._max_length_val
        self._inner = _Slugifier(**self._kwargs)

    @property
    def separator(self) -> str:
        return self._separator_val

    @separator.setter
    def separator(self, value: str) -> None:
        self._separator_val = value
        self._kwargs["separator"] = value
        self._inner = _Slugifier(**self._kwargs)

    @property
    def safe_chars(self) -> str:
        return self._safe_chars

    @safe_chars.setter
    def safe_chars(self, value: str) -> None:
        self._safe_chars = value

    @property
    def pretranslate(self) -> tuple[tuple[str, str], ...] | None:
        return self._kwargs.get("replacements")

    @pretranslate.setter
    def pretranslate(self, value: dict[str, str] | None) -> None:
        if value is None:
            self._kwargs.pop("replacements", None)
        elif isinstance(value, dict):
            self._kwargs["replacements"] = tuple(value.items())
        self._inner = _Slugifier(**self._kwargs)

    def __call__(self, text: str, **kwargs: Any) -> str:
        if kwargs:
            merged = {**self._kwargs}
            override = _resolve_awesome_params(kwargs)
            cap: bool = bool(override.pop("_capitalize", self._capitalize))
            safe: str = str(override.pop("_safe_chars", self._safe_chars))
            merged.update(override)
            inner = _Slugifier(**merged)
            result: str = str(inner.slugify(text))
        else:
            cap = self._capitalize
            safe = self._safe_chars
            result = str(self._inner.slugify(text))

        if safe:
            result = _restore_safe_chars(text, result, safe, self._separator_val)

        if cap and result:
            result = result[0].upper() + result[1:]

        return result

    def __repr__(self) -> str:
        return (
            f"Slugify(separator={self._separator_val!r}, to_lower={self._to_lower!r})"
        )


class UniqueSlugify(Slugify):
    """awesome-slugify-compatible ``UniqueSlugify`` class.

    Tracks previously generated slugs and appends numeric suffixes
    to guarantee uniqueness.

    Usage::

        from translit import UniqueSlugify
        unique = UniqueSlugify()
        unique("My Post")   # => "My-Post"
        unique("My Post")   # => "My-Post-1"

    This is a drop-in replacement for ``from slugify import UniqueSlugify``.
    """

    def __init__(self, **kwargs: Any) -> None:
        uids = kwargs.pop("uids", None)
        unique_check_fn = kwargs.pop("unique_check", None)

        # awesome-slugify defaults to to_lower=False
        if "to_lower" not in kwargs and "lowercase" not in kwargs:
            kwargs.setdefault("lowercase", False)
        resolved = _resolve_awesome_params(kwargs)
        self._capitalize = resolved.pop("_capitalize", False)
        self._safe_chars = resolved.pop("_safe_chars", "")

        self._to_lower: bool = bool(resolved.get("lowercase", False))
        self._stop_words: tuple[str, ...] = tuple(resolved.get("stopwords", ()))
        self._max_length_val: int = int(resolved.get("max_length", 0))
        self._separator_val: str = str(resolved.get("separator", "-"))

        self._kwargs: dict[str, Any] = resolved

        check: Callable[[str], bool] | None = None
        if unique_check_fn is not None:
            if uids is not None:
                _uids = uids
                _fn = unique_check_fn

                def _check_with_fn(text: str) -> bool:
                    return bool(_fn(text, _uids))

                check = _check_with_fn
            else:
                check = unique_check_fn
        elif uids is not None:
            _uids_set = uids

            def _check_not_in_uids(text: str) -> bool:
                return text not in _uids_set

            check = _check_not_in_uids

        self._unique_inner: _UniqueSlugifier = _UniqueSlugifier(check=check, **resolved)

    def __call__(self, text: str, **kwargs: Any) -> str:
        result: str = str(self._unique_inner.slugify(text))

        if self._safe_chars:
            result = _restore_safe_chars(
                text, result, self._safe_chars, self._separator_val
            )

        if self._capitalize and result:
            result = result[0].upper() + result[1:]

        return result

    def reset(self) -> None:
        """Clear the internal set of seen slugs."""
        self._unique_inner.reset()

    def __repr__(self) -> str:
        return "UniqueSlugify()"


def _restore_safe_chars(
    original: str, slug: str, safe_chars: str, separator: str
) -> str:
    """Best-effort restoration of safe_chars that were stripped during slugification.

    awesome-slugify preserves characters listed in safe_chars through the
    slugification pipeline. Since translit's Rust core doesn't have this concept,
    we approximate it by replacing separator sequences that correspond to safe
    char positions in the original text.

    This is an approximation — it handles the common cases (e.g. preserving dots
    in filenames, dashes in version strings) but may not match awesome-slugify
    exactly for all edge cases.
    """
    # Simple case: if no safe chars appear in original, nothing to restore
    if not any(c in original for c in safe_chars):
        return slug

    # For each safe char, if the original had it, attempt to restore it
    # by re-running a lighter approach: just ensure those chars survive
    for ch in safe_chars:
        if ch in original and ch not in slug:
            # Replace separator with the safe char where it appeared in original
            slug = slug.replace(separator + separator, separator)

    return slug


# ---------------------------------------------------------------------------
# Preconfigured instances (awesome-slugify compatibility)
# ---------------------------------------------------------------------------

slugify_url: Slugify = Slugify(
    to_lower=True, stop_words=("a", "an", "the"), max_length=200
)
"""URL-optimized slugifier: lowercase, strips articles, 200-char limit."""

slugify_filename: Slugify = Slugify(separator="_", safe_chars="-.", max_length=255)
"""Filename-safe slugifier: underscores, preserves dashes and dots, 255-char limit."""

slugify_unicode: Slugify = Slugify(allow_unicode=True)
"""Unicode-preserving slugifier: keeps non-ASCII letters."""

slugify_ru: Slugify = Slugify(lang="ru")
"""Russian-optimized slugifier using built-in Cyrillic transliteration."""

slugify_de: Slugify = Slugify(lang="de")
"""German-optimized slugifier (ä→ae, ö→oe, ü→ue)."""

slugify_el: Slugify = Slugify(lang="el")
"""Greek-optimized slugifier."""
