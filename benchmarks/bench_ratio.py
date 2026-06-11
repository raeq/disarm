#!/usr/bin/env python3
"""Transliterate-axis comparator ratio (#234 gate V14) — interleaved, median-of-reps.

The cross-run-valid signal is a **ratio** of disarm to a pinned comparator,
measured **interleaved in one session** so both share the same instantaneous
runner noise (which then cancels to first order). We take the **median** over
several reps to shed outliers, and the result is only meaningful **bucketed by
the fingerprint** (microarch + CPython); pair this with `perf_fingerprint.py`.

Transliterate axis only: `unidecode`, `text-unidecode`, `anyascii`. `ftfy` is a
normalizer, not a transliterator, and must never appear here (gate V16).

Usage::

    python benchmarks/bench_ratio.py            # human table
    python benchmarks/bench_ratio.py --json      # {"ratios": {...}} for the record
"""

from __future__ import annotations

import json
import statistics
import sys
from collections.abc import Callable
from time import perf_counter

import disarm

# Comparators on the transliterate axis (NOT ftfy — V16). Imported lazily so a
# missing optional comparator (e.g. uroman absent on <3.10) degrades to a skip.
_COMPARATORS: dict[str, str] = {
    "unidecode": "from unidecode import unidecode as f",
    "text-unidecode": "from text_unidecode import unidecode as f",
    "anyascii": "from anyascii import anyascii as f",
}

# Compact, deterministic, script-representative inputs (one paragraph each).
INPUTS: dict[str, str] = {
    "latin": "Çà et là, l'élève zélé répète sa leçon; Übermäßige Größe, œuvre, año, coração. ",
    "cyrillic": "Москва — столица России. Быстрая транслитерация текста на латиницу. ",
    "greek": "Η Αθήνα είναι η πρωτεύουσα της Ελλάδας. Η γρήγορη μεταγραφή κειμένου. ",
    "mixed": "Pricing: café №7, naïve Москва, Ελλάδα — straße, 北京 pinyin. ",
}

REPS = 7
INNER = 2000


def _load(comparator_src: str) -> Callable[[str], str] | None:
    ns: dict[str, object] = {}
    try:
        exec(comparator_src, ns)  # noqa: S102 (fixed, trusted import strings)
    except ImportError:
        return None
    fn = ns.get("f")
    return fn if callable(fn) else None


# Measurement regime marker, recorded in every JSON output so perf-results
# history never silently mixes epochs. "fresh-string/v2" (#277): every timed
# call receives a NEW str object, because production workloads are always new
# string objects — re-calling on one cached object lets CPython's per-object
# AsUTF8 cache hide ~105-137 ns/call of UTF-8 encode cost that only translit
# pays (pure-Python comparators never call AsUTF8), flattering translit.
# Records before this marker were the cached-object v1 regime.
REGIME = "fresh-string/v2"


def _fresh_copies(text: str) -> list[str]:
    """INNER distinct, newly constructed str objects (built outside the timed
    region). Partial slice of a concatenation: guaranteed-new on CPython —
    ``s + ""``, full-range slices, and ``"".join((s,))`` all return the
    original object and would defeat the cold-cache requirement."""
    return [(text + " ")[:-1] for _ in range(INNER)]


def _time(fn: Callable[[str], str], objs: list[str]) -> float:
    """Seconds for one call of fn over each of the INNER fresh objects."""
    start = perf_counter()
    for o in objs:
        fn(o)
    return perf_counter() - start


def measure() -> dict[str, dict[str, float]]:
    """Median disarm/comparator throughput ratio per input, interleaved per rep."""
    translit_fn: Callable[[str], str] = disarm.transliterate
    comparators = {name: fn for name, src in _COMPARATORS.items() if (fn := _load(src))}

    out: dict[str, dict[str, float]] = {}
    for label, text in INPUTS.items():
        # Per rep: time disarm and each comparator back-to-back (interleaved),
        # so a load spike hits both and cancels in the ratio.
        per_cmp: dict[str, list[float]] = {name: [] for name in comparators}
        for _ in range(REPS):
            # Fresh objects per timed run (regime fresh-string/v2): every call
            # pays the real, production cost of a never-seen str object.
            t_translit = _time(translit_fn, _fresh_copies(text))
            for name, fn in comparators.items():
                t_cmp = _time(fn, _fresh_copies(text))
                # ratio = how many x faster disarm is than the comparator
                per_cmp[name].append(t_cmp / t_translit if t_translit > 0 else float("nan"))
        out[label] = {name: round(statistics.median(rs), 3) for name, rs in per_cmp.items() if rs}
    return out


def main(argv: list[str]) -> int:
    ratios = measure()
    if "--json" in argv[1:]:
        print(
            json.dumps(
                {"regime": REGIME, "reps": REPS, "inner": INNER, "ratios": ratios},
                sort_keys=True,
            )
        )
        return 0
    comparators = sorted({c for r in ratios.values() for c in r})
    if not comparators:
        print("no comparators installed — nothing to compare")
        return 0
    header = f"{'input':10s}" + "".join(f"{c:>16s}" for c in comparators)
    print(f"disarm speed-up vs comparator (median of {REPS} interleaved reps; >1 = disarm faster)")
    print(header)
    print("-" * len(header))
    for label, row in ratios.items():
        line = f"{label:10s}" + "".join(f"{row.get(c, float('nan')):>15.2f}x" for c in comparators)
        print(line)
    print("\nValid only within an identical fingerprint bucket (see scripts/perf_fingerprint.py).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
