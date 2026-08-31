"""#746 — `code_context`, the only structure-preserving entry point.

Every one of the eleven `PRESETS` and both LLM profiles ends in `collapse_whitespace`,
which folds LF to a space by design (#433). Measured over this repository, all thirteen
collapse every file to a single line, and Python files stop parsing. So disarm claimed two
source-code CVEs and pointed LLM-stack authors at the guardrail path while shipping no
entry point whose output is still source code.

**Line count, indentation and case are the contract**, not a side effect — which is what
these tests exist to hold. The CVE gate could not see the gap because both its Trojan
Source vectors are single lines.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from disarm import canonicalize, get_pipeline, inspect_anomalies, is_confusable, list_profiles

ROOT = Path(__file__).resolve().parent.parent
CODE = get_pipeline("code_context")

#: The published multi-line Trojan Source PoC shape: a comment that closes early under
#: bidi reordering. Written as escapes, per #802.
TROJAN_C = """\
#include <stdio.h>
int main() {
    bool isAdmin = false;
    /*\u202e } \u2066if (isAdmin)\u2069 \u2066 begin admins only */
        printf("You are an admin.\\n");
    /* end admins only \u202e { \u2066*/
    return 0;
}
"""


def test_the_profile_is_registered() -> None:
    assert "code_context" in list_profiles()


# ── the contract: line count, indentation, case ──────────────────────────────


def _sources() -> list[Path]:
    """Every Python and Rust file in the repository — the corpus #746 measured."""
    out: list[Path] = []
    for suffix in (".py", ".rs"):
        out.extend(
            p
            for p in ROOT.rglob(f"*{suffix}")
            if not any(part in {".git", "target", "node_modules", ".venv"} for part in p.parts)
        )
    return sorted(out)


SOURCES = _sources()


def test_the_corpus_is_not_empty() -> None:
    """A gate over an empty corpus passes for the wrong reason."""
    assert len(SOURCES) > 100, len(SOURCES)


def test_line_count_is_invariant_over_the_repository() -> None:
    """`output.count("\\n") == input.count("\\n")` — #746 §2's first invariant.

    The thirteen other entry points change it on every file in this corpus.
    """
    changed = []
    for path in SOURCES:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if CODE(text).count("\n") != text.count("\n"):
            changed.append(str(path.relative_to(ROOT)))
    assert not changed, changed[:10]


def test_python_that_parses_still_parses() -> None:
    """#746 §2's second invariant, over every Python file in the repository."""
    broken = []
    for path in SOURCES:
        if path.suffix != ".py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
            ast.parse(text)
        except (UnicodeDecodeError, OSError, SyntaxError):
            continue  # not our baseline to hold
        try:
            ast.parse(CODE(text))
        except SyntaxError as exc:
            broken.append((str(path.relative_to(ROOT)), str(exc)))
    assert not broken, broken[:5]


def test_the_contrast_the_profile_exists_for() -> None:
    """`canonicalize` collapses this file to one line and it stops parsing."""
    text = Path(__file__).read_text(encoding="utf-8")
    assert canonicalize(text).count("\n") == 0
    assert CODE(text).count("\n") == text.count("\n")


@pytest.mark.parametrize(
    "source",
    [
        "def f():\n    return 1\n",
        "if x:\n\tpass\n",
        "class A:\n    def b(self):\n        pass\n",
    ],
    ids=["spaces", "tab", "nested"],
)
def test_indentation_survives(source: str) -> None:
    assert CODE(source) == source


def test_case_survives() -> None:
    """No `fold_case`: `MAX_RETRIES` and `max_retries` are different identifiers."""
    assert CODE("MAX_RETRIES = maxRetries") == "MAX_RETRIES = maxRetries"


def test_nfkc_does_not_run() -> None:
    """NFKC rewrites fullwidth forms and ligatures, which changes source text.

    The compatibility class is *reported* by the `compat_fold` kind instead — the same
    strip-and-report split the confusable class takes.
    """
    source = 'x = "ｆｕｌｌwidth"'
    assert CODE(source) == source
    # Reported, not rewritten. Mixed rather than whole-token, because a token spelled
    # *wholly* in fullwidth is the deliberate #722 exemption — `ＮＨＫ` is ordinary text.
    assert inspect_anomalies(source).kinds == ["compat_fold"]


# ── what it does remove ──────────────────────────────────────────────────────


def test_the_trojan_source_poc_comes_back_compilable() -> None:
    """Every bidi control removed, indentation and string delimiters intact."""
    out = CODE(TROJAN_C)
    assert out.count("\n") == TROJAN_C.count("\n")
    for control in ("\u202e", "\u2066", "\u2069"):
        assert control not in out
    assert out.count('"') == TROJAN_C.count('"')
    assert "    bool isAdmin = false;" in out


@pytest.mark.parametrize(
    ("ch", "name"),
    [
        ("\u202e", "RLO"),
        ("\u200b", "ZWSP"),
        ("\u200d", "ZWJ"),
        ("\ufeff", "BOM"),
        ("\x00", "NUL"),
        ("\x07", "BEL"),
    ],
    ids=["RLO", "ZWSP", "ZWJ", "BOM", "NUL", "BEL"],
)
def test_the_stripped_classes(ch: str, name: str) -> None:
    source = f"x = 1{ch}\ny = 2\n"
    out = CODE(source)
    assert ch not in out, name
    assert out.count("\n") == source.count("\n"), name


# ── strip-and-report: what stays report-only, and why ────────────────────────


def test_the_three_ascii_tr39_rows_are_not_folded() -> None:
    """Exactly three ASCII code points are TR39 sources (#725), and all three are syntax.

    The double quote folds to two apostrophes, the backtick to one, and the pipe to
    `l`. Folding them is why
    `normalize_confusables` breaks 287 of 287 Python files here while preserving every
    line — so a code profile has to leave them alone.
    """
    source = 'a = "x" | ' + chr(96) + "y" + chr(96) + "\n"
    assert CODE(source) == source


def test_the_homoglyph_class_is_reported_rather_than_rewritten() -> None:
    """The other half of strip-and-report: the predicates carry it.

    arXiv:2503.14281v4 §E rules rewriting out on quality grounds for the same reason —
    the useful answer is "this region of the gathered context is anomalous", not a
    rewritten prompt.
    """
    source = "def pɑypal():\n    pass\n"
    assert CODE(source) == source  # unchanged
    assert is_confusable(source)
    assert inspect_anomalies(source).kinds == ["confusable"]


def test_a_clean_result_is_not_a_claim_about_homoglyphs() -> None:
    """The contract a caller has to understand: strip is not the whole answer here."""
    source = "def pɑypal():\n    pass\n"
    out = CODE(source)
    assert "ɑ" in out, "the profile does not rewrite it"
    assert inspect_anomalies(out).kinds == ["confusable"], "the detector still reports it"


# ── a gate for a class I have now introduced twice ──────────────────────────


def test_no_python_source_emits_a_syntax_warning() -> None:
    """A docstring carrying `\\w` or a backslash in a non-raw string warns on import.

    Two have shipped: `\\w` in the `slugify` docstring (#712, fixed in #808) and a
    backslash in the `canonicalize` one (#719, fixed here). Both were invisible because a
    `SyntaxWarning` is not an error and pytest folds it into a summary line nobody reads.

    Found by the `ast.parse` loop above, which is what makes this cheap to hold.
    """
    import warnings

    offenders = []
    for path in SOURCES:
        if path.suffix != ".py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                ast.parse(text)
            except SyntaxError:
                continue
        offenders += [
            f"{path.relative_to(ROOT)}: {w.message}"
            for w in caught
            if issubclass(w.category, SyntaxWarning)
        ]
    assert not offenders, offenders
