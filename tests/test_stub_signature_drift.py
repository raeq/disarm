"""Drift detection between the Rust PyO3 extension and its hand-written stub.

The compiled extension ``disarm._disarm`` and the hand-written type stub
``python/disarm/_disarm.pyi`` can silently diverge: a Rust signature change
(param added/removed/renamed/reordered, default added/removed, or a
positional-vs-keyword change) is invisible to ``mypy`` because mypy compares
source against the *stub*, never against the *binary*.

This test closes that gap. It:

1. Parses the ``.pyi`` stub with :mod:`ast` (the stub has multi-line ``def``s,
   so we walk the AST rather than regex) and extracts, for every top-level
   ``def`` and for the ``__init__`` of the builder classes, each parameter's
   name, kind, and whether it carries a default. Type annotations and the
   concrete default *value* are deliberately ignored.
2. Introspects the built extension via :func:`inspect.signature` (PyO3 emits
   ``__text_signature__``), extracting the same name/kind/has-default tuples.
3. Asserts the two agree, with a message that names the offending symbol and
   the precise difference.

The binary is the source of truth; a failure here means the stub must be
updated to match the Rust ``#[pyo3(signature = ...)]`` declaration.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import disarm._disarm as ext

# --------------------------------------------------------------------------- #
# Parameter model
# --------------------------------------------------------------------------- #

# Canonical kind names, decoupled from both ast and inspect representations.
POSITIONAL_ONLY = "positional-only"
POSITIONAL_OR_KEYWORD = "positional-or-keyword"
KEYWORD_ONLY = "keyword-only"
VAR_POSITIONAL = "var-positional"
VAR_KEYWORD = "var-keyword"

# Builder classes whose constructor signature we compare via __init__.
BUILDER_CLASSES = ("_Slugifier", "_UniqueSlugifier", "_TextPipeline")

# Opaque/builtin types with no introspectable constructor signature.
# These have no __text_signature__ and inspect.signature() raises on them,
# so there is nothing to compare against the stub.
SKIP = frozenset(
    {
        # Opaque types with no introspectable constructor signature to compare.
        "DisarmError",
        "InvalidArgumentError",  # #183 exception subclasses
        "ResourceLimitError",
        "UnsupportedError",
        "HostnameAnalysis",
    }
)

# Minimum number of symbols the test must check; guards against the comparison
# silently passing because it inspected nothing (e.g. an import or parse change
# that empties one side).
MIN_COVERED = 40

STUB_PATH = Path(__file__).resolve().parents[1] / "python" / "disarm" / "_disarm.pyi"


def _params_from_inspect(sig: inspect.Signature) -> list[tuple[str, str, bool]]:
    """Reduce an ``inspect.Signature`` to ``(name, kind, has_default)`` tuples."""
    kind_map = {
        inspect.Parameter.POSITIONAL_ONLY: POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD: POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY: KEYWORD_ONLY,
        inspect.Parameter.VAR_POSITIONAL: VAR_POSITIONAL,
        inspect.Parameter.VAR_KEYWORD: VAR_KEYWORD,
    }
    out: list[tuple[str, str, bool]] = []
    for p in sig.parameters.values():
        # self is implicitly bound for the builder constructors and never
        # appears in inspect.signature(cls); nothing to strip here.
        has_default = p.default is not inspect.Parameter.empty
        out.append((p.name, kind_map[p.kind], has_default))
    return out


def _params_from_ast(args: ast.arguments) -> list[tuple[str, str, bool]]:
    """Reduce an ``ast.arguments`` node to ``(name, kind, has_default)`` tuples.

    ``self`` (the leading positional arg on class ``__init__``) is dropped so
    the result lines up with ``inspect.signature(cls)``.
    """
    out: list[tuple[str, str, bool]] = []

    # Positional-only args (before a `/`). Defaults are shared across the
    # posonly + regular positional list, right-aligned.
    posonly = list(args.posonlyargs)
    positional = list(args.args)
    pos_all = posonly + positional
    pos_defaults = list(args.defaults)
    # Right-align defaults onto the combined positional list.
    n_with_default = len(pos_defaults)
    first_default_idx = len(pos_all) - n_with_default

    for i, a in enumerate(posonly):
        out.append((a.arg, POSITIONAL_ONLY, i >= first_default_idx))
    for j, a in enumerate(positional):
        idx = len(posonly) + j
        out.append((a.arg, POSITIONAL_OR_KEYWORD, idx >= first_default_idx))

    # *args
    if args.vararg is not None:
        out.append((args.vararg.arg, VAR_POSITIONAL, False))

    # Keyword-only args. kw_defaults is positionally aligned with kwonlyargs;
    # an entry of None means "no default".
    for a, d in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        out.append((a.arg, KEYWORD_ONLY, d is not None))

    # **kwargs
    if args.kwarg is not None:
        out.append((args.kwarg.arg, VAR_KEYWORD, False))

    # Drop a leading `self` if present (class __init__ methods).
    if out and out[0][0] == "self":
        out = out[1:]
    return out


def _parse_stub(path: Path) -> dict[str, list[tuple[str, str, bool]]]:
    """Map symbol name -> stub-declared params.

    Top-level ``def``s map under their own name. Builder classes map under the
    class name, using the params of their ``__init__``.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: dict[str, list[tuple[str, str, bool]]] = {}

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            result[node.name] = _params_from_ast(node.args)
        elif isinstance(node, ast.ClassDef) and node.name in BUILDER_CLASSES:
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name == "__init__":
                    result[node.name] = _params_from_ast(sub.args)
                    break
    return result


# Parse the stub once at collection time so we can parametrize per symbol.
_STUB_PARAMS = _parse_stub(STUB_PATH)


def _ext_targets() -> list[str]:
    """Names exported by the extension that we should compare.

    Only callables (functions/classes) have signatures to drift; module-level
    constants exposed by the extension — e.g. ``_MAX_BATCH_SIZE`` (#200) — have
    no ``inspect.signature`` and are skipped.
    """
    return [
        n
        for n in dir(ext)
        if not n.startswith("__") and n not in SKIP and callable(getattr(ext, n))
    ]


_EXT_NAMES = _ext_targets()


def test_stub_covers_a_meaningful_number_of_symbols() -> None:
    """Vacuity guard: the comparison must exercise a real number of symbols."""
    comparable = [n for n in _EXT_NAMES if n in _STUB_PARAMS]
    assert len(comparable) >= MIN_COVERED, (
        f"only {len(comparable)} extension symbols matched a stub entry "
        f"(expected >= {MIN_COVERED}); the drift check may be vacuous. "
        f"extension symbols: {sorted(_EXT_NAMES)}"
    )


@pytest.mark.parametrize("name", sorted(_EXT_NAMES))
def test_stub_matches_binary_signature(name: str) -> None:
    """Each extension symbol's signature must match its stub declaration."""
    obj = getattr(ext, name)

    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        pytest.fail(
            f"{name!r} is exported by disarm._disarm but has no "
            f"introspectable signature ({exc!r}). If it is a genuinely opaque "
            f"builtin type, add it to SKIP; otherwise the binary is broken."
        )

    assert name in _STUB_PARAMS, (
        f"{name!r} is exported by disarm._disarm but has no corresponding "
        f"top-level def (or builder __init__) in {STUB_PATH.name}. "
        f"Add a stub entry for it."
    )

    binary = _params_from_inspect(sig)
    stub = _STUB_PARAMS[name]

    # Compare parameter-by-parameter for a precise failure message.
    if binary != stub:
        diffs = _describe_diffs(name, stub, binary)
        raise AssertionError(
            f"signature drift for {name!r} between stub and binary:\n"
            + "\n".join(diffs)
            + f"\n  stub:   {stub}\n  binary: {binary}"
        )


def _describe_diffs(
    name: str,
    stub: list[tuple[str, str, bool]],
    binary: list[tuple[str, str, bool]],
) -> list[str]:
    """Produce human-readable per-parameter difference lines."""
    diffs: list[str] = []
    stub_by_name = {p[0]: p for p in stub}
    binary_by_name = {p[0]: p for p in binary}

    for pname in stub_by_name.keys() - binary_by_name.keys():
        diffs.append(f"  - param {pname!r} is in stub but not in binary")
    for pname in binary_by_name.keys() - stub_by_name.keys():
        diffs.append(f"  - param {pname!r} is in binary but not in stub")

    for pname in stub_by_name.keys() & binary_by_name.keys():
        s = stub_by_name[pname]
        b = binary_by_name[pname]
        if s[1] != b[1]:
            diffs.append(f"  - param {pname!r} kind: stub={s[1]} binary={b[1]}")
        if s[2] != b[2]:
            diffs.append(f"  - param {pname!r} has_default: stub={s[2]} binary={b[2]}")

    # Ordering differences (same names/attrs but different order).
    if not diffs and [p[0] for p in stub] != [p[0] for p in binary]:
        diffs.append(
            f"  - parameter order differs: stub={[p[0] for p in stub]} "
            f"binary={[p[0] for p in binary]}"
        )
    return diffs
