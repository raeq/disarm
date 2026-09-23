"""The `Text` stub declares the parameters `Text` takes (F9).

`tests/test_stub_signature_drift.py` holds `_core.pyi` against the compiled extension;
nothing held `_text.pyi` against `disarm.Text`, and two methods drifted. The stub for
`Text.normalize_confusables` had no `digit_policy`, so a type-checked caller could not
pass it (found by the Lean model of the confusable fold, `formal/lean/Confusables`), and
`Text.ml_normalize` had no `fold_case`. Names and kinds are compared, as that file does;
annotations and default values are not.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import disarm

STUB = Path(disarm.__file__).parent / "_text.pyi"


def _stub_methods() -> dict[str, list[tuple[str, str]]]:
    tree = ast.parse(STUB.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Text")
    out = {}
    for fn in cls.body:
        if not isinstance(fn, ast.FunctionDef) or fn.name.startswith("__"):
            continue
        if any(isinstance(d, ast.Name) and d.id == "property" for d in fn.decorator_list):
            continue
        args = fn.args
        out[fn.name] = [(a.arg, "positional") for a in args.args[1:]] + [
            (a.arg, "keyword") for a in args.kwonlyargs
        ]
    return out


STUB_METHODS = _stub_methods()


def test_the_stub_declares_the_class_it_describes() -> None:
    assert len(STUB_METHODS) > 30, sorted(STUB_METHODS)


@pytest.mark.parametrize("name", sorted(STUB_METHODS))
def test_the_stub_matches_the_implementation(name: str) -> None:
    impl = getattr(disarm.Text, name, None)
    assert impl is not None, f"_text.pyi declares Text.{name}, which Text does not have"
    params = list(inspect.signature(impl).parameters.values())[1:]
    actual = [
        (p.name, "keyword" if p.kind is p.KEYWORD_ONLY else "positional")
        for p in params
        if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
    ]
    assert STUB_METHODS[name] == actual, f"Text.{name}: stub {STUB_METHODS[name]}, impl {actual}"
