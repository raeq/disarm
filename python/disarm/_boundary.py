"""#469: enforce the malformed-Unicode contract at the ``str`` -> Rust boundary.

A Python ``str`` may carry unpaired surrogates (and surrogate pairs presented as
two code points). They have no UTF-8 encoding, so the PyO3 ``str`` -> ``&str``
conversion raises ``UnicodeEncodeError`` before any disarm logic runs. Rust can
never receive this input, so the contract is enforced here, one level above the
extension: every ``_core`` callable is re-exported wrapped so that, on the boundary
failure, the offending string arguments are converted **WTF-8 -> UTF-8** and the
call retried.

The conversion (``str.encode('utf-16-le', 'surrogatepass').decode(..., 'replace')``)
recombines a well-formed high+low pair into its astral scalar — matching a
UTF-16-native binding such as Node — and replaces each genuinely lone surrogate
code unit with exactly one ``U+FFFD`` (the Unicode replacement character). The
substituted ``U+FFFD`` is terminal: this neutralizes the input, it does not recover
the original bytes.

The wrap is lazy: valid input (the overwhelming common case) takes the success path
and pays nothing beyond an un-raised ``try``; only a call that actually fails at the
boundary is scrubbed and retried. Wrapping every ``_core`` callable here — rather
than at each call site — keeps the contract uniform across all entrypoints (and the
``Text`` builder, which delegates to the public functions), so a new entrypoint is
covered for free.
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


def _surrogate_safe(fn: _F) -> _F:
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except UnicodeEncodeError:
            return fn(
                *(_scrub(a) for a in args),
                **{k: _scrub(v) for k, v in kwargs.items()},
            )

    return wrapper  # type: ignore[return-value]


# Re-export every `_core` member: functions wrapped with the boundary guard,
# everything else (exception classes, the Transliterator type, constants) verbatim.
# Classes are excluded from wrapping so `except DisarmError` and constructors keep
# working.
for _name in dir(_core):
    if _name.startswith("__"):
        continue
    _obj = getattr(_core, _name)
    globals()[_name] = (
        _surrogate_safe(_obj) if callable(_obj) and not isinstance(_obj, type) else _obj
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
