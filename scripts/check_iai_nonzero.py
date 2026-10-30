#!/usr/bin/env python3
"""Fail when a benchmark of the iai gate measured zero instructions, or none at all.

Callgrind counts only inside the benchmark function, which it finds by symbol. In a
stripped binary it finds nothing, every metric is 0, and a comparison reads 0 against 0
as "No change": the required "iai estimated-cycles gate" passed every pull request that
way from #893 until this check. A zero is never a valid measurement of a benchmark that
runs code, on either side of a comparison, so any zero fails.

Reads the `summary.json` each benchmark writes under `--save-summary=json`, in the
version 7 format of gungraun 0.20 (iai-callgrind until 0.17.0, hence the name). A summary
of another version, or one with no Callgrind instruction count in it, fails too: a
count this script cannot find is not a count that was checked.

Usage:
    python scripts/check_iai_nonzero.py [target/gungraun]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT_ROOT = Path("target") / "gungraun"

# The `version` gungraun 0.20 writes. The paths below are that version's: 6 kept the
# count at `summaries.total.summary.Callgrind.Ir.metrics`, as `{"Int": n}` under
# `Left`/`Right`/`Both`.
SUMMARY_VERSION = "7"


def _name(summary: dict) -> str:
    return f"{summary['module_path']} {summary.get('id', '')}".rstrip()


def instruction_counts(summary: dict) -> list[int | float]:
    """Every instruction count recorded for one benchmark: `new` (this run), `old` (the
    baseline), or both. Empty when the summary holds no Callgrind count."""
    counts: list[int | float] = []
    for profile in summary.get("profiles", []):
        if profile.get("tool") != "Callgrind":
            continue
        ir = profile.get("data", {}).get("total", {}).get("metrics", {}).get("Ir", {})
        counts.extend(ir.get("values", {}).values())
    return counts


def unmeasured(root: Path) -> tuple[list[str], list[str]]:
    """`(zero, missing)`: the benchmarks whose instruction count is 0 in the run or its
    baseline, and those with no Callgrind instruction count at all. Each sorted."""
    zero = []
    missing = []
    for path in sorted(root.rglob("summary.json")):
        summary = json.loads(path.read_text())
        version = summary.get("version")
        if version != SUMMARY_VERSION:
            sys.exit(
                f"{path}: summary version {version!r}, and this script reads version "
                f"{SUMMARY_VERSION}. Was gungraun bumped without it?"
            )
        counts = instruction_counts(summary)
        if not counts:
            missing.append(_name(summary))
        elif any(value == 0 for value in counts):
            zero.append(_name(summary))
    return sorted(zero), sorted(missing)


def zero_measurements(root: Path) -> list[str]:
    """Benchmarks whose instruction count is 0 in the run or its baseline, sorted."""
    return unmeasured(root)[0]


def main(argv: list[str]) -> None:
    root = Path(argv[0]) if argv else DEFAULT_ROOT
    found = list(root.rglob("summary.json"))
    if not found:
        sys.exit(f"no summary.json under {root}: run the bench with --save-summary=json")
    zero, missing = unmeasured(root)
    if missing:
        sys.exit(
            f"{len(missing)} of {len(found)} benchmarks have no Callgrind instruction count "
            "in their summary, so nothing was checked:\n  " + "\n  ".join(missing)
        )
    if zero:
        sys.exit(
            f"{len(zero)} of {len(found)} benchmarks measured 0 instructions, which is no "
            "measurement (is the benchmark binary stripped?):\n  " + "\n  ".join(zero)
        )
    print(f"all {len(found)} benchmarks measured a nonzero instruction count")


if __name__ == "__main__":
    main(sys.argv[1:])
