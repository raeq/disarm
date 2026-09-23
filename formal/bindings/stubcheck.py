"""Compare the type stub `python/disarm/_core.pyi` with the extension's runtime signatures.

    $DISARM_PYTHON formal/bindings/stubcheck.py

For every function the stub declares, the parameter names, kinds and default values
must match what PyO3 reports (`__text_signature__`). A stub default that differs from
the runtime one is a documented default the caller does not get.
"""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

import disarm._core as core

STUB = Path(__file__).resolve().parents[2] / "python" / "disarm" / "_core.pyi"


def stub_sigs() -> dict[str, list[tuple[str, str, str | None]]]:
    tree = ast.parse(STUB.read_text())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            a = node.args
            params = []
            pos = a.posonlyargs + a.args
            defaults = [None] * (len(pos) - len(a.defaults)) + [ast.unparse(d) for d in a.defaults]
            for p, d in zip(pos, defaults, strict=True):
                params.append((p.arg, "pos", d))
            if a.vararg:
                params.append((a.vararg.arg, "var", None))
            for p, d in zip(a.kwonlyargs, a.kw_defaults, strict=True):
                params.append((p.arg, "kw", ast.unparse(d) if d is not None else None))
            out[node.name] = params
    return out


def runtime_sig(fn) -> list[tuple[str, str, str | None]] | None:
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return None
    res = []
    for p in sig.parameters.values():
        kind = {inspect.Parameter.KEYWORD_ONLY: "kw", inspect.Parameter.VAR_POSITIONAL: "var"}.get(
            p.kind, "pos"
        )
        d = None if p.default is inspect.Parameter.empty else repr(p.default)
        res.append((p.name, kind, d))
    return res


def norm(d: str | None) -> str | None:
    if d is None:
        return None
    try:
        return repr(ast.literal_eval(d))
    except (ValueError, SyntaxError):
        return d


def main() -> int:
    bad = 0
    checked = 0
    for name, sp in sorted(stub_sigs().items()):
        fn = getattr(core, name, None)
        if fn is None:
            print(f"{name}: in the stub, missing at runtime")
            bad += 1
            continue
        rt = runtime_sig(fn)
        if rt is None:
            continue
        checked += 1
        s = [(n, k, norm(d)) for n, k, d in sp]
        r = [(n, k, norm(d)) for n, k, d in rt]
        # `...` on either side means "has a default, value not stated": it matches any
        # default but not the absence of one.
        same = len(s) == len(r) and all(
            sn == rn
            and sk == rk
            and (sd == rd or (sd is not None and rd is not None and "Ellipsis" in (sd, rd)))
            for (sn, sk, sd), (rn, rk, rd) in zip(s, r, strict=True)
        )
        if not same:
            bad += 1
            print(f"{name}:\n  stub    {s}\n  runtime {r}")
    print(f"{checked} functions compared, {bad} differ")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
