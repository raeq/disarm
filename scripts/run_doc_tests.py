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

The pages are independent of each other — that is the whole premise of running
them in separate processes — so the loop runs them concurrently (#658). Before
that it was 33 sequential interpreter-plus-collection starts for about 4.6s of
actual assertions, and the process starts were most of the wall time. Output is
buffered per page and printed in allowlist order, so a concurrent run reads the
same as a serial one.

Usage:
    python3 scripts/run_doc_tests.py            # all allowlisted pages
    python3 scripts/run_doc_tests.py -k slug    # extra args forwarded to pytest

Set ``DISARM_DOC_TEST_JOBS=1`` to run serially, which is worth doing when a page
fails and the interleaved-but-buffered output is harder to read than a plain one.
"""

from __future__ import annotations

import concurrent.futures
import os
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


def _run_one(rel: str, argv: list[str]) -> tuple[str, int, str]:
    """One page in its own pytest process. Returns (page, returncode, output)."""
    path = DOCS / rel
    if not path.exists():
        return rel, 1, f"MISSING: {rel}\n"
    result = subprocess.run(  # noqa: S603 — fixed argv, no shell
        [sys.executable, "-m", "pytest", str(path), "-q", "-p", "no:cacheprovider", *argv],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return rel, result.returncode, result.stdout + result.stderr


def _jobs(count: int) -> int:
    """How many pages to run at once.

    ``DISARM_DOC_TEST_JOBS`` overrides; 1 restores the serial behaviour. The
    default is capped at 8 because the work is process startup rather than
    compute, so more workers stop helping well before the core count does.
    """
    override = os.environ.get("DISARM_DOC_TEST_JOBS", "").strip()
    if override:
        try:
            return max(1, int(override))
        except ValueError:
            print(f"ignoring DISARM_DOC_TEST_JOBS={override!r}: not an integer", file=sys.stderr)
    return max(1, min(8, (os.cpu_count() or 1), count))


def main(argv: list[str]) -> int:
    recipes = _load_allowlist()
    jobs = _jobs(len(recipes))

    results: dict[str, tuple[int, str]] = {}
    if jobs == 1:
        for rel in recipes:
            _, code, output = _run_one(rel, argv)
            results[rel] = (code, output)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
            # Threads, not processes: each task only waits on a subprocess, so the
            # GIL is released for the whole of it.
            for rel, code, output in pool.map(lambda r: _run_one(r, argv), recipes):
                results[rel] = (code, output)

    # Only failures print their pytest output, and in allowlist order rather than
    # completion order — a concurrent run of a healthy suite says nothing, and a
    # failing one reads exactly like a serial run of just the pages that failed.
    failed = [rel for rel in recipes if results[rel][0] != 0]
    for rel in failed:
        print(f"--- {rel} " + "-" * max(0, 68 - len(rel)))
        print(results[rel][1].rstrip())
        print()

    print()
    if failed:
        print(f"FAILED ({len(failed)}/{len(recipes)}): {', '.join(failed)}")
        return 1
    print(f"All {len(recipes)} doc pages passed (per-file isolated, {jobs} at a time).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
