#!/usr/bin/env python3
"""Condense a TLC counterexample to one line per step: the action and what it changed.

python3 formal/tla/WatchPR/trace_summary.py formal/tla/WatchPR/traces/<run>.txt
"""

from __future__ import annotations

import re
import sys

KEYS = [
    "pc",
    "head",
    "viewHead",
    "ck",
    "ghost",
    "unres",
    "overflow",
    "requested",
    "review",
    "reviewHead",
    "behind",
    "prState",
    "stuckN",
    "failN",
    "fails",
    "snap",
    "issue",
    "mfacts",
    "stop",
    "dec",
]


def main(path: str) -> None:
    text = open(path, encoding="utf-8").read()
    prev: dict[str, str] = {}
    for block in re.split(r"\n(?=State \d+:)", text):
        m = re.match(r"State (\d+): <(\w+)", block)
        if not m:
            if "Back to state" in block or "Stuttering" in block:
                print(block.strip().splitlines()[0])
            continue
        vals = {}
        for k in KEYS:
            mm = re.search(r"^/\\ " + k + r" = (.*?)(?=\n/\\ |\n\n|\Z)", block, re.S | re.M)
            if mm:
                vals[k] = " ".join(mm.group(1).split())
        changed = {k: v for k, v in vals.items() if prev.get(k) != v}
        print(
            f"{m.group(1):>3} {m.group(2):<22} " + "; ".join(f"{k}={v}" for k, v in changed.items())
        )
        prev = vals
    for line in text.splitlines():
        if line.startswith("Error:") and "behavior" not in line:
            print(line)


if __name__ == "__main__":
    main(sys.argv[1])
