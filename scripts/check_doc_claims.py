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


#: An opening/closing code fence: 3+ backticks, then an optional info string.
_FENCE = re.compile(r"^(`{3,})(.*)$")


def offenders_in(path: Path) -> list[tuple[int, str]]:
    """Return (line_number, line) for every claim-arrow inside a python block.

    Fence length is tracked (``` vs ````) so a shorter nested fence inside a
    longer one — e.g. a ```python sample inside a ````markdown recipe template —
    is treated as content and does not prematurely close the outer block.
    """
    found: list[tuple[int, str]] = []
    fence_len = 0  # 0 = not in a fence; otherwise the opening backtick count
    lang: str | None = None
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = _FENCE.match(line.strip())
        if m:
            ticks, info = len(m.group(1)), m.group(2).strip()
            if fence_len == 0:
                fence_len, lang = ticks, (info or None)
                continue
            if ticks >= fence_len and not info:
                fence_len, lang = 0, None
                continue
            # A nested/shorter fence inside an open block: content, not a close.
        if fence_len and lang == "python" and CLAIM_ARROW.search(line):
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
