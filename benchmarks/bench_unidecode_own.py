#!/usr/bin/env python3
"""Unidecode's own benchmark, head-to-head (#281) — interleaved, median-of-reps.

Clean-room replication of the four timeit cells published in Unidecode's
``benchmark.py`` (avian2/unidecode). The GPL-2.0 file itself is NOT copied or
ported; only the published *methodology* is replicated — per-call timing of
``unidecode_expect_ascii`` / ``unidecode_expect_nonascii`` on a 12-char ASCII
string and a 12-char non-ASCII string. translit runs the identical inputs
through ``translit.transliterate``, interleaved per rep so runner noise
cancels in the ratio (same model as bench_ratio.py, V14).

A cell is "won" when the median ratio (comparator seconds / translit seconds)
is > 1.0. The headline claim "beats Unidecode on its own benchmark" requires
winning all four cells (#281). Until #277 levers 1 and 4 land, the
``expect_ascii/ascii`` cell is expected to report LOSS — that is signal, not
failure (this benchmark is flag-only and never blocks a PR).

Per measurement policy, ``--json`` emits ratios and the sweep verdict only;
absolute ns/call appear in the human table for context and are never stored.

Usage::

    python benchmarks/bench_unidecode_own.py          # human table
    python benchmarks/bench_unidecode_own.py --json   # {"cells": {...}, "swept": bool}
"""

from __future__ import annotations

import json
import statistics
import sys
from collections.abc import Callable
from time import perf_counter

import translit

# The two inputs published in Unidecode's benchmark.py (12 chars each).
INPUTS: dict[str, str] = {
    "ascii": "Hello, World",
    "non_ascii": "¡Hola mundo!",
}

REPS = 7
INNER = 20000


def _comparators() -> dict[str, Callable[[str], str]]:
    """The two function variants Unidecode's own benchmark exercises."""
    try:
        from unidecode import unidecode_expect_ascii, unidecode_expect_nonascii
    except ImportError:
        return {}
    return {
        "expect_ascii": unidecode_expect_ascii,
        "expect_nonascii": unidecode_expect_nonascii,
    }


# Regime marker (see bench_ratio.py): fresh str object per timed call —
# production-true; cached-object re-calls hide the AsUTF8 encode cost.
REGIME = "fresh-string/v2"


def _fresh_copies(text: str) -> list[str]:
    """INNER distinct new str objects, built outside the timed region."""
    return [(text + " ")[:-1] for _ in range(INNER)]


def _time(fn: Callable[[str], str], objs: list[str]) -> float:
    """Seconds for one call of fn over each of the INNER fresh objects."""
    start = perf_counter()
    for o in objs:
        fn(o)
    return perf_counter() - start


def measure() -> dict[str, dict[str, float | bool]]:
    """Median comparator/translit ratio per cell, interleaved per rep."""
    translit_fn: Callable[[str], str] = translit.transliterate
    cells: dict[str, dict[str, float | bool]] = {}
    for variant, cmp_fn in _comparators().items():
        for label, text in INPUTS.items():
            ratios: list[float] = []
            translit_ns: list[float] = []
            cmp_ns: list[float] = []
            for _ in range(REPS):
                t = _time(translit_fn, _fresh_copies(text))
                c = _time(cmp_fn, _fresh_copies(text))
                ratios.append(c / t)
                translit_ns.append(t / INNER * 1e9)
                cmp_ns.append(c / INNER * 1e9)
            ratio = round(statistics.median(ratios), 3)
            cells[f"{variant}/{label}"] = {
                "ratio": ratio,
                "won": ratio > 1.0,
                # context only — printed in the human table, stripped from --json
                "translit_ns": round(statistics.median(translit_ns), 1),
                "unidecode_ns": round(statistics.median(cmp_ns), 1),
            }
    return cells


def main(argv: list[str]) -> int:
    cells = measure()
    if not cells:
        print("unidecode not installed -- skipping", file=sys.stderr)
        return 0
    swept = all(c["won"] for c in cells.values())
    if "--json" in argv:
        slim = {name: {"ratio": c["ratio"], "won": c["won"]} for name, c in cells.items()}
        print(
            json.dumps(
                {"regime": REGIME, "inner": INNER, "reps": REPS, "cells": slim, "swept": swept},
                sort_keys=True,
            )
        )
        return 0
    print(f"{'cell':28s}{'translit':>12s}{'unidecode':>12s}{'ratio':>9s}  result")
    for name, c in cells.items():
        verdict = "WIN" if c["won"] else "LOSS"
        print(
            f"{name:28s}{c['translit_ns']:>10.1f}ns{c['unidecode_ns']:>10.1f}ns"
            f"{c['ratio']:>8.2f}x  {verdict}"
        )
    print(f"\nfour-cell sweep: {'YES' if swept else 'NO'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
