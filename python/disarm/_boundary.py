"""#469: enforce the malformed-Unicode contract at the ``str`` -> Rust boundary.

A Python ``str`` may carry unpaired surrogates (and surrogate pairs presented as
two code points). They have no UTF-8 encoding, so the PyO3 ``str`` -> ``&str``
conversion raises ``UnicodeEncodeError`` before any disarm logic runs. Rust can
never receive this input, so the contract is enforced here, one level above the
extension: every ``_core`` callable is re-exported wrapped so that, on the boundary
failure, the offending string arguments are converted **WTF-8 -> UTF-8** and the
call retried. The exceptions are the entry points in ``_SELF_GUARDED``, which convert
their own string arguments natively and are re-exported unwrapped.

The conversion (``str.encode('utf-16-le', 'surrogatepass').decode(..., 'replace')``)
recombines a well-formed high+low pair into its astral scalar — matching a
UTF-16-native binding such as Node — and replaces each genuinely lone surrogate
code unit with exactly one ``U+FFFD`` (the Unicode replacement character). The
substituted ``U+FFFD`` is terminal: this neutralizes the input, it does not recover
the original bytes.

The wrap is lazy: valid input (the overwhelming common case) takes the success path,
which never leaves native code (``_core.SurrogateSafe``); only a call that actually
fails at the boundary is scrubbed and retried, in Python. Wrapping by default here,
rather than at each call site, keeps the contract uniform across all entrypoints (and
the ``Text`` builder, which delegates to the public functions), so a new entrypoint
is covered for free; an entry point opts out only by guarding itself, and
``test_the_guard_never_enters_python_on_valid_input`` holds the list.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, TypeVar

from disarm import _core

_F = TypeVar("_F", bound=Callable[..., Any])


def _wtf8(s: str) -> str:
    """WTF-8 -> UTF-8: recombine surrogate pairs, one U+FFFD per lone surrogate."""
    return s.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")


def _scrub(value: Any) -> Any:
    """Scrub strings and any container of them — lists/tuples (stopwords), sets/
    frozensets (lexicon / anomaly word sets, e.g. `has_anomalies`), and dicts
    (`register_lang` / `register_replacements` tables, keys and values). Everything
    else passes through unchanged; identity on valid input."""
    if isinstance(value, str):
        return _wtf8(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        return type(value)(_scrub(item) for item in value)
    if isinstance(value, dict):
        return {_scrub(k): _scrub(v) for k, v in value.items()}
    return value


def _snapshot(value: Any) -> Any:
    """Materialize a one-shot iterable (a generator/iterator — e.g. a `Lexicon` word
    stream) to a list, so a scrub-and-retry scrubs the same items the first attempt
    consumed rather than an exhausted iterator (#476 review). Strings and stable
    collections (list / tuple / set / frozenset / dict) pass through unchanged."""
    if hasattr(value, "__iter__") and not isinstance(
        value, (str, bytes, list, tuple, set, frozenset, dict)
    ):
        return list(value)
    return value


def _retry(fn: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any] | None) -> Any:
    """The failure path: scrub every string argument and call ``fn`` again."""
    return fn(
        *(_scrub(a) for a in args),
        **{k: _scrub(v) for k, v in (kwargs or {}).items()},
    )


def _surrogate_safe(fn: _F) -> _F:
    """``fn`` guarded by the scrub-and-retry above.

    The guard is native (``_core.SurrogateSafe``): it forwards the call and enters
    Python only when the call raised ``UnicodeEncodeError``. A Python wrapper function
    cost 70-84 ns on every call, valid input included, which was two to four times the
    native cost of a short call. ``update_wrapper`` gives it the wrapped function's
    name, docstring and ``__wrapped__``, which ``help()`` and ``inspect.signature`` read.
    """
    guarded = _core.SurrogateSafe(fn, _retry)
    functools.update_wrapper(guarded, fn)
    return guarded  # type: ignore[return-value]


# Entry points that keep the contract themselves and are re-exported unwrapped.
# `_transliterate_entry` is the public `transliterate` (#277): its string arguments are
# scrubbed natively (`src/py/boundary.rs`, `Utf8Arg`), because even the native guard's
# extra call layer cost as much as a short call and lost Unidecode's ASCII benchmark cell.
_SELF_GUARDED = frozenset({"_transliterate_entry"})

# Re-export every `_core` member: functions wrapped with the boundary guard,
# everything else (exception classes, the Transliterator type, constants) verbatim.
# Classes are excluded from wrapping so `except DisarmError` and constructors keep
# working.
for _name in dir(_core):
    if _name.startswith("__"):
        continue
    _obj = getattr(_core, _name)
    globals()[_name] = (
        _surrogate_safe(_obj)
        if callable(_obj) and not isinstance(_obj, type) and _name not in _SELF_GUARDED
        else _obj
    )

del _name, _obj


# #476: `Lexicon([...])` crosses the str -> Rust boundary on *construction*, which the
# module-level loop above (functions only) does not cover. `_core.Lexicon` is
# `#[pyclass(frozen)]` and not subclassable, so wrap it with a metaclass proxy: the
# proxy's `__call__` applies the same scrub-and-retry contract to construction, while
# `__instancecheck__`/`__subclasscheck__` delegate to the real type so that
# `isinstance(x, Lexicon)` — used by `has_anomalies` / `inspect_anomalies` to dispatch a
# prebuilt handle vs an iterable — stays True for every real handle.
class _LexiconMeta(type):
    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        # Snapshot one-shot iterables up front: `Lexicon(words)` accepts any
        # `Iterable[str]`, and a generator would be exhausted by the first attempt,
        # leaving the retry to scrub an empty stream (#476 review).
        args = tuple(_snapshot(a) for a in args)
        kwargs = {k: _snapshot(v) for k, v in kwargs.items()}
        try:
            return _core.Lexicon(*args, **kwargs)
        except UnicodeEncodeError:
            return _core.Lexicon(
                *(_scrub(a) for a in args),
                **{k: _scrub(v) for k, v in kwargs.items()},
            )

    def __instancecheck__(cls, instance: Any) -> bool:
        return isinstance(instance, _core.Lexicon)

    def __subclasscheck__(cls, subclass: type) -> bool:
        return issubclass(subclass, _core.Lexicon)


class Lexicon(metaclass=_LexiconMeta):
    """Boundary-guarded handle for the Rust ``Lexicon`` (#469/#476): construction scrubs
    WTF-8 -> UTF-8 on the boundary failure instead of raising, and ``isinstance`` against
    it recognizes every real ``_core.Lexicon`` instance. Construct via ``Lexicon([...])``."""
