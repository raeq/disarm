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
    assert len(_list("EXECUTED_RECIPES")) > 20
    assert _list("EXECUTE_ONLY_RECIPES")


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


def test_the_scan_finds_something() -> None:
    """A regex that matched nothing would make the check above vacuous."""
    pages = _pages_with_python_blocks()
    assert len(pages) > 25, sorted(pages)
