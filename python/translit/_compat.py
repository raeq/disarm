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

from translit import find_untranslatable, strip_accents, transliterate
from translit._translit import (
    InvalidArgumentError,
    UnsupportedError,
    _Slugifier,
    _UniqueSlugifier,
)


def unidecode(text: str, errors: str = "ignore", replace_str: str = "?") -> str:
    """Drop-in replacement for ``from unidecode import unidecode``.

    Mirrors the Unidecode 1.3 signature
    ``unidecode(string, errors="ignore", replace_str="?")`` (#72), mapping
    Unidecode's *errors* values onto translit's native error modes:

    - ``"ignore"`` (default) — drop unmapped characters.
    - ``"replace"`` — substitute each unmapped character with *replace_str*
      (Unidecode's default is ``"?"``).
    - ``"preserve"`` — keep unmapped characters verbatim.
    - ``"strict"`` — raise ``ValueError`` on the first unmapped character
      (Unidecode raises ``UnidecodeError``; this shim raises a ``ValueError``
      carrying the offending character and its index, to match Unidecode's
      ValueError-on-strict contract).

    Examples:
        >>> unidecode("café")
        'cafe'
        >>> unidecode("北亰")
        'bei jing'
        >>> unidecode("a→b", errors="replace", replace_str="?")
        'a?b'
    """
    if errors == "ignore":
        return transliterate(text, errors="ignore")
    if errors == "replace":
        return transliterate(text, errors="replace", replace_with=replace_str)
    if errors == "preserve":
        return transliterate(text, errors="preserve")
    if errors == "strict":
        # Retired the old O(n)-per-character re-transliteration hack onto the
        # native scan (#184). `find_untranslatable` returns each unmapped
        # character with its byte offset; raise on the first, reporting the
        # *character* index (Unidecode's contract). The bare `ValueError` is
        # deliberate — Unidecode's strict mode raises ValueError, and this shim
        # mimics it exactly (translit's own native strict mode raises a
        # TranslitError; see transliterate(errors="strict")).
        untranslatable = find_untranslatable(text)
        if untranslatable:
            ch, byte_offset = untranslatable[0]
            char_index = len(text.encode("utf-8")[:byte_offset].decode("utf-8"))
            raise ValueError(f"no replacement found for character {ch!r} at index {char_index}")
        return transliterate(text)
    # Invalid `errors` argument to this shim — a translit-owned error (#183).
    raise InvalidArgumentError(
        f"invalid value for errors: {errors!r} "
        "(expected 'ignore', 'strict', 'replace', or 'preserve')"
    )


# Elasticsearch/Solr terminology
ascii_fold = strip_accents


# ---------------------------------------------------------------------------
# awesome-slugify compatibility
# ---------------------------------------------------------------------------


# Simple renames: awesome-slugify name → translit name.
_AWESOME_PARAM_RENAMES: dict[str, str] = {
    "to_lower": "lowercase",
    "unique_check": "check",
}

# Parameters that emit deprecation warnings when used.
# #131: "uids" removed — it is not deprecated, just wrong-class; handled separately below.
_AWESOME_DEPRECATED_PARAMS: dict[str, str] = {
    "translate": (
        "awesome-slugify's translate parameter is ignored; "
        "translit always uses its built-in transliteration engine. "
        "Use the lang parameter for language-specific transliteration."
    ),
    "fold_abbrs": "awesome-slugify's fold_abbrs is not supported in translit.",
}


def _resolve_awesome_params(
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Map awesome-slugify parameter names to translit equivalents.

    Accepted awesome-slugify params and their translit mappings:
        to_lower     -> lowercase
        stop_words   -> stopwords  (coerced to tuple)
        safe_chars   -> _safe_chars  (post-processing, not passed to Rust)
        capitalize   -> _capitalize  (post-processing flag)
        pretranslate -> replacements  (if dict; callable raises NotImplementedError)
        translate    -> (ignored with DeprecationWarning)
        fold_abbrs   -> (ignored with DeprecationWarning)
        unique_check -> check

    Returns a dict of translit-native kwargs plus a '_capitalize' key.
    """
    result: dict[str, Any] = {}
    capitalize = False

    for key, value in kwargs.items():
        # Simple renames
        if key in _AWESOME_PARAM_RENAMES:
            result[_AWESOME_PARAM_RENAMES[key]] = value
        # Coerced rename
        elif key == "stop_words":
            result["stopwords"] = tuple(value) if not isinstance(value, tuple) else value
        # Post-processing flags (not passed to Rust)
        elif key == "safe_chars":
            if value:
                result["_safe_chars"] = value
        elif key == "capitalize":
            capitalize = value
        # Complex transform
        elif key == "pretranslate":
            if isinstance(value, dict):
                result["replacements"] = tuple(value.items())
            elif callable(value):
                raise UnsupportedError(
                    "awesome-slugify's callable pretranslate is not supported; "
                    "use a dict or translit's replacements parameter instead."
                )
        # #131: "uids" is a UniqueSlugify-only param; passing it to Slugify is a
        # wrong-class error, not a deprecation — emit UserWarning, not DeprecationWarning.
        elif key == "uids":
            warnings.warn(
                "The 'uids' parameter is only supported by UniqueSlugify; it is ignored by Slugify.",
                UserWarning,
                stacklevel=3,
            )
        # Deprecated params
        elif key in _AWESOME_DEPRECATED_PARAMS:
            # #122: rewritten as explicit if/elif/else to avoid operator-precedence
            # ambiguity in the original ternary expression.
            # - "translate": warn whenever the value is not None (any value is a misuse)
            # - "fold_abbrs": warn only when the value is truthy (False/None means no-op)
            if key == "translate":
                should_warn = value is not None
            elif key == "fold_abbrs":
                should_warn = bool(value)
            else:
                should_warn = value is not None
            if should_warn:
                warnings.warn(
                    _AWESOME_DEPRECATED_PARAMS[key],
                    DeprecationWarning,
                    stacklevel=3,
                )
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
        self._dirty: bool = False

    def _ensure_inner(self) -> _Slugifier:
        """Rebuild the inner _Slugifier only if a property was changed."""
        if self._dirty:
            self._inner = _Slugifier(**self._kwargs)
            self._dirty = False
        return self._inner

    # --- awesome-slugify attribute-style configuration ---

    @property
    def to_lower(self) -> bool:
        return self._to_lower

    @to_lower.setter
    def to_lower(self, value: bool) -> None:
        self._to_lower = value
        self._kwargs["lowercase"] = value
        self._dirty = True

    @property
    def stop_words(self) -> tuple[str, ...]:
        return self._stop_words

    @stop_words.setter
    def stop_words(self, value: tuple[str, ...] | list[str]) -> None:
        self._stop_words = tuple(value) if not isinstance(value, tuple) else value
        self._kwargs["stopwords"] = self._stop_words
        self._dirty = True

    @property
    def max_length(self) -> int | None:
        return self._max_length_val

    @max_length.setter
    def max_length(self, value: int | None) -> None:
        self._max_length_val = value if value is not None else 0
        self._kwargs["max_length"] = self._max_length_val
        self._dirty = True

    @property
    def separator(self) -> str:
        return self._separator_val

    @separator.setter
    def separator(self, value: str) -> None:
        self._separator_val = value
        self._kwargs["separator"] = value
        self._dirty = True

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
        else:
            raise TypeError(
                f"pretranslate must be dict[str, str] or None, got {type(value).__name__}"
            )
        self._dirty = True

    def _apply_post_processing(
        self, text: str, result: str, capitalize: bool, safe_chars: str
    ) -> str:
        """Apply safe-char restoration and capitalization after slugification."""
        if safe_chars:
            result = _restore_safe_chars(text, result, safe_chars, self._separator_val)
        if capitalize and result:
            result = result[0].upper() + result[1:]
        return result

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
            result = str(self._ensure_inner().slugify(text))

        return self._apply_post_processing(text, result, cap, safe)

    def __repr__(self) -> str:
        return f"Slugify(separator={self._separator_val!r}, to_lower={self._to_lower!r})"


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

        # Delegate common setup (param resolution, property init) to parent.
        super().__init__(**kwargs)

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
            _uids_set = uids if isinstance(uids, (set, frozenset)) else set(uids)

            def _check_not_in_uids(text: str) -> bool:
                return text not in _uids_set

            check = _check_not_in_uids

        self._unique_inner: _UniqueSlugifier = _UniqueSlugifier(check=check, **self._kwargs)

    def __call__(self, text: str, **kwargs: Any) -> str:
        result: str = str(self._unique_inner.slugify(text))
        return self._apply_post_processing(text, result, self._capitalize, self._safe_chars)

    def reset(self) -> None:
        """Clear the internal set of seen slugs."""
        self._unique_inner.reset()

    def __repr__(self) -> str:
        return "UniqueSlugify()"


def _find_next_safe_char(original: str, safe_set: frozenset[str], start: int) -> int:
    """Return the index of the next safe char in original from start, or -1."""
    for i in range(start, len(original)):
        if original[i] in safe_set:
            return i
    return -1


def _restore_safe_chars(original: str, slug: str, safe_chars: str, separator: str) -> str:
    """Best-effort restoration of safe_chars that were stripped during slugification.

    awesome-slugify preserves characters listed in safe_chars through the
    slugification pipeline. Since translit's Rust core doesn't have this concept,
    we approximate it by replacing separator sequences that correspond to safe
    char positions in the original text.

    Args:
        original: The original input text before slugification.
        slug: The slugified result.
        safe_chars: Characters to restore (e.g. ".-").
        separator: The slug separator (e.g. "-").

    This is an approximation — it handles the common cases (e.g. preserving dots
    in filenames, dashes in version strings) but may not match awesome-slugify
    exactly for all edge cases.
    """
    safe_set = frozenset(safe_chars)
    # Quick check: if no safe chars appear in original, nothing to restore
    if not safe_set.intersection(original):
        return slug
    # With an empty separator, there are no separator sequences to match
    # against safe chars — restoration is not possible.
    if not separator:
        return slug

    # Walk original and slug in parallel: when the slug has a separator
    # where the original had a safe char, restore the safe char.
    parts: list[str] = []
    sep_len = len(separator)
    original_pos = 0
    slug_pos = 0

    while slug_pos < len(slug):
        # Check if we're at a separator in the slug
        if slug[slug_pos : slug_pos + sep_len] == separator:
            safe_idx = _find_next_safe_char(original, safe_set, original_pos)
            if safe_idx >= 0:
                parts.append(original[safe_idx])
                original_pos = safe_idx + 1
            else:
                parts.append(separator)
            slug_pos += sep_len
        else:
            parts.append(slug[slug_pos])
            original_pos += 1
            slug_pos += 1

    return "".join(parts)


# ---------------------------------------------------------------------------
# Preconfigured instances (awesome-slugify compatibility)
# ---------------------------------------------------------------------------

slugify_url: Slugify = Slugify(to_lower=True, stop_words=("a", "an", "the"), max_length=200)
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
