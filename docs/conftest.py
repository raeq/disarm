"""Sybil doc-test harness for the cookbook (#154).

Every fenced ``python`` block in the Markdown files under ``docs/`` is executed
against the **installed** ``translit`` wheel, and any ``assert`` it contains is
checked. This is what keeps published recipes from rotting: a wrong claim or a
broken snippet turns the test suite red, gated alongside the existing tiers.

Authoring rules for recipes (see CONTRIBUTING.md → "Doc-test recipes"):

* Assert outputs, never decorate them with ``# =>`` comments.
* Use the **public API only** — reaching into internals is itself a doc bug.
* A document shares one namespace top-to-bottom, so import once and reuse.
* Hide setup/teardown in ``<!--- invisible-code-block: python ... -->`` blocks.
* Skip a block that is intentionally not runnable with ``<!--- skip: next -->``.
"""

from __future__ import annotations

from sybil import Sybil
from sybil.parsers.markdown import PythonCodeBlockParser, SkipParser

# Allowlist of converted recipes whose ``python`` blocks are executed and
# asserted. This is a deliberate ratchet: a page joins the list only once its
# examples are asserted (not decorated with ``# =>``). #154 seeds it with one
# recipe; #156 grows it to the whole cookbook and adds the anti-rot lint that
# keeps un-converted pages visibly unguarded. Paths are relative to docs/.
EXECUTED_RECIPES = [
    "user-guide/filenames.md",
]

pytest_collect_file = Sybil(
    parsers=[
        PythonCodeBlockParser(),
        SkipParser(),
    ],
    patterns=EXECUTED_RECIPES,
).pytest()
