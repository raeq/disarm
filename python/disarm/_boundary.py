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
    """Scrub strings (and lists/tuples of them — e.g. stopwords, lexicons); pass
    everything else through unchanged. Identity on valid input."""
    if isinstance(value, str):
        return _wtf8(value)
    if isinstance(value, (list, tuple)):
        return type(value)(_scrub(item) for item in value)
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
