"""#656: every documentation page with a Python block is executed by something.

Before the execute-only tier there were three states a page could be in, and the
third was invisible:

* on ``EXECUTED_RECIPES`` — blocks run, and their assertions are checked;
* no ``python`` blocks at all — nothing to run;
* **``python`` blocks and nothing running them**, so a signature change broke a
  published example in silence.

Eight pages were in that third state. The tier removed it; this file keeps it
removed, which the tier cannot do for itself — a new page with a code block joins
the tree without touching either list, and nothing would notice.

The ratchet is about *assertions* and is untouched. A page still joins
``EXECUTED_RECIPES`` only once its examples assert rather than decorate. What is
no longer available is writing a runnable example that nothing ever runs.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
CONFTEST = DOCS / "conftest.py"

#: A fenced ``python`` block. Deliberately not matching ``pycon`` or ``py``:
#: Sybil's PythonCodeBlockParser reads ``python`` only, so a page whose blocks
#: are all ``pycon`` genuinely has nothing for it to run.
PY_BLOCK = re.compile(r"^```python\s*$", re.MULTILINE)

#: Dated records rather than instructions — the same set the docs-vs-release gate
#: skips, and for the same reason.
EXCLUDED_DIRS = frozenset({"reviews", "plans", "__pycache__"})


def _list(name: str) -> list[str]:
    tree = ast.parse(CONFTEST.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return list(ast.literal_eval(node.value))
    raise AssertionError(f"{name} not found in docs/conftest.py")


def _pages_with_python_blocks() -> set[str]:
    found: set[str] = set()
    for path in DOCS.rglob("*.md"):
        if path.is_symlink() or EXCLUDED_DIRS.intersection(path.parts):
            continue
        if PY_BLOCK.search(path.read_text(encoding="utf-8")):
            found.add(str(path.relative_to(DOCS)))
    return found


def test_both_lists_exist_and_are_populated() -> None:
    """Empty lists would make every check below pass while testing nothing.

    Deliberately not a count. A threshold breaks on ordinary docs churn without
    indicating a coverage regression, and the thing worth guarding is the vacuous
    case — a renamed or emptied list — which emptiness catches on its own.
    """
    for name in ("EXECUTED_RECIPES", "EXECUTE_ONLY_RECIPES"):
        assert _list(name), (
            f"{name} is empty in docs/conftest.py. Sybil's `patterns` is built from "
            "both lists, so an empty one silently stops executing that whole tier "
            "and every check in this file still passes."
        )


def test_no_page_is_on_both_lists() -> None:
    """The two say different things about a page; it cannot say both."""
    both = set(_list("EXECUTED_RECIPES")) & set(_list("EXECUTE_ONLY_RECIPES"))
    assert not both, sorted(both)


def test_every_listed_page_exists() -> None:
    for name in _list("EXECUTED_RECIPES") + _list("EXECUTE_ONLY_RECIPES"):
        assert (DOCS / name).is_file(), f"{name} is listed but not present"


def test_every_page_with_python_blocks_is_executed() -> None:
    """The check the tier exists to make possible.

    A page carrying a runnable example that nothing runs is the state #656 was
    filed about. Adding one now fails here, and the fix is to put the page on a
    list rather than to widen this exclusion.
    """
    covered = set(_list("EXECUTED_RECIPES")) | set(_list("EXECUTE_ONLY_RECIPES"))
    orphans = sorted(_pages_with_python_blocks() - covered)
    assert not orphans, (
        "these pages have ```python blocks and are on neither recipe list, so "
        f"nothing executes them: {orphans}. Add each to EXECUTED_RECIPES if its "
        "examples assert, or to EXECUTE_ONLY_RECIPES if they only need to run."
    )


def test_the_scan_finds_every_listed_page() -> None:
    """A regex matching nothing would make the check above vacuous.

    Anchored to the lists rather than to a count. Every listed page is a recipe,
    so every one has a ```python block by construction — which makes the scan a
    superset of the lists, and makes that a fact about the tree rather than a
    number somebody has to keep updating. It also fails harder than a threshold:
    a regex that half-works is caught, not just one that matches nothing.
    """
    listed = set(_list("EXECUTED_RECIPES")) | set(_list("EXECUTE_ONLY_RECIPES"))
    scanned = _pages_with_python_blocks()
    missed = sorted(listed - scanned)
    assert not missed, (
        "these pages are on a recipe list but the scan did not find a ```python "
        f"block in them: {missed}. Either the scan is broken — which would make "
        "test_every_page_with_python_blocks_is_executed vacuous — or these pages "
        "no longer have runnable examples and should come off the list."
    )
