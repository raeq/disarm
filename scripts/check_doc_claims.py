#!/usr/bin/env python3
"""Anti-rot lint: forbid decorative output claims in documentation (#156).

Cookbook examples must *assert* their outputs, not decorate them with
``# =>`` / ``# →`` comments that nothing verifies. This check scans every
``python`` fenced block under ``docs/`` and fails if a claim-arrow remains.

A claim-arrow is ``=>`` or ``→`` appearing as the first token of a ``#``
comment, e.g. ``slugify("x")  # => "x"``. Descriptive comments that merely
contain an arrow (``# Cyrillic а → a``) are fine — the arrow is not the first
token. Blocks that cannot run in the doc-test environment should be skip-marked
(``<!--- skip: next -->``) with their arrows rewritten to plain comments.

Usage:
    python3 scripts/check_doc_claims.py            # scan docs/
    python3 scripts/check_doc_claims.py path ...   # scan specific files
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CLAIM_ARROW = re.compile(r"#\s*(?:=>|→)\s")


def offenders_in(path: Path) -> list[tuple[int, str]]:
    """Return (line_number, line) for every claim-arrow inside a python block."""
    found: list[tuple[int, str]] = []
    in_fence = False
    lang: str | None = None
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_fence:
                in_fence = True
                lang = stripped.strip("`").strip()
            else:
                in_fence = False
                lang = None
            continue
        if in_fence and lang == "python" and CLAIM_ARROW.search(line):
            found.append((lineno, line.strip()))
    return found


def main(argv: list[str]) -> int:
    if argv:
        files = [Path(a) for a in argv]
    else:
        files = sorted(Path("docs").rglob("*.md"))

    total = 0
    for path in files:
        offenders = offenders_in(path)
        if offenders:
            total += len(offenders)
            print(f"{path}: {len(offenders)} decorative claim(s)")
            for lineno, text in offenders:
                print(f"  L{lineno}: {text}")

    if total:
        print(
            f"\n{total} decorative '# =>' / '# →' claim(s) found. Convert them to "
            "asserted examples (see CONTRIBUTING.md → Doc-test recipes), or "
            "skip-mark the block and drop the arrow.",
            file=sys.stderr,
        )
        return 1
    print("No decorative doc claims found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
