"""Shared helpers for the `_api_*` modules: resource limits, batch validation, and
the coercion of the `NF` and `Script` enums to the strings the core expects."""

from __future__ import annotations

from disarm._boundary import (
    _MAX_BATCH_SIZE,
    InvalidArgumentError,
    ResourceLimitError,
)
from disarm._enums import Script
from disarm._types import (
    NF,
    NormalizationForm,
)

# --- Resource limits ---
# _MAX_BATCH_SIZE is imported from the Rust extension above (single source of
# truth, #200). _MAX_GRAPHEME_SPLIT_INPUT has no Rust counterpart — the
# grapheme_split() size guard is enforced only on the Python side — so it is
# defined here (in characters/codepoints, see grapheme_split()).
_MAX_GRAPHEME_SPLIT_INPUT: int = 10 * 1024 * 1024  # ~10.5M characters (codepoints)

# The `errors=` / `form=` enum values are validated once, in the Rust core (#185),
# which raises InvalidArgumentError with the canonical message. The Python wrapper
# no longer keeps a hand-synced copy of those sets — that drift hazard scaled per
# binding. Only *combinations* of otherwise-valid kwargs are checked here (#69).


# Upper bound of the Rust `i64` that `max_length`/`max_graphemes` cross into.
# A larger value can't reach the core — PyO3 raises a bare `OverflowError` at
# extraction, outside the DisarmError hierarchy — so reject it here as
# InvalidArgumentError, consistently with the core's negative-value check (#255).
# This is the one bound the core provably cannot enforce (the value never arrives).
_MAX_I64: int = 2**63 - 1


def _checked_i64_max(value: int, name: str) -> int:
    """Reject a max-bound too large for the Rust i64 boundary (#255)."""
    if value > _MAX_I64:
        raise InvalidArgumentError(f"{name} too large: {value} exceeds the maximum {_MAX_I64}")
    return value


def _validate_batch(texts: object, func_name: str) -> None:
    """Validate that texts is a list[str] within batch size limits."""
    if not isinstance(texts, list):
        raise TypeError(f"{func_name}() expects list[str], got {type(texts).__name__}")
    if len(texts) > _MAX_BATCH_SIZE:
        raise ResourceLimitError(
            f"batch too large ({len(texts)} items); maximum is {_MAX_BATCH_SIZE} items"
        )
    for i, t in enumerate(texts):
        if not isinstance(t, str):
            raise TypeError(f"{func_name}() element {i} must be str, got {type(t).__name__}")


def _norm_form(form: NormalizationForm | NF) -> NormalizationForm:
    """The string the core expects, from either an `NF` member or a bare form string.

    `NF`, `Script` and `Component` are plain `enum.Enum`, not `str` subclasses, so PyO3
    rejects a member outright (#767). The coercion existed as a one-liner twice — in
    `percent_encode` and `script_info` — and nothing generalised it, which is exactly why
    those two were the only two surfaces that accepted their own enum.

    A bare string is returned untouched, so it still reaches the core and is still
    validated there. Subclassing `str` was rejected as the fix: it would make
    `Script.LATIN == "Latin"` true and silently change the meaning of every equality and
    `in` test a caller has already written against these members.
    """
    return form.value if isinstance(form, NF) else form


def _target_script(value: str | Script) -> str:
    """`Script` has two spellings in this API and they are not interchangeable (#767).

    `script_info` takes the enum's own value — `"Latin"` — and rejects `"latin"`. The
    confusable surfaces take `"latin"` and reject `"Latin"`. So the one-liner that fixes
    `form=` is not enough here: it yields `"Latin"`, which is still wrong at six surfaces.

    Only a member is lowered. A bare string passes through unchanged, so `"Latin"` keeps
    failing exactly as it does today rather than being quietly repaired.
    """
    return value.value.lower() if isinstance(value, Script) else value
