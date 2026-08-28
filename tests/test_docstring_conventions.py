"""#664: docstrings use the markup mkdocstrings is configured to read.

``mkdocs.yml`` sets ``docstring_style: google``. reStructuredText markup is not
processed under that setting, so a ``.. warning::`` directive renders as the
literal characters ``.. warning::`` on the published API reference, and a
``:func:`x``` cross-reference renders as the literal characters ``:func:``.

That is not a hypothetical. Before #664 there were 13 directives and 120 roles in
``python/disarm``, and 56 of the roles reached the built site as literal text
across seven API pages. One of them was ``strip_format``'s markup-safety
warning — a threat-model statement, rendered as an ordinary paragraph opening
with a stray ``.. warning::``.

Nothing caught it. ``mkdocs build --strict`` fails on broken links and missing
nav pages; markup that renders as text is neither. These tests are the check.

The equivalents that *do* render, and that also read correctly under ``help()``:

===========================  ==================================
reST                         Google / Markdown
===========================  ==================================
``.. warning::``             ``Warning:`` section
``.. note::``                ``Note:`` section
``.. deprecated:: X``        ``Deprecated:`` section, ``Since X.``
``:func:`canonicalize```     ```canonicalize```
===========================  ==================================
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parent.parent / "python" / "disarm"

#: ``.. warning::``, ``.. note::``, ``.. deprecated:: 0.11.0`` — block markup.
DIRECTIVE = re.compile(r"^\s*\.\.\s+(?P<name>[a-z-]+)::", re.MULTILINE)

#: ``:func:`x```, ``:class:`X```, ``:doc:`Label </path>``` — inline markup.
ROLE = re.compile(r":(?P<name>func|class|meth|data|mod|attr|obj|doc|ref|term):`")


def _modules() -> list[Path]:
    return sorted(p for p in PACKAGE.glob("*.py") if p.name != "__main__.py")


def _docstrings(path: Path) -> list[tuple[str, str]]:
    """Every docstring in a module, paired with a name for the failure message."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[str, str]] = []

    module_doc = ast.get_docstring(tree, clean=False)
    if module_doc:
        found.append((f"{path.name} (module)", module_doc))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                found.append((f"{path.name}::{node.name}", doc))
    return found


@pytest.mark.parametrize("module", _modules(), ids=lambda p: p.name)
def test_no_rest_directives_in_docstrings(module: Path) -> None:
    """A ``.. warning::`` renders as those exact characters on the site."""
    offenders = [
        (name, match.group("name"))
        for name, doc in _docstrings(module)
        for match in DIRECTIVE.finditer(doc)
    ]
    assert not offenders, (
        f"reST directives render as literal text under docstring_style: google. "
        f"Use a Google section instead (Warning:, Note:, Deprecated:). Found: {offenders}"
    )


@pytest.mark.parametrize("module", _modules(), ids=lambda p: p.name)
def test_no_rest_roles_in_docstrings(module: Path) -> None:
    """A ``:func:`x``` renders the literal ``:func:`` on the site."""
    offenders = [
        (name, match.group("name"))
        for name, doc in _docstrings(module)
        for match in ROLE.finditer(doc)
    ]
    assert not offenders, (
        f"reST roles render as literal text under docstring_style: google. "
        f"Use a plain code span — `name` — which reads correctly in help() too. "
        f"Found: {offenders}"
    )


def test_the_check_is_pointed_at_something() -> None:
    """A glob that matches nothing would pass both tests above forever."""
    modules = _modules()
    assert len(modules) >= 5, modules
    total = sum(len(_docstrings(m)) for m in modules)
    assert total > 100, f"only {total} docstrings found; the parser is not working"


def test_the_patterns_still_match_what_they_are_for() -> None:
    """Guards the other direction: a regex edited into matching nothing.

    Both tests above pass vacuously if the pattern stops working, and the whole
    convention would quietly lapse. These are the exact forms that were live in
    the tree before #664.
    """
    assert DIRECTIVE.search("    .. warning::\n       body")
    assert DIRECTIVE.search(".. deprecated:: 0.11.0")
    assert ROLE.search("see :func:`canonicalize`")
    assert ROLE.search("see :doc:`Limitations </limitations>`")

    # And that they do not fire on the replacements.
    assert not DIRECTIVE.search("    Warning:\n        body")
    assert not ROLE.search("see `canonicalize`")
