#!/usr/bin/env python3
"""Run the cookbook doc-tests with per-FILE process isolation.

Some documented APIs mutate process-global state (``register_lang`` adds a
language for the lifetime of the process and cannot be unregistered;
``register_replacements`` adds user replacements). If every page ran in one
process, a registration in one page would leak into another and break exact
output assertions — e.g. a page that shows the full ``list_langs()`` list would
see an extra language registered by a *different* page.

Running each allowlisted page in its own ``pytest`` subprocess gives every page a
clean process, so the doc-tests verify exactly what each page documents,
independent of execution order. The allowlist is read from ``docs/conftest.py``
(single source of truth).

Usage:
    python3 scripts/run_doc_tests.py            # all allowlisted pages
    python3 scripts/run_doc_tests.py -k slug    # extra args forwarded to pytest
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs"


def _load_allowlist() -> list[str]:
    """Read EXECUTED_RECIPES from docs/conftest.py without importing it."""
    import ast

    source = (DOCS / "conftest.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "EXECUTED_RECIPES" for t in node.targets
        ):
            return list(ast.literal_eval(node.value))
    raise SystemExit("EXECUTED_RECIPES not found in docs/conftest.py")


def main(argv: list[str]) -> int:
    recipes = _load_allowlist()
    failed: list[str] = []
    for rel in recipes:
        path = DOCS / rel
        if not path.exists():
            print(f"MISSING: {rel}")
            failed.append(rel)
            continue
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(path), "-q", "-p", "no:cacheprovider", *argv],
            cwd=REPO_ROOT,
        )
        if result.returncode != 0:
            failed.append(rel)

    print()
    if failed:
        print(f"FAILED ({len(failed)}/{len(recipes)}): {', '.join(failed)}")
        return 1
    print(f"All {len(recipes)} doc pages passed (per-file isolated).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
