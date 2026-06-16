"""Sybil doc-test harness for the cookbook (#154).

Every fenced ``python`` block in the Markdown files under ``docs/`` is executed
against the **installed** ``disarm`` wheel, and any ``assert`` it contains is
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

import disarm


def _reset_global_state(namespace: dict) -> None:
    """Clear user-registered replacements before/after each document.

    Defensive hygiene for in-process runs. Full cross-page isolation (needed
    because ``register_lang`` is process-global and not reversible) is provided
    by running each page in its own subprocess — see ``scripts/run_doc_tests.py``,
    which is the doc-test gate. That isolation is what lets the ``list_langs()`` /
    ``list_scripts()`` pages assert their exact documented output.
    """
    disarm.clear_replacements()


# Allowlist of converted recipes whose ``python`` blocks are executed and
# asserted. This is a deliberate ratchet: a page joins the list only once its
# examples are asserted (not decorated with ``# =>``). #154 seeds it with one
# recipe; #156 grows it to the whole cookbook and adds the anti-rot lint that
# keeps un-converted pages visibly unguarded. Paths are relative to docs/.
EXECUTED_RECIPES = [
    "index.md",
    "python/getting-started.md",
    # performance.md is tables-only (#322); its executable claims now live in
    # tests/test_performance_claims.py, so it is intentionally not doctested here.
    "policy-templates.md",
    "api/classes.md",
    "api/enums.md",
    "api/graphemes.md",
    "api/language-profiles.md",
    "api/pipelines.md",
    "api/transforms.md",
    "architecture/emoji-plugins.md",
    "migration/from-anyascii.md",
    "migration/from-confusable-homoglyphs.md",
    "migration/from-pathvalidate.md",
    "migration/from-python-slugify.md",
    "migration/from-unidecode.md",
    "migration/unidecode-recipes.md",
    "security/adversarial-defense.md",
    "user-guide/abjad-transliteration.md",
    "user-guide/confusables.md",
    "user-guide/filenames.md",
    "user-guide/graphemes.md",
    "user-guide/anomaly-detection.md",
    "user-guide/language-detection.md",
    "user-guide/language-support.md",
    "user-guide/llm-pipelines.md",
    "user-guide/normalization.md",
    "user-guide/normalize-first.md",
    "user-guide/pipeline.md",
    "user-guide/slugification.md",
    "user-guide/tokenizer-preprocessing.md",
    "user-guide/text-cleaning.md",
    "user-guide/transliteration.md",
]

pytest_collect_file = Sybil(
    parsers=[
        PythonCodeBlockParser(),
        SkipParser(),
    ],
    # `Path.match` is suffix-based, so a bare "index.md" pattern also matches
    # api/index.md and migration/index.md — exclude those (they are not on the
    # allowlist).
    excludes=["api/index.md", "migration/index.md"],
    setup=_reset_global_state,
    teardown=_reset_global_state,
    patterns=EXECUTED_RECIPES,
).pytest()
