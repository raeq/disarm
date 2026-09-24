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

#: A fenced ``python`` block, matched against the line with its indentation
#: stripped. Deliberately not matching ``pycon`` or ``py``: Sybil's
#: PythonCodeBlockParser reads ``python`` only, so a page whose blocks are all
#: ``pycon`` genuinely has nothing for it to run.
PY_BLOCK = re.compile(r"^```python\s*$")

#: An opening or closing fence of three or more backticks, then an info string.
FENCE = re.compile(r"^(`{3,})(.*)$")


def _has_python_block(text: str) -> bool:
    """A ``python`` block at any indentation, not one quoted inside a longer fence.

    Indented fences count. A block nested in a ``===`` tab (pymdownx.tabbed) or a
    ``!!!`` admonition is indented by four spaces, and Sybil's Markdown lexer strips
    that prefix and runs it like any other block; see
    ``test_sybil_runs_an_indented_block_from_its_real_line`` below. A column-0-only
    match missed those, so ``upgrading.md`` held an example nothing was required to run.

    The recipe template in ``docs/contributing/documentation.md`` shows a ```python
    block inside a ````markdown one: it is an example of how to write a recipe, not a
    recipe, and running it would execute its illustrative ``make_fixture()``. Fence
    length is tracked the way ``scripts/check_doc_claims.py`` tracks it for the same
    template, so a shorter fence inside a longer block is content, at any indentation.
    """
    fence = 0
    for line in text.splitlines():
        stripped = line.strip()
        m = FENCE.match(stripped)
        if not m:
            continue
        ticks, info = len(m.group(1)), m.group(2).strip()
        if fence == 0:
            if PY_BLOCK.match(stripped):
                return True
            fence = ticks
        elif ticks >= fence and not info:
            fence = 0
    return False


#: Dated records rather than instructions — the same set the docs-vs-release gate
#: skips, and for the same reason. ``changelog`` is the archive of old release
#: sections, moved verbatim out of ``CHANGELOG.md``.
EXCLUDED_DIRS = frozenset({"reviews", "plans", "changelog", "__pycache__"})


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
        # Relative to docs/: an absolute path would drop every page of a checkout
        # that happens to live under a directory called, say, `changelog`.
        if path.is_symlink() or EXCLUDED_DIRS.intersection(path.relative_to(DOCS).parts):
            continue
        if _has_python_block(path.read_text(encoding="utf-8")):
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


def test_a_python_block_quoted_in_a_longer_fence_is_not_a_recipe() -> None:
    """The recipe template's nested block is content; a real block still counts.

    Both halves, so the fence tracking cannot pass by never finding anything.
    """
    template = "````markdown\n```python\nassert f() == 1\n```\n````\n"
    assert not _has_python_block(template)
    assert _has_python_block(template + "\n```python\nassert f() == 1\n```\n")
    assert _has_python_block("```python\nx = 1\n```\n")
    assert not _has_python_block("```pycon\n>>> x = 1\n```\n")


def test_an_indented_python_block_is_a_recipe() -> None:
    """An admonition's body is indented; its block is still a runnable example."""
    admonition = '!!! danger "Heads up"\n    ```python\n    assert f() == 1\n    ```\n'
    assert _has_python_block(admonition)
    assert not _has_python_block(admonition.replace("```python", "```pycon"))


def test_a_python_block_nested_in_a_tab_is_a_recipe() -> None:
    """pymdownx.tabbed content, including a tab that opens with prose."""
    tabs = (
        '=== "Before"\n\n    Some prose.\n\n    ```text\n    old\n    ```\n\n'
        '=== "After"\n\n    ```python\n    assert f() == 1\n    ```\n'
    )
    # The ```text block in the first tab opens and closes at the same indentation, so
    # the fence tracking is back at the top level by the time the python block starts.
    assert _has_python_block(tabs)
    assert not _has_python_block(tabs.replace("```python", "```pycon"))


def test_a_quoted_python_block_is_not_a_recipe_at_any_indentation() -> None:
    """Quoting is about fence length, not column: an indented template is content too.

    Covers both fences indented to the same depth inside a tab, the inner fence
    indented further than the outer, and the outer at column 0 with the inner
    indented, so no mix of indentation turns quoted content back into a recipe. Each
    case is also checked to flip once a real block follows, so the tracking cannot
    pass by never matching.
    """
    real = '\n=== "Tab"\n\n    ```python\n    assert f() == 1\n    ```\n'
    quoted = [
        # Outer and inner fences both indented, inside a tab.
        '=== "Template"\n\n    ````markdown\n    ```python\n    assert f() == 1\n'
        "    ```\n    ````\n",
        # Outer indented, inner indented further.
        "!!! example\n    ````markdown\n        ```python\n        assert f() == 1\n"
        "        ```\n    ````\n",
        # Outer at column 0, inner indented.
        "````markdown\n    ```python\n    assert f() == 1\n    ```\n````\n",
    ]
    for text in quoted:
        assert not _has_python_block(text), text
        assert _has_python_block(text + real), text


def test_sybil_runs_an_indented_block_from_its_real_line(tmp_path: Path) -> None:
    """The premise of counting indented blocks: Sybil executes them, dedented.

    Checked against the installed Sybil rather than asserted in a comment, because
    the gate above is only honest while this holds. Sybil's Markdown fence lexer
    captures the indentation as a ``prefix``, strips it from every line of the
    block, and anchors the example at the fence's own line, so a failure inside a
    tab reports the line an author would open. If a Sybil upgrade stopped doing
    that, indented examples would quietly stop running and this would say so.
    """
    from sybil import Sybil
    from sybil.parsers.markdown import PythonCodeBlockParser

    page = tmp_path / "page.md"
    page.write_text(
        "# Page\n"
        "\n"
        '=== "Tab"\n'
        "\n"
        "    ```python\n"  # line 5
        "    x = 1\n"
        "\n"
        "    assert x == 1\n"
        "    ```\n"
        "\n"
        '!!! note "Admonition"\n'
        "    ```python\n"  # line 12
        "    y = 2\n"
        "    ```\n",
        encoding="utf-8",
    )
    document = Sybil(parsers=[PythonCodeBlockParser()]).parse(page)
    examples = list(document)
    assert [e.line for e in examples] == [5, 12]
    assert [e.parsed for e in examples] == ["x = 1\n\nassert x == 1\n", "y = 2\n"]
    for example in examples:
        example.evaluate()
    assert document.namespace["y"] == 2
