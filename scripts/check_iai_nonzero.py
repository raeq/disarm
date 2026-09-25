#!/usr/bin/env python3
"""Fail when an iai-callgrind benchmark measured zero instructions.

Callgrind counts only inside the benchmark function, which it finds by symbol. In a
stripped binary it finds nothing, every metric is 0, and a comparison reads 0 against 0
as "No change": the required "iai estimated-cycles gate" passed every pull request that
way from #893 until this check. A zero is never a valid measurement of a benchmark that
runs code, on either side of a comparison, so any zero fails.

Reads the `summary.json` each benchmark writes under `--save-summary=json`.

Usage:
    python scripts/check_iai_nonzero.py [target/iai]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT_ROOT = Path("target") / "iai"


def _values(metrics: dict) -> list[int | float]:
    """Every side iai recorded: `Left` (this run), `Right` (baseline), or `Both`."""
    sides = metrics.get("Both") or [metrics[k] for k in ("Left", "Right") if k in metrics]
    return [next(iter(side.values())) for side in sides]


def zero_measurements(root: Path) -> list[str]:
    """Benchmarks whose instruction count is 0 in the run or its baseline, sorted."""
    zero = []
    for path in sorted(root.rglob("summary.json")):
        summary = json.loads(path.read_text())
        name = f"{summary['module_path']} {summary['id']}"
        for profile in summary["profiles"]:
            if profile.get("tool") != "Callgrind":
                continue
            ir = profile["summaries"]["total"]["summary"]["Callgrind"]["Ir"]["metrics"]
            if any(value == 0 for value in _values(ir)):
                zero.append(name)
    return sorted(zero)


def main(argv: list[str]) -> None:
    root = Path(argv[0]) if argv else DEFAULT_ROOT
    found = list(root.rglob("summary.json"))
    if not found:
        sys.exit(f"no summary.json under {root}: run the bench with --save-summary=json")
    zero = zero_measurements(root)
    if zero:
        sys.exit(
            f"{len(zero)} of {len(found)} benchmarks measured 0 instructions, which is no "
            "measurement (is the benchmark binary stripped?):\n  " + "\n  ".join(zero)
        )
    print(f"all {len(found)} benchmarks measured a nonzero instruction count")


if __name__ == "__main__":
    main(sys.argv[1:])
