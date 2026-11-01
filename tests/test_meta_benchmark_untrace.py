"""`untrace-techniques` reads untrace's inputs against untrace's expected reports (#1204)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import disarm
from benchmarks.meta.protocol import Outcome, Status
from benchmarks.meta.suites import comparators
from benchmarks.meta.suites.comparators import UntraceTechniques
from benchmarks.meta.suites.practitioner import tree_digest

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

ZWSP = chr(0x200B)
REPO_ROOT = Path(__file__).resolve().parent.parent

HIDDEN = "  1:3  detected  U+200B Zero Width Space (hidden)"
TYPOGRAPHIC = "  1:3  detected  U+2014 Em Dash (typographic)"
PAYLOAD = "  !! hidden payload (tag-ascii) decodes to 'x' across 9 characters"
MIXED = "  1:1  mixed-script  'x' mixes Cyrillic and Latin"
METADATA = "  metadata  xmp creator = 'x' (9 bytes)"


def _report(named: dict[str, list[str]], scanned: int) -> str:
    lines: list[str] = []
    for name, body in named.items():
        lines.extend([name, *body])
    if named:
        lines.append(f"found: 1 marker(s) in {len(named)} of {scanned} file(s)")
    else:
        lines.append(f"clean: {scanned} file(s) scanned")
    return "\n".join(lines) + "\n"


def _case(
    root: Path,
    name: str,
    inputs: dict[str, str],
    named: dict[str, list[str]],
    scanned: int | None = None,
    args: str | None = None,
) -> Path:
    case = root / "cases" / name
    for rel, text in inputs.items():
        path = case / "in" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    case.mkdir(parents=True, exist_ok=True)
    (case / "want.txt").write_text(_report(named, scanned or len(inputs)), encoding="utf-8")
    if args is not None:
        (case / "args").write_text(args, encoding="utf-8")
    return case


def _classes(root: Path) -> Path:
    """One file of each class, so a run has something on both sides of the control."""
    _case(root, "payload", {"p.txt": "payload text"}, {"p.txt": [PAYLOAD]})
    _case(root, "hidden", {"h.txt": "hidden text"}, {"h.txt": [HIDDEN]})
    _case(root, "mixed", {"m.txt": "mixed text"}, {"m.txt": [MIXED]})
    _case(root, "typography", {"t.txt": "typographic text"}, {"t.txt": [TYPOGRAPHIC]})
    _case(root, "clean", {"c.txt": "clean text"}, {})
    return root


def _never(_text: str) -> bool:
    return False


def _always(_text: str) -> bool:
    return True


def _measure(root: Path, monkeypatch, *, anomalies=_never, primitive=_never, limit=None) -> Outcome:
    monkeypatch.setattr(
        comparators,
        "detectors",
        lambda: {"has_anomalies": anomalies, "is_confusable": primitive},
    )
    suite = UntraceTechniques()
    suite.locate = lambda: root
    outcome = Outcome(suite=suite.name, family=suite.family, provenance=suite.provenance)
    suite.measure(outcome, limit)
    return outcome


def _row(outcome: Outcome, key: str) -> tuple[float, float | None]:
    measurement = outcome.measurement(key)
    assert measurement is not None, key
    return measurement.value, measurement.of


# --- what is read ----------------------------------------------------------


def test_a_command_line_and_an_expected_report_are_never_probes(tmp_path, monkeypatch):
    _classes(tmp_path)
    (tmp_path / "cases/clean/args").write_text(".", encoding="utf-8")
    seen: list[str] = []

    def spy(text: str) -> bool:
        seen.append(text)
        return False

    _measure(tmp_path, monkeypatch, anomalies=spy)
    assert sorted(set(seen)) == [
        "clean text",
        "hidden text",
        "mixed text",
        "payload text",
        "typographic text",
    ]


def test_every_text_file_under_in_is_read(tmp_path, monkeypatch):
    _classes(tmp_path)
    case = _case(
        tmp_path,
        "several",
        {"a.txt": "first file", "sub/b.md": "second file", "c.py": "third file"},
        {},
    )
    (case / "in/image.png").write_bytes(b"\x89PNG\x00")
    (case / "in/noise.dat").write_bytes(b"\xff\xfe\x00")
    (case / "want.txt").write_text(_report({}, 5), encoding="utf-8")
    seen: list[str] = []

    def spy(text: str) -> bool:
        seen.append(text)
        return False

    outcome = _measure(tmp_path, monkeypatch, anomalies=spy)
    assert {"first file", "second file", "third file"} <= set(seen)
    assert _row(outcome, "files")[0] == 8


def test_a_case_with_no_plain_run_is_counted_and_left_out(tmp_path, monkeypatch):
    _classes(tmp_path)
    _case(tmp_path, "flagged", {"f.txt": "flagged text"}, {}, args="--json .")
    seen: list[str] = []

    def spy(text: str) -> bool:
        seen.append(text)
        return False

    outcome = _measure(tmp_path, monkeypatch, anomalies=spy)
    assert "flagged text" not in seen
    assert _row(outcome, "cases") == (6, None)
    assert _row(outcome, "cases_left_out") == (1, 6)


def test_a_report_that_is_not_text_is_left_out(tmp_path, monkeypatch):
    _classes(tmp_path)
    case = _case(tmp_path, "bad-config", {"b.txt": "bad config"}, {})
    (case / "want.txt").write_text('{"error": "nope"}\n', encoding="utf-8")
    outcome = _measure(tmp_path, monkeypatch)
    assert _row(outcome, "cases_left_out") == (1, 6)


def test_a_plain_run_under_runs_is_read_when_the_case_itself_is_flagged(tmp_path, monkeypatch):
    _classes(tmp_path)
    case = _case(tmp_path, "tree", {"x.txt": "tree text"}, {}, args="--json .")
    run = case / "runs/plain"
    run.mkdir(parents=True)
    (run / "args").write_text(".", encoding="utf-8")
    (run / "want.txt").write_text(_report({"x.txt": [HIDDEN]}, 1), encoding="utf-8")
    outcome = _measure(tmp_path, monkeypatch, anomalies=lambda s: s == "tree text")
    assert _row(outcome, "has_anomalies_on_hidden") == (1, 2)
    assert _row(outcome, "cases_left_out") == (0, 6)


# --- what a file's label is ------------------------------------------------


def test_each_class_comes_from_the_report(tmp_path, monkeypatch):
    _classes(tmp_path)
    outcome = _measure(tmp_path, monkeypatch, anomalies=_always)
    assert _row(outcome, "has_anomalies_on_payload") == (1, 1)
    assert _row(outcome, "has_anomalies_on_hidden") == (1, 1)
    assert _row(outcome, "has_anomalies_on_mixed_script") == (1, 1)
    assert _row(outcome, "has_anomalies_on_typographic") == (1, 1)
    assert _row(outcome, "has_anomalies_on_clean") == (1, 1)


def test_a_hidden_marker_outranks_typography_in_the_same_file(tmp_path, monkeypatch):
    _classes(tmp_path)
    _case(tmp_path, "both", {"b.txt": "both"}, {"b.txt": [TYPOGRAPHIC, HIDDEN]})
    outcome = _measure(tmp_path, monkeypatch, anomalies=lambda s: s == "both")
    assert _row(outcome, "has_anomalies_on_hidden") == (1, 2)
    assert _row(outcome, "has_anomalies_on_typographic") == (0, 1)


def test_a_file_a_run_ignored_has_no_verdict(tmp_path, monkeypatch):
    """The report scanned fewer files than exist, and it does not say which it skipped."""
    _classes(tmp_path)
    _case(
        tmp_path,
        "gitignore",
        {"kept.txt": "kept", "secret.txt": "secret", ".gitignore": "secret.txt\n"},
        {"kept.txt": [HIDDEN]},
        scanned=2,
    )
    outcome = _measure(tmp_path, monkeypatch, anomalies=lambda s: s == "secret")
    assert _row(outcome, "has_anomalies_on_clean") == (0, 1)
    assert _row(outcome, "files_without_verdict") == (2, 8)
    assert _row(outcome, "has_anomalies_on_hidden") == (0, 2)


def test_a_case_with_a_config_answers_to_it_so_an_unnamed_file_has_no_verdict(
    tmp_path, monkeypatch
):
    _classes(tmp_path)
    _case(
        tmp_path,
        "tree-config",
        {".untrace.json": "{}", "docs/attack.md": "attack", "src/a.py": "named"},
        {"src/a.py": [HIDDEN]},
    )
    outcome = _measure(tmp_path, monkeypatch, anomalies=lambda s: s == "attack")
    assert _row(outcome, "has_anomalies_on_clean") == (0, 1)
    assert _row(outcome, "files_without_verdict") == (2, 8)
    assert _row(outcome, "has_anomalies_on_hidden") == (0, 2)


def test_a_file_that_suppressed_itself_has_no_verdict(tmp_path, monkeypatch):
    _classes(tmp_path)
    _case(tmp_path, "suppression", {"whole.py": "# untrace:ignore-file\nx = 1\n"}, {})
    outcome = _measure(tmp_path, monkeypatch, anomalies=lambda s: "ignore-file" in s)
    assert _row(outcome, "has_anomalies_on_clean") == (0, 1)
    assert _row(outcome, "files_without_verdict") == (1, 6)


def test_firing_on_a_file_with_only_metadata_is_a_false_positive(tmp_path, monkeypatch):
    """`legitimate-authors`: untrace names the file for its metadata and finds no marker."""
    _classes(tmp_path)
    _case(tmp_path, "legitimate-authors", {"drawing.svg": "drawing"}, {"drawing.svg": [METADATA]})
    outcome = _measure(tmp_path, monkeypatch, anomalies=lambda s: s == "drawing")
    assert _row(outcome, "has_anomalies_on_clean") == (1, 2)
    measurement = outcome.measurement("has_anomalies_on_clean")
    assert measurement is not None
    assert measurement.higher_is_better is False


# --- the rows and the control ----------------------------------------------


def test_the_old_rows_are_gone(tmp_path, monkeypatch):
    _classes(tmp_path)
    keys = {m.key for m in _measure(tmp_path, monkeypatch).measurements}
    assert not keys & {"techniques", "reported_by_any_detector", "silent"}


def test_only_the_primitives_on_a_clean_file_are_directed(tmp_path, monkeypatch):
    """`is_confusable` firing on a Russian file says nothing about a hidden character."""
    _classes(tmp_path)
    outcome = _measure(tmp_path, monkeypatch, primitive=_always)
    directions = {m.key: m.higher_is_better for m in outcome.measurements}
    assert directions["has_anomalies_on_payload"] is True
    assert directions["has_anomalies_on_hidden"] is True
    assert directions["has_anomalies_on_mixed_script"] is True
    assert directions["has_anomalies_on_typographic"] is None
    assert directions["has_anomalies_on_clean"] is False
    assert directions["primitives_on_payload"] is None
    assert directions["primitives_on_hidden"] is None
    assert directions["primitives_on_mixed_script"] is None
    assert directions["primitives_on_typographic"] is None
    assert directions["primitives_on_clean"] is False


def test_a_primitive_is_reported_apart_from_has_anomalies(tmp_path, monkeypatch):
    _classes(tmp_path)
    outcome = _measure(tmp_path, monkeypatch, primitive=_always)
    assert _row(outcome, "has_anomalies_on_hidden") == (0, 1)
    assert _row(outcome, "primitives_on_hidden") == (1, 1)
    assert _row(outcome, "has_anomalies_tpr_minus_fpr")[0] == 0


def test_a_detector_that_always_fires_is_no_better_than_one_that_never_does(tmp_path, monkeypatch):
    _classes(tmp_path)
    always = _measure(tmp_path, monkeypatch, anomalies=_always)
    never = _measure(tmp_path, monkeypatch, anomalies=_never)
    assert _row(always, "has_anomalies_tpr_minus_fpr")[0] == 0
    assert _row(never, "has_anomalies_tpr_minus_fpr")[0] == 0
    assert _row(always, "control_always_fires")[0] == 0


def test_a_detector_that_reports_only_the_positives_scores_one(tmp_path, monkeypatch):
    _classes(tmp_path)
    outcome = _measure(tmp_path, monkeypatch, anomalies=lambda s: "clean" not in s)
    assert _row(outcome, "has_anomalies_tpr_minus_fpr")[0] == 1


def test_a_corpus_with_no_clean_file_cannot_report(tmp_path, monkeypatch):
    """Always firing would score best on it, which is the failure the control exists for."""
    _case(tmp_path, "payload", {"p.txt": "payload text"}, {"p.txt": [PAYLOAD]})
    with pytest.raises(ValueError, match="always fires"):
        _measure(tmp_path, monkeypatch)


def test_a_run_of_such_a_corpus_ends_in_an_error(tmp_path, monkeypatch):
    _case(tmp_path, "payload", {"p.txt": "payload text"}, {"p.txt": [PAYLOAD]})
    monkeypatch.setattr(comparators, "detectors", lambda: {"has_anomalies": _never})
    suite = UntraceTechniques()
    suite.locate = lambda: tmp_path
    suite.available = lambda: (True, "")
    assert suite.run().status is Status.ERROR


def test_a_limit_keeps_every_class(tmp_path, monkeypatch):
    _classes(tmp_path)
    _case(tmp_path, "more", {"a.txt": "more hidden", "b.txt": "still more"}, {"a.txt": [HIDDEN]})
    outcome = _measure(tmp_path, monkeypatch, limit=1)
    for key in ("payload", "hidden", "mixed_script", "typographic", "clean"):
        assert _row(outcome, f"has_anomalies_on_{key}")[1] == 1


def test_altered_ignores_whitespace(tmp_path, monkeypatch):
    spaced = "two   spaces and\n\n\nthree lines"
    assert disarm.strip_obfuscation(spaced) != spaced
    assert " ".join(disarm.strip_obfuscation(spaced).split()) == " ".join(spaced.split())
    _classes(tmp_path)
    _case(tmp_path, "spaced", {"s.txt": spaced}, {})
    unchanged = _measure(tmp_path, monkeypatch)
    assert _row(unchanged, "altered_by_strip_obfuscation") == (0, 6)
    _case(tmp_path, "carrier", {"z.txt": "pay" + ZWSP + "pal"}, {})
    changed = _measure(tmp_path, monkeypatch)
    assert _row(changed, "altered_by_strip_obfuscation") == (1, 7)


# --- the pin ---------------------------------------------------------------


def test_the_source_is_pinned_to_a_commit_and_a_digest():
    source = UntraceTechniques.SOURCES[0]
    assert re.search(r"/tar\.gz/[0-9a-f]{40}$", source.url), source.url
    assert source.member is not None
    assert source.member.endswith("/testdata")
    assert re.fullmatch(r"[0-9a-f]{64}", UntraceTechniques.TREE_SHA256)


def test_a_tree_that_is_not_the_pinned_one_is_refused(tmp_path):
    suite = UntraceTechniques()
    suite.locate = lambda: tmp_path
    ready, reason = suite.available()
    assert not ready
    assert "digest" in reason


def test_the_provenance_no_longer_calls_it_a_technique_list():
    suite = UntraceTechniques()
    assert "technique list" not in suite.summary
    assert "operator-selected" not in suite.provenance.version
    assert "<TAB>" not in suite.provenance.notes
    assert 1204 in suite.provenance.issues


# --- the real corpus, when it is cached ------------------------------------


def _cached() -> Path:
    suite = UntraceTechniques()
    root = suite.locate()
    if root is None:
        pytest.skip("untrace is not cached")
    return root


def test_the_pinned_tree_still_matches_when_it_is_cached():
    assert tree_digest(_cached()) == UntraceTechniques.TREE_SHA256


def test_the_real_census_when_it_is_cached():
    """Counts that come from untrace's reports alone, so no build can move them."""
    suite = UntraceTechniques()
    suite.locate = _cached
    outcome = Outcome(suite=suite.name, family=suite.family, provenance=suite.provenance)
    suite.measure(outcome, None)
    assert _row(outcome, "cases")[0] == 64
    assert _row(outcome, "cases_left_out")[0] == 33
    assert _row(outcome, "files")[0] == 94
    assert _row(outcome, "files_without_verdict")[0] == 33
    assert _row(outcome, "has_anomalies_on_payload")[1] == 6
    assert _row(outcome, "has_anomalies_on_hidden")[1] == 20
    assert _row(outcome, "has_anomalies_on_mixed_script")[1] == 4
    assert _row(outcome, "has_anomalies_on_typographic")[1] == 8
    assert _row(outcome, "has_anomalies_on_clean")[1] == 23
    assert _row(outcome, "has_anomalies_on_payload")[0] == 6
    assert _row(outcome, "has_anomalies_on_clean")[0] == 0


# --- `U+200B` between digits ------------------------------------------------


def test_a_zero_width_space_between_digits_stays_clean_and_the_reducers_remove_it():
    """A decision, not an oversight (#1204): the neighbour rule reads letters."""
    text = "12" + ZWSP + "34"
    assert not disarm.has_anomalies(text)
    assert disarm.canonicalize(text) == "1234"
    assert not disarm.is_canonical(text)
    assert disarm.has_anomalies("ab" + ZWSP + "cd")
    assert disarm.has_anomalies("a1" + ZWSP + "2b")


def test_the_decision_on_digits_is_recorded():
    page = (REPO_ROOT / "docs/limitations.md").read_text(encoding="utf-8")
    assert "between two digits" in page
    guide = (REPO_ROOT / "docs/user-guide/anomaly-detection.md").read_text(encoding="utf-8")
    assert "between two digits" in guide
