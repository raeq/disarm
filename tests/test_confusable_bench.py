"""#736 — `confusable-bench.v1` beside the adversarial corpus: an identifier against the name it
impersonates.

The corpus is 140 labelled identifier rows (120 malicious, 20 benign controls), checked in
verbatim under ``tests/fixtures/confusable_bench/``. Every row carries a ``protect`` list,
so the predicate surfaces and the key builders are scored on the same set-shaped question.

**Every number here was measured before it was written**, on the tree this test runs
against — not carried from the issue, which was measured at 0.14.1. Since then the detector
grew (#700, #701, #727, #937), `skeleton_key` (#650) and `nearest_match` (#894) landed,
and the two rows the issue pinned as the ASCII boundary are caught by an edit-distance
surface that is deliberately outside every Unicode transform.

The table on ``docs/security/adversarial-corpora.md`` is parsed and compared row by row, the
way the first corpus's table is, so a cell cannot go stale.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

import disarm

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "confusable_bench" / "confusable-bench.v1.json"
README = FIXTURE.parent / "README.md"
PAGE = ROOT / "docs" / "security" / "adversarial-corpora.md"

ROWS = json.loads(FIXTURE.read_text(encoding="utf-8"))
MALICIOUS = [r for r in ROWS if r["label"] == "malicious"]
CONTROLS = [r for r in ROWS if r["label"] != "malicious"]


def _collides(key, row) -> bool:
    return any(key(row["identifier"]) == key(p) for p in row["protect"])


def _lexicon(row) -> bool:
    return bool(disarm.inspect_anomalies(row["identifier"], row["protect"]).findings)


def _nearest(row) -> bool:
    return disarm.nearest_match(row["identifier"], list(row["protect"]), max_distance=1) is not None


#: Label on the page -> the policy. The labels are the page's first column, verbatim.
POLICIES = {
    "`has_anomalies(text)`": lambda r: disarm.has_anomalies(r["identifier"]),
    "`inspect_anomalies(text, lexicon=protect)`": _lexicon,
    "`is_confusable(text)`": lambda r: disarm.is_confusable(r["identifier"]),
    "`is_mixed_script(text)`": lambda r: disarm.is_mixed_script(r["identifier"]),
    "`catalog_key` collision": lambda r: _collides(disarm.catalog_key, r),
    "`canonicalize_strict` collision": lambda r: _collides(disarm.canonicalize_strict, r),
    "`skeleton_key` collision": lambda r: _collides(disarm.skeleton_key, r),
    '`skeleton_key(digit_policy="tr39")` collision': lambda r: _collides(
        lambda s: disarm.skeleton_key(s, digit_policy="tr39"), r
    ),
    "`nearest_match(max_distance=1)`": _nearest,
    "`nearest_match` **or** `is_confusable`": lambda r: (
        _nearest(r) or disarm.is_confusable(r["identifier"])
    ),
}


def _score(policy) -> tuple[int, int, int]:
    """(true positives, false negatives, false positives)."""
    tp = sum(1 for r in MALICIOUS if policy(r))
    fp = sum(1 for r in CONTROLS if policy(r))
    return tp, len(MALICIOUS) - tp, fp


class TestTheFixture:
    def test_it_is_the_published_file(self) -> None:
        sha = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        assert sha in README.read_text(encoding="utf-8")

    def test_the_shape_the_page_describes(self) -> None:
        assert (len(ROWS), len(MALICIOUS), len(CONTROLS)) == (140, 120, 20)
        assert all(r["protect"] for r in ROWS)


@pytest.mark.parametrize(
    "label", list(POLICIES), ids=[re.sub(r"\W+", "_", k).strip("_") for k in POLICIES]
)
def test_every_control_is_clean_under_every_policy(label: str) -> None:
    """Precision 1.000 everywhere: the twenty benign rows exist to keep the score honest."""
    _, _, fp = _score(POLICIES[label])
    assert fp == 0, label


def _published_rows() -> dict[str, tuple[int, int]]:
    text = PAGE.read_text(encoding="utf-8")
    section = text[text.index("## A second corpus") :]
    out = {}
    for m in re.finditer(
        r"^\|\s*(?P<label>`[^|]+?)\s*\|\s*(?P<tp>\d+)\s*\|\s*(?P<fn>\d+)\s*\|\s*[\d.]+\s*\|",
        section,
        re.M,
    ):
        out[m.group("label").strip()] = (int(m.group("tp")), int(m.group("fn")))
    return out


def test_the_page_table_names_every_policy_scored_here() -> None:
    assert set(_published_rows()) == set(POLICIES)


@pytest.mark.parametrize(
    "label", list(POLICIES), ids=[re.sub(r"\W+", "_", k).strip("_") for k in POLICIES]
)
def test_each_page_row_matches_the_measurement(label: str) -> None:
    tp, fn, _ = _score(POLICIES[label])
    assert _published_rows()[label] == (tp, fn), (label, tp, fn)


def test_two_calls_reach_every_malicious_row() -> None:
    tp, fn, fp = _score(POLICIES["`nearest_match` **or** `is_confusable`"])
    assert (tp, fn, fp) == (120, 0, 0)


def test_what_nearest_match_alone_misses_is_the_two_step_chain() -> None:
    misses = [r for r in MALICIOUS if not _nearest(r)]
    assert len(misses) == 7
    assert {r["category"] for r in misses} == {"confusable-chain"}
    for r in misses:
        # Two substitutions, so two edits: beyond a one-edit threshold by construction,
        # and every one is caught by the fold instead.
        assert disarm.edit_distance(r["identifier"], r["target"]) == 2
        assert disarm.is_confusable(r["identifier"])


def test_the_ascii_boundary_rows_are_caught_by_edit_distance_not_by_normalization() -> None:
    """The issue pinned `paypaI` and `paypa-l` as the two residual misses: pure ASCII, where
    every Unicode transform is a documented no-op. Both halves of that stay true — and an
    edit-distance surface, which is not a Unicode transform, now reports them."""
    rows = {r["identifier"]: r for r in MALICIOUS if r["identifier"] in ("paypaI", "paypa-l")}
    assert set(rows) == {"paypaI", "paypa-l"}
    for ident, r in rows.items():
        assert disarm.canonicalize(ident) == ident
        assert not disarm.is_confusable(ident)
        hit = disarm.nearest_match(ident, list(r["protect"]), max_distance=1)
        assert hit is not None and hit.value == "paypal" and hit.distance == 1


def test_the_composability_rows_answer_prototype_policy_s_question() -> None:
    """#646 §1 asked whether the NFKC/TR39 divergence class is in scope. The corpus's 31
    rows are its direct answer: all caught by the fold's view, and most by the detector
    through the `compat_fold` kind that did not exist when the issue was measured."""
    comp = [r for r in MALICIOUS if r["category"] == "nfkc-tr39-divergence"]
    assert len(comp) == 31
    assert all(disarm.is_confusable(r["identifier"]) for r in comp)
    reported = [r for r in comp if disarm.has_anomalies(r["identifier"])]
    assert len(reported) == 28
    assert all("compat_fold" in disarm.inspect_anomalies(r["identifier"]).kinds for r in reported)


def test_the_changelog_states_the_number_of_policies_the_registry_has() -> None:
    """Copilot on #956: the release note said nine where the table and this file score ten.
    Prose counts go stale; this pins the sentence to the registry."""
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    entry = changelog[changelog.index("`confusable-bench.v1` scored beside") :]
    entry = entry[: entry.index("\n- ")] if "\n- " in entry else entry
    words = {
        1: "one",
        2: "two",
        3: "three",
        4: "four",
        5: "five",
        6: "six",
        7: "seven",
        8: "eight",
        9: "nine",
        10: "ten",
        11: "eleven",
        12: "twelve",
    }
    assert f"scored across {words[len(POLICIES)]} policies" in entry, len(POLICIES)
