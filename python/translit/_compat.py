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

    @staticmethod
    def _capitalize_first(result: str, capitalize: bool) -> str:
        """Capitalize the first character, awesome-slugify style."""
        if capitalize and result:
            return result[0].upper() + result[1:]
        return result

    def __call__(self, text: str, **kwargs: Any) -> str:
        if kwargs:
            merged = {**self._kwargs}
            override = _resolve_awesome_params(kwargs)
            cap: bool = bool(override.pop("_capitalize", self._capitalize))
            safe: str = str(override.pop("_safe_chars", self._safe_chars))
            merged.update(override)
            kw = merged
        else:
            cap = self._capitalize
            safe = self._safe_chars
            kw = self._kwargs

        result: str
        if safe:
            # Preserve safe_chars at their true positions: protect them through
            # slugification, then restore (awesome-slugify treats safe_chars as
            # word characters, not separators). Slugify without max_length so the
            # bound applies to the restored result, not the longer marker form.
            separator = str(kw.get("separator", "-"))
            max_length = int(kw.get("max_length", 0))
            slugifier = _Slugifier(**{**kw, "max_length": 0})
            result = _slugify_with_safe_chars(
                slugifier.slugify, text, safe, separator, truncate_to=max_length
            )
        elif kwargs:
            result = str(_Slugifier(**kw).slugify(text))
        else:
            result = str(self._ensure_inner().slugify(text))

        return self._capitalize_first(result, cap)

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

        # When safe_chars is set, the safe-char path protects them with
        # placeholders before slugifying; `max_length` must NOT be applied by the
        # inner slugifier (it could truncate a placeholder mid-marker). Build the
        # inner without it and let the safe-char helper bound the restored result
        # via `truncate_to`. safe_chars is fixed per instance for UniqueSlugify
        # (per-call kwargs are not honored), so the non-safe path is unused here.
        inner_kwargs = dict(self._kwargs)
        if self._safe_chars:
            inner_kwargs["max_length"] = 0
        self._unique_inner: _UniqueSlugifier = _UniqueSlugifier(check=check, **inner_kwargs)

    def __call__(self, text: str, **kwargs: Any) -> str:
        if self._safe_chars:
            separator = str(self._kwargs.get("separator", "-"))
            result: str = _slugify_with_safe_chars(
                self._unique_inner.slugify,
                text,
                self._safe_chars,
                separator,
                truncate_to=self._max_length_val,
            )
        else:
            result = str(self._unique_inner.slugify(text))
        return self._capitalize_first(result, self._capitalize)

    def reset(self) -> None:
        """Clear the internal set of seen slugs."""
        self._unique_inner.reset()

    def __repr__(self) -> str:
        return "UniqueSlugify()"


def _safe_marker(index: int, text: str) -> str:
    """A collision-free, slug-stable placeholder for a safe character.

    Markers are lowercase ASCII (case-fold invariant) and contain only word
    characters, so they survive slugification unchanged and unsplit. A leading
    ``z`` is prepended until the marker does not occur in ``text``.
    """
    suffix = chr(ord("a") + index) if index < 26 else f"x{index}x"
    marker = f"zqx{suffix}qzx"
    while marker in text:
        marker = "z" + marker
    return marker


def _slugify_with_safe_chars(
    slugify_fn: Callable[[str], str],
    text: str,
    safe_chars: str,
    separator: str,
    truncate_to: int = 0,
) -> str:
    """Slugify while preserving ``safe_chars`` at their original positions.

    awesome-slugify treats ``safe_chars`` as word characters: they pass through
    the pipeline and belong to the adjacent token rather than acting as
    separators. translit's Rust core has no such concept, so we protect each
    safe character with a word-character placeholder, slugify, then restore.

    ``slugify_fn`` must NOT apply ``max_length`` itself (the placeholders are
    longer than the characters they stand in for); pass ``truncate_to`` to bound
    the final, restored result instead.
    """
    present = [c for c in dict.fromkeys(safe_chars) if c in text]
    if not present:
        result = slugify_fn(text)
    else:
        mapping: dict[str, str] = {}
        protected = text
        for i, char in enumerate(present):
            marker = _safe_marker(i, text)
            mapping[marker] = char
            protected = protected.replace(char, marker)
        result = slugify_fn(protected)
        for marker, char in mapping.items():
            result = result.replace(marker, char)
    if truncate_to and len(result) > truncate_to:
        result = result[:truncate_to].rstrip(separator)
    return result


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
