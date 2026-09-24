"""Render an lcov file as a Markdown coverage table, lowest-covered module first.

    cargo llvm-cov --no-default-features --branch --lcov --output-path lcov.info
    python3 scripts/coverage_summary.py lcov.info

Used by ``.github/workflows/coverage.yml`` for the job summary, and locally for the
baseline recorded in ``docs/architecture/testing-guarantees.md``. Report only: nothing
here compares against a threshold.

Only files under ``src/`` are listed; the integration tests themselves are not the thing
being measured. Branch columns read ``-`` when the lcov carries no branch records (a
stable toolchain, which cannot instrument branches).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileCov:
    lines_found: int = 0
    lines_hit: int = 0
    branches_found: int = 0
    branches_hit: int = 0
    functions_found: int = 0
    functions_hit: int = 0


def parse(lcov: str) -> dict[str, FileCov]:
    """Per-source-file totals from the LF/LH, BRF/BRH and FNF/FNH summary records."""
    out: dict[str, FileCov] = {}
    current: FileCov | None = None
    fields = {
        "LF": "lines_found",
        "LH": "lines_hit",
        "BRF": "branches_found",
        "BRH": "branches_hit",
        "FNF": "functions_found",
        "FNH": "functions_hit",
    }
    for line in lcov.splitlines():
        key, _, value = line.partition(":")
        if key == "SF":
            current = out.setdefault(value, FileCov())
        elif key in fields and current is not None:
            setattr(current, fields[key], getattr(current, fields[key]) + int(value))
        elif key == "end_of_record":
            current = None
    return out


def pct(hit: int, found: int) -> str:
    return "-" if found == 0 else f"{100 * hit / found:.1f}%"


def module(path: str) -> str | None:
    """`src/...` relative path, or None for anything outside the crate's sources."""
    parts = Path(path).parts
    if "src" not in parts:
        return None
    i = len(parts) - 1 - parts[::-1].index("src")
    return "/".join(parts[i:])


def render(files: dict[str, FileCov]) -> str:
    rows = [(m, c) for p, c in files.items() if (m := module(p)) is not None]
    rows.sort(key=lambda r: (r[1].lines_hit / r[1].lines_found if r[1].lines_found else 1.0, r[0]))
    total = FileCov()
    for _, c in rows:
        for f in vars(total):
            setattr(total, f, getattr(total, f) + getattr(c, f))
    out = [
        "| Module | Lines | Branches | Functions |",
        "|---|---:|---:|---:|",
        f"| **Total** | **{pct(total.lines_hit, total.lines_found)}** "
        f"({total.lines_hit:,}/{total.lines_found:,}) | "
        f"**{pct(total.branches_hit, total.branches_found)}** | "
        f"**{pct(total.functions_hit, total.functions_found)}** |",
    ]
    for m, c in rows:
        out.append(
            f"| `{m}` | {pct(c.lines_hit, c.lines_found)} ({c.lines_hit:,}/{c.lines_found:,}) "
            f"| {pct(c.branches_hit, c.branches_found)} "
            f"| {pct(c.functions_hit, c.functions_found)} |"
        )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("lcov", type=Path, help="an lcov file (cargo llvm-cov --lcov)")
    args = parser.parse_args(argv)
    files = parse(args.lcov.read_text(encoding="utf-8"))
    if not any(module(p) for p in files):
        print(f"no src/ files in {args.lcov}", file=sys.stderr)
        return 1
    print(render(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
