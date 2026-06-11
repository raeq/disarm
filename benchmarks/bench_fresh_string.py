#!/usr/bin/env python3
"""Fresh-string vs cached-string per-call cost (#277 lever-5 decision gate).

CPython caches a str object's UTF-8 buffer after the first
``PyUnicode_AsUTF8AndSize`` call. Benchmarks that reuse one input object per
cell (bench_ratio.py, bench_unidecode_own.py) therefore hide the encode cost
that production fresh-string traffic pays on every call — exactly the cost
the proposed unsafe PEP 393 input path (#277 lever 5) would remove.

Design: time identical loops over a list of INNER references. **cached** mode
iterates INNER references to one object (UTF-8 cache warm after an untimed
warm-up call). **fresh** mode iterates INNER distinct, newly constructed
objects (cache always cold; construction happens outside the timed region).
Two controls separate the encode tax from plain memory-locality effects:
a pure-Python comparator (never calls AsUTF8) and translit on pure-ASCII
input (compact ASCII: the UTF-8 buffer IS the data — no encode). The
non-ASCII translit delta beyond the ASCII control estimates the encode tax.

Per measurement policy, ``--json`` emits dimensionless quantities only
(fresh/cached ratios and tax shares); absolute ns appear in the human table.

Usage::

    python benchmarks/bench_fresh_string.py          # human table (ns)
    python benchmarks/bench_fresh_string.py --json   # ratios + tax shares
"""

from __future__ import annotations

import json
import statistics
import sys
from collections.abc import Callable
from time import perf_counter

import translit

# ASCII control first (no encode possible), then the bench_ratio.py inputs.
INPUTS: dict[str, str] = {
    "ascii": "Plain ASCII control text of comparable length to the others. ",
    "latin": "Çà et là, l'élève zélé répète sa leçon; Übermäßige Größe, œuvre, año, coração. ",
    "cyrillic": "Москва — столица России. Быстрая транслитерация текста на латиницу. ",
    "greek": "Η Αθήνα είναι η πρωτεύουσα της Ελλάδας. Η γρήγορη μεταγραφή κειμένου. ",
    "mixed": "Pricing: café №7, naïve Москва, Ελλάδα — straße, 北京 pinyin. ",
}

REPS = 7
INNER = 2000


def _comparator() -> Callable[[str], str] | None:
    try:
        from unidecode import unidecode
    except ImportError:
        return None
    return unidecode


def _fresh_copy(text: str) -> str:
    # Partial slice of a concatenation: guaranteed-new object on CPython
    # (full-range slices, ``s + ""`` and ``"".join((s,))`` all return the
    # original object and would defeat the cold-cache requirement).
    return (text + " ")[:-1]


def _time_over(fn: Callable[[str], str], objs: list[str]) -> float:
    start = perf_counter()
    for o in objs:
        fn(o)
    return perf_counter() - start


def measure() -> dict[str, dict[str, dict[str, float]]]:
    """Median ns/call per (input, impl, mode), fresh interleaved with cached."""
    impls: dict[str, Callable[[str], str]] = {"translit": translit.transliterate}
    if (cmp_fn := _comparator()) is not None:
        impls["unidecode"] = cmp_fn

    out: dict[str, dict[str, dict[str, float]]] = {}
    for label, text in INPUTS.items():
        cached_objs = [text] * INNER
        per_impl: dict[str, dict[str, list[float]]] = {
            name: {"cached": [], "fresh": []} for name in impls
        }
        for fn in impls.values():
            fn(text)  # untimed warm-up: populates the shared object's UTF-8 cache
        for _ in range(REPS):
            for name, fn in impls.items():
                # Construction outside the timed region, rebuilt every rep so
                # every fresh object is first-touched inside the timed loop.
                fresh_objs = [_fresh_copy(text) for _ in range(INNER)]
                t_fresh = _time_over(fn, fresh_objs)
                t_cached = _time_over(fn, cached_objs)
                per_impl[name]["fresh"].append(t_fresh / INNER * 1e9)
                per_impl[name]["cached"].append(t_cached / INNER * 1e9)
        out[label] = {
            name: {
                "cached_ns": round(statistics.median(modes["cached"]), 1),
                "fresh_ns": round(statistics.median(modes["fresh"]), 1),
            }
            for name, modes in per_impl.items()
        }
    return out


def main(argv: list[str]) -> int:
    results = measure()
    if "unidecode" not in next(iter(results.values())):
        print("unidecode not installed -- locality control missing", file=sys.stderr)

    # Locality control: translit's fresh-vs-cached delta on pure ASCII input
    # (no encode possible). Non-ASCII deltas beyond this estimate the encode tax.
    ascii_delta = (
        results["ascii"]["translit"]["fresh_ns"] - results["ascii"]["translit"]["cached_ns"]
    )

    if "--json" in argv:
        payload: dict[str, object] = {"inner": INNER, "reps": REPS, "inputs": {}}
        for label, impls in results.items():
            entry: dict[str, object] = {}
            for name, m in impls.items():
                entry[name] = {"fresh_over_cached": round(m["fresh_ns"] / m["cached_ns"], 3)}
            if label != "ascii":
                tax = impls["translit"]["fresh_ns"] - impls["translit"]["cached_ns"] - ascii_delta
                entry["encode_tax_share_of_fresh"] = round(
                    max(tax, 0.0) / impls["translit"]["fresh_ns"], 3
                )
            payload["inputs"][label] = entry  # type: ignore[index]
        print(json.dumps(payload, sort_keys=True))
        return 0

    print(f"{'input':10s}{'impl':12s}{'cached':>10s}{'fresh':>10s}{'delta':>9s}{'delta%':>8s}")
    for label, impls in results.items():
        for name, m in impls.items():
            delta = m["fresh_ns"] - m["cached_ns"]
            pct = 100.0 * delta / m["fresh_ns"]
            print(
                f"{label:10s}{name:12s}{m['cached_ns']:>8.1f}ns{m['fresh_ns']:>8.1f}ns"
                f"{delta:>7.1f}ns{pct:>7.1f}%"
            )
    print(f"\nlocality control (translit ASCII fresh-cached delta): {ascii_delta:.1f} ns")
    for label, impls in results.items():
        if label == "ascii":
            continue
        tax = impls["translit"]["fresh_ns"] - impls["translit"]["cached_ns"] - ascii_delta
        share = 100.0 * max(tax, 0.0) / impls["translit"]["fresh_ns"]
        print(
            f"estimated encode tax {label:9s}: {max(tax, 0.0):6.1f} ns/call ({share:.1f}% of fresh per-call)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
