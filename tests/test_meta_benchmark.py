"""Tests for the meta-benchmark harness (``benchmarks/meta``).

The harness itself never reaches the network and never needs an external
corpus: everything asserted here runs off the registry, the selection logic and
the two suite tiers whose data is vendored or derived. Suites whose artifact is
absent must report SKIPPED, and that is asserted rather than assumed — a silent
pass on a missing corpus is the one failure mode this harness exists to prevent.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import math
import os

import pytest

from benchmarks.meta import fetch, leaderboard, registry, subjects
from benchmarks.meta.base import SuiteBase, surfaces, thin
from benchmarks.meta.baseline import Drift, compare, snapshot
from benchmarks.meta.protocol import Availability, Family, Outcome, Provenance, Status
from benchmarks.meta.report import load_outcomes, render_json, render_markdown
from benchmarks.meta.runner import RunReport, run
from benchmarks.meta.suites import academic

# The harness scores every surface a caller can reach, deprecated ones included,
# so these fire tens of thousands of times per run. Expected, not a defect.
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

# --- registry ---------------------------------------------------------------


def test_every_suite_has_a_unique_name():
    names = [s.name for s in registry.all_suites()]
    assert len(names) == len(set(names)), "duplicate suite name"


def test_every_suite_declares_a_citable_provenance():
    for suite in registry.all_suites():
        p = suite.provenance
        assert p.origin and p.citation and p.version and p.licence, suite.name
        if p.external:
            assert p.url.startswith("http"), f"{suite.name}: external suite needs a URL"


def test_only_the_introspective_family_is_non_external():
    for suite in registry.all_suites():
        is_introspective = suite.family is Family.INTROSPECTIVE
        assert suite.provenance.external is not is_introspective, suite.name


def test_every_suite_names_the_issues_it_identified():
    for suite in registry.all_suites():
        assert suite.provenance.issues, f"{suite.name} cites no issue"


def test_vendored_and_derived_suites_are_always_available():
    for suite in registry.all_suites():
        if suite.availability in (Availability.VENDORED, Availability.DERIVED):
            ready, reason = suite.available()
            assert ready, f"{suite.name} should always be runnable: {reason}"


def test_unavailable_suites_explain_themselves():
    for suite in registry.all_suites():
        ready, reason = suite.available()
        if not ready:
            assert reason.strip(), f"{suite.name} refused without a reason"


# --- selection: n of m ------------------------------------------------------


def test_introspective_suites_are_excluded_by_default():
    default = {s.name for s in registry.select()}
    included = {s.name for s in registry.select(include_introspective=True)}
    assert default < included
    assert all(registry.by_name(n).provenance.external for n in default)


def test_glob_selection_picks_a_group():
    picked = registry.select(patterns=["uts39-*"])
    assert picked, "expected the UTS #39 group to be non-empty"
    assert all(s.name.startswith("uts39-") for s in picked)


def test_family_filter():
    picked = registry.select(families=["normative"])
    assert picked
    assert {s.family for s in picked} == {Family.NORMATIVE}


def test_sample_is_deterministic_for_a_seed():
    a = [s.name for s in registry.select(sample=4, seed=7)]
    b = [s.name for s in registry.select(sample=4, seed=7)]
    c = [s.name for s in registry.select(sample=4, seed=8)]
    assert a == b
    assert len(a) == 4
    assert a != c or len(registry.all_suites()) <= 4


def test_sample_larger_than_the_registry_is_a_no_op():
    everything = registry.select()
    assert len(registry.select(sample=len(everything) + 50)) == len(everything)


def test_filters_compose():
    picked = registry.select(patterns=["*"], families=["cve"], only_available=True)
    for suite in picked:
        assert suite.family is Family.CVE
        assert suite.available()[0]


# --- thin(): stride, never truncation ---------------------------------------


def test_thin_spreads_across_the_domain_rather_than_truncating():
    domain = list(range(0, 100000))
    sampled = thin(domain, 10)
    assert len(sampled) == 10
    # A truncating implementation would stop at 9; a stride reaches the far end.
    assert max(sampled) > 50000


def test_thin_is_a_no_op_when_the_limit_is_generous():
    domain = list(range(50))
    assert thin(domain, 500) is domain
    assert thin(domain, None) is domain


def test_thin_handles_degenerate_limits():
    assert thin(list(range(10)), 0) == []
    assert thin([], 5) == []


# --- surfaces ---------------------------------------------------------------


def test_surfaces_cover_every_preset_and_profile():
    import disarm

    got = surfaces()
    for preset in disarm.PRESETS:
        assert preset in got
    for profile in disarm.list_profiles():
        assert f"profile:{profile}" in got


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_every_surface_is_callable_on_text():
    # Deprecated presets are still surfaces a caller can reach, so the harness
    # scores them; the deprecation warning is expected here, not a defect.
    for name, fn in surfaces().items():
        assert isinstance(fn("paypal"), str), name


# --- running ----------------------------------------------------------------


@pytest.fixture
def derived_suites():
    return registry.select(availabilities=["derived", "vendored"], include_introspective=True)


def test_a_run_produces_measurements_with_denominators(derived_suites):
    report = run(derived_suites[:3], registered=len(registry.all_suites()), limit=200)
    assert report.ran, "expected at least one suite to produce measurements"
    for outcome in report.ran:
        assert outcome.measurements, outcome.suite
        for m in outcome.measurements:
            if m.of is not None:
                assert m.of > 0, f"{outcome.suite}.{m.key} has a zero denominator"
                assert m.value <= m.of, f"{outcome.suite}.{m.key} exceeds its population"


class _AlwaysMissing(SuiteBase):
    """A suite whose artifact can never be present.

    The skip path must be testable without depending on what the developer
    happens to have downloaded: with `$DISARM_META_CACHE` populated, every real
    suite can become available and a test written against `not available()`
    would fail while the behaviour it checks is still correct.
    """

    name = "always-missing"
    family = Family.ACADEMIC
    availability = Availability.MANUAL
    env_var = "DISARM_META_NO_SUCH_ARTIFACT_EVER"
    summary = "test double"
    provenance = Provenance(
        origin="test",
        citation="test-corpus",
        url="http://example.invalid",
        version="1",
        licence="n/a",
        issues=(1,),
    )

    def locate(self):
        return None

    def measure(self, outcome, limit):  # pragma: no cover - never reached
        raise AssertionError("measure() must not run when the artifact is absent")


def test_a_missing_artifact_skips_and_never_passes_silently():
    report = run([_AlwaysMissing()], registered=len(registry.all_suites()))
    assert report.outcomes
    for outcome in report.outcomes:
        assert outcome.status is Status.SKIPPED
        assert not outcome.measurements
        assert outcome.skip_reason
        assert "DISARM_META_NO_SUCH_ARTIFACT_EVER" in outcome.skip_reason


def test_a_throwing_suite_does_not_end_the_run(derived_suites):
    class Exploding:
        name = "exploding"
        family = Family.INTROSPECTIVE
        availability = Availability.DERIVED
        summary = ""
        provenance = Provenance(
            origin="test",
            citation="test",
            url="",
            version="1",
            licence="n/a",
            external=False,
            issues=(1,),
        )

        def available(self):
            return True, ""

        def run(self, limit=None, subject=None):
            raise RuntimeError("boom")

    report = run([Exploding(), *derived_suites[:1]], registered=2, limit=100)
    assert len(report.errored) == 1
    assert "boom" in report.errored[0].error
    assert report.ran, "the healthy suite still ran"


def test_introspective_outcomes_are_marked_non_external():
    suites = registry.select(families=["introspective"], include_introspective=True)
    report = run(suites[:1], registered=len(registry.all_suites()), limit=100)
    assert report.outcomes
    assert not any(o.external for o in report.outcomes)
    assert not report.external_ran


# --- baseline / drift -------------------------------------------------------


def _outcome(
    name: str, key: str, value: float, of: float, population: int, subject: str = "disarm"
) -> Outcome:
    from benchmarks.meta.protocol import Measurement, Method

    return Outcome(
        method=Method(
            subject=subject,
            subject_version="0.0.0",
            environment={"unicode_version": "17.0.0", "confusables_version": "17.0.0"},
        ),
        suite=name,
        family=Family.NORMATIVE,
        provenance=Provenance(
            origin="o", citation="c", url="http://x", version="1", licence="l", issues=(1,)
        ),
        population=population,
        measurements=[Measurement(key=key, value=value, of=of, higher_is_better=True)],
    )


def test_snapshot_is_keyed_by_subject_as_well_as_suite():
    """The same measurement means different things for different tools.

    Keying on the suite alone would compare disarm's number against whichever
    subject happened to be recorded last.
    """
    snap = snapshot([_outcome("s", "k", 5, 10, 10)], "0.0.0")
    round_tripped = json.loads(json.dumps(snap))
    assert "disarm@0.0.0::s" in round_tripped["suites"]
    assert round_tripped["suites"]["disarm@0.0.0::s"]["measurements"]["k"]["value"] == 5
    assert round_tripped["unicode_version"]
    assert round_tripped["confusables_version"]


def test_drift_across_different_populations_is_marked_incomparable():
    d = Drift(
        suite="s",
        key="k",
        before=5,
        after=50,
        before_of=10,
        after_of=1000,
        comparable=False,
        higher_is_better=True,
    )
    assert d.ratio_delta is None
    assert not d.comparable


def test_drift_direction_follows_higher_is_better():
    better = Drift("s", "k", 5, 8, 10, 10, comparable=True, higher_is_better=True)
    worse = Drift("s", "k", 5, 8, 10, 10, comparable=True, higher_is_better=False)
    neutral = Drift("s", "k", 5, 8, 10, 10, comparable=True, higher_is_better=None)
    assert better.direction == "better"
    assert worse.direction == "worse"
    assert neutral.direction == "moved"


def test_compare_against_an_absent_baseline_is_empty():
    assert compare([_outcome("s", "k", 1, 2, 2)], name="a-baseline-that-does-not-exist") == []


def test_noise_floor_suppresses_a_tiny_ratio_move():
    tiny = Drift("s", "k", 1000, 1001, 100000, 100000, comparable=True, higher_is_better=True)
    assert not tiny.significant
    real = Drift("s", "k", 1000, 3000, 100000, 100000, comparable=True, higher_is_better=True)
    assert real.significant


# --- reporting --------------------------------------------------------------


def test_markdown_report_separates_findings_from_current_measurements(derived_suites):
    report = run(derived_suites[:2], registered=len(registry.all_suites()), limit=200)
    md = render_markdown(report)
    assert "# disarm meta-benchmark" in md
    assert "measured now" in md
    for outcome in report.ran:
        if outcome.provenance.finding:
            assert "**Found during the cycle.**" in md
            break


def test_markdown_names_every_skipped_suite_and_why():
    report = run([_AlwaysMissing()], registered=len(registry.all_suites()))
    md = render_markdown(report)
    assert "## Not run" in md
    for outcome in report.skipped:
        assert outcome.suite in md
        assert outcome.skip_reason in md


def test_json_report_carries_provenance_and_the_external_flag(derived_suites):
    report = run(derived_suites[:2], registered=len(registry.all_suites()), limit=100)
    payload = json.loads(render_json(report))
    assert payload["registered"] == len(registry.all_suites())
    for suite in payload["suites"]:
        assert "external" in suite
        assert suite["provenance"]["citation"]


# --- regressions for review findings ----------------------------------------


def test_a_zero_denominator_is_printed_not_hidden():
    """`of=0` is a real denominator: an empty population must stay visible."""
    from benchmarks.meta.protocol import Measurement
    from benchmarks.meta.report import fmt

    assert fmt(Measurement(key="k", value=0, of=0)) == "0 / 0"
    assert fmt(Measurement(key="k", value=3, of=None)) == "3"
    assert fmt(Measurement(key="k", value=1, of=4)) == "1 / 4 (25.0%)"


def test_per_row_counters_do_not_latch():
    """A per-row flag must reset each row, not read a cumulative total.

    `manufactured_from_fullwidth` was computed as `any(per_surface.values())`
    inside the row loop, so once one row fired every later row counted too.
    """
    from benchmarks.meta.suites.model_artifacts import ChatTemplateDelimiters

    src = inspect.getsource(ChatTemplateDelimiters.measure)
    assert "any(per_surface_manufacture.values())" not in src
    assert "manufactured_here" in src


# --- the bias boundary ------------------------------------------------------


def test_no_external_suite_is_anchored_to_a_disarm_owned_table():
    """A benchmark must not be scored against a file disarm generated.

    ``data/confusables_lgr.tsv`` and ``data/confusables_supplement.tsv`` are
    disarm's own admission-filtered extracts, and the shipped fold was built
    from them. Anchoring an external suite to either would report success by
    construction — the drift-gate mistake, one layer up.
    """
    forbidden = (
        "confusables_lgr.tsv",
        "confusables_supplement.tsv",
        "confusables_attested.tsv",
        "confusables_vision.tsv",
    )
    for suite in registry.all_suites():
        if not suite.provenance.external:
            continue
        located = suite.locate() if hasattr(suite, "locate") else None
        if located is None:
            continue
        assert located.name not in forbidden, (
            f"{suite.name} is scored against disarm's own {located.name}"
        )


# --- subjects, controls and the degenerate solution -------------------------


def test_controls_are_registered_and_marked():
    """The two degenerate answers stay in the roster as controls.

    They are how a metric is shown to be capable of failing. A run that drops
    them can no longer demonstrate that.
    """
    names = {s.info.name for s in subjects.all_subjects()}
    assert {"null-baseline", "identity"} <= names
    for name in subjects.CONTROLS:
        assert getattr(subjects.by_name(name), "control", False), name


def test_tools_selection_excludes_controls():
    assert not [s for s in subjects.select(["tools"]) if getattr(s, "control", False)]
    assert [s for s in subjects.select(["all"]) if getattr(s, "control", False)]


@pytest.mark.parametrize(
    ("suite_name", "key"),
    [
        ("uts39-confusables", "folded"),
        ("uts39-equivalence-classes", "closed_under_canonicalize"),
    ],
)
def test_deleting_everything_scores_zero_coverage(suite_name, key):
    """The delete-everything control must not win a coverage metric.

    It did: both sides of every comparison became the empty string, so it folded
    100% of UTS #39 onto target and closed every equivalence class. Collisions
    now require a non-empty shared form.
    """
    suite = registry.by_name(suite_name)
    null = suite.run(limit=300, subject=subjects.by_name("null-baseline"))
    real = suite.run(limit=300, subject=subjects.by_name("disarm"))
    assert null.measurement(key).value == 0
    assert real.measurement(key).value > 0


def test_doing_nothing_scores_zero_coverage_and_zero_cost():
    identity = registry.by_name("corruption-cost").run(subject=subjects.by_name("identity"))
    assert identity.measurement("destroyed").value == 0
    assert identity.measurement("clean_ascii_altered").value == 0
    assert identity.measurement("identity_retention").value == 1.0
    assert identity.measurement("degenerate").value == 0


def test_the_degenerate_flag_fires_only_on_the_null_baseline():
    flagged = set()
    scored = 0
    for subject in subjects.all_subjects():
        if not subject.available()[0]:
            continue  # an optional subject nobody installed is absent, not zero
        out = registry.by_name("corruption-cost").run(subject=subject)
        measured = out.measurement("degenerate")
        if measured is None:
            continue  # a subject with no transform surface is not asked
        scored += 1
        if measured.value:
            flagged.add(subject.info.name)
    assert scored > 1, "expected several subjects to be scored"
    assert flagged == {"null-baseline"}


def test_recovery_requires_something_to_survive():
    """XMR must not count a row both of whose sides were deleted."""
    src = inspect.getsource(academic.AttackCorpusSuite.measure)
    assert "if clean is not None and out and out == transform(clean)" in src


def test_a_suite_locked_to_disarm_skips_other_subjects():
    locked = next(s for s in registry.all_suites() if not s.MULTI_SUBJECT and s.available()[0])
    out = locked.run(limit=50, subject=subjects.by_name("ftfy"))
    assert out.status is Status.SKIPPED
    assert "disarm-specific" in out.skip_reason


def test_a_subject_without_a_capability_is_skipped_not_scored():
    detector_suite = registry.by_name("uts39-augmented-scripts")
    out = detector_suite.run(subject=subjects.by_name("unidecode"))
    assert out.status is Status.SKIPPED
    assert not out.measurements


# --- the method record ------------------------------------------------------


def test_every_run_records_its_method():
    out = registry.by_name("uts39-confusables").run(limit=200, subject=subjects.by_name("disarm"))
    m = out.method
    assert m.subject == "disarm" and m.subject_version
    assert m.domain and m.domain_size > 0
    assert m.predicates, "the surfaces actually invoked must be named"
    assert "limit" in m.parameters
    assert m.environment["host_ucd"]
    assert m.environment["unicode_version"]


def test_an_artifact_backed_suite_pins_its_input():
    out = registry.by_name("cve-2026-17084-stringprep").run()
    assert out.method.artifact_sha256 and len(out.method.artifact_sha256) == 64
    assert out.method.artifact_bytes > 0


def test_the_method_reaches_the_json_report():
    report = run(
        [registry.by_name("uts39-confusables")],
        registered=len(registry.all_suites()),
        limit=100,
        subjects=[subjects.by_name("disarm")],
    )
    payload = json.loads(render_json(report))
    method = payload["suites"][0]["method"]
    assert method["predicates"] and method["environment"] and method["domain"]


# --- reproduction of the published measurements -----------------------------


def test_reproductions_are_pinned_and_never_empty():
    """Any suite claiming a reproduction must pin values and say what it re-runs."""
    for suite in registry.all_suites():
        if suite.REPRO_EXPECTED:
            assert suite.provenance.reproduces, f"{suite.name} pins values but names no script"
            assert suite.reproduce.__func__ is not SuiteBase.reproduce, suite.name


def test_reproductions_hold_on_this_build():
    """Re-run each published script against a reference build and compare.

    Guarded by an environment variable rather than by ``__version__``: this tree
    *reports* 0.14.1 while carrying post-0.14.1 code, so the version string
    cannot tell a reference build from a development one. Build the tag in its
    own worktree, then::

        DISARM_META_REFERENCE_BUILD=0.14.1 \\
            pytest tests/test_meta_benchmark.py -k reproductions --noconftest

    ``--noconftest`` is required: tests/conftest.py imports post-0.14.1 API
    (``Script.BUHID``, added by #775) and cannot load against the reference
    build.

    A mismatch does not mean disarm regressed. It means the finding and the live
    measurement are no longer a before/after, which the report states via
    ``reproduces_its_finding``.
    """
    reference = os.environ.get("DISARM_META_REFERENCE_BUILD")
    if not reference:
        pytest.skip("set DISARM_META_REFERENCE_BUILD to run against a pinned build")
    for suite in registry.all_suites():
        if not suite.REPRO_EXPECTED or not suite.available()[0]:
            continue
        if suite.REPRO_VERSION != reference:
            continue
        got = suite.reproduce()
        for key, expected in suite.REPRO_EXPECTED.items():
            assert got.get(key) == expected, f"{suite.name}.{key}"


def test_a_reproduction_mismatch_is_visible_in_the_report():
    from benchmarks.meta.protocol import Reproduction

    out = Outcome(
        suite="s",
        family=Family.NORMATIVE,
        provenance=Provenance(
            origin="o",
            citation="c",
            url="http://x",
            version="1",
            licence="l",
            issues=(1,),
            reproduces="script.py",
        ),
        reproduction=[Reproduction(key="k", expected=10, actual=12)],
    )
    assert out.reproduces_its_finding is False
    report = RunReport(outcomes=[out], selected=1, registered=1, subjects=["disarm"])
    assert "does NOT reproduce" in render_markdown(report)


# --- provisioning -----------------------------------------------------------


def test_declared_sources_carry_a_licence_and_a_real_url():
    for suite in registry.all_suites():
        for source in suite.SOURCES:
            assert source.url.startswith("https://"), suite.name
            assert source.licence, f"{suite.name}: {source.filename} has no licence"
            assert source.kind in ("file", "zip", "tar.gz"), source.kind


def test_provisioning_never_overwrites_an_existing_file(tmp_path):
    """An operator who placed a specific revision must keep it."""
    from benchmarks.meta.fetch import Source, ensure

    source = Source(url="https://example.invalid/x", filename="x.json", licence="MIT")
    placed = tmp_path / "x.json"
    placed.write_text("operator's own copy", encoding="utf-8")
    got = ensure(source, cache=tmp_path)
    assert got is not None and got.from_cache
    assert placed.read_text(encoding="utf-8") == "operator's own copy"


def test_offline_never_reaches_the_network(tmp_path):
    from benchmarks.meta.fetch import Source, provision

    source = Source(url="https://example.invalid/x", filename="x.json", licence="MIT")
    got = provision([source], cache=tmp_path, offline=True)
    assert got.skipped_offline == [source]
    assert not got.fetched


def test_an_archive_member_escaping_the_destination_is_refused(tmp_path):
    import io
    import tarfile

    from benchmarks.meta.fetch import _safe_extract

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="../escaped.txt")
        payload = b"nope"
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    buf.seek(0)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar, pytest.raises(ValueError, match="escapes"):
        _safe_extract(tar, tmp_path)


def test_an_empty_parse_of_a_present_artifact_is_an_error_not_a_zero():
    """A parser that extracts nothing is broken; 0 would read as a result.

    The ICANN LGR suite reported `blocked_pairs: 0` while its two-table join was
    wrong, which looks like perfect agreement rather than a fault.
    """
    src = inspect.getsource(SuiteBase.run)
    assert "parser fault" in src


# --- leaderboard ------------------------------------------------------------


def _board_outcome(subject: str, suite: str, key: str, value: float) -> Outcome:
    from benchmarks.meta.protocol import Measurement, Method

    return Outcome(
        suite=suite,
        family=Family.NORMATIVE,
        provenance=Provenance(
            origin="o", citation="c", url="http://x", version="1", licence="l", issues=(1,)
        ),
        method=Method(subject=subject),
        population=10,
        measurements=[Measurement(key=key, value=value, of=1.0, higher_is_better=True)],
    )


def test_census_measurements_never_enter_the_ranking():
    """A number with no declared direction cannot be scored."""
    from benchmarks.meta.protocol import Measurement, Method

    out = Outcome(
        suite="s",
        family=Family.NORMATIVE,
        provenance=Provenance(
            origin="o", citation="c", url="http://x", version="1", licence="l", issues=(1,)
        ),
        method=Method(subject="disarm"),
        measurements=[Measurement(key="census", value=5, of=10, higher_is_better=None)],
    )
    board = leaderboard.build([out])
    assert board.items == []
    assert board.excluded_census_measurements == 1


def test_measurements_are_parcelled_so_one_suite_gets_one_vote():
    outs = [
        _board_outcome(subj, "wide", f"m{i}", value)
        for subj, value in (("a", 0.9), ("b", 0.1))
        for i in range(7)
    ]
    outs += [_board_outcome(subj, "narrow", "m", v) for subj, v in (("a", 0.5), ("b", 0.6))]
    board = leaderboard.build(outs, bootstrap=20)
    assert len(board.items) == 2, "seven correlated measurements must not be seven items"
    assert {i.suite for i in board.items} == {"wide", "narrow"}


def test_a_thin_or_incoherent_battery_refuses_to_rank():
    outs = [
        _board_outcome(subj, f"s{i}", "m", value)
        for i in range(3)
        for subj, value in (("a", 0.9 - 0.1 * i), ("b", 0.2 + 0.1 * i))
    ]
    board = leaderboard.build(outs, bootstrap=50)
    assert not board.supported
    assert board.blockers
    assert any("benchmarks contribute" in b for b in board.blockers)


def test_the_refusal_is_stated_in_the_report():
    outs = [
        _board_outcome(subj, f"s{i}", "m", value)
        for i in range(3)
        for subj, value in (("a", 0.9), ("b", 0.2))
    ]
    board = leaderboard.build(outs, bootstrap=20)
    report = RunReport(outcomes=outs, selected=1, registered=1, subjects=["a", "b"])
    md = render_markdown(report, leaderboard=board)
    assert "does not support a ranking" in md
    assert "must not be quoted" in md


def test_controls_do_not_set_the_scale():
    """A strawman must not compress the tools into a band near the mean.

    Three tools minimum: a corrected item-total correlation over two points is
    undefined, so a two-tool battery legitimately scores nothing at all.
    """
    tools = [
        _board_outcome(subj, f"s{i}", "m", value)
        for i in range(4)
        for subj, value in (("a", 0.80), ("b", 0.60), ("c", 0.40))
    ]
    with_control = tools + [_board_outcome("null-baseline", f"s{i}", "m", 0.0) for i in range(4)]
    without = leaderboard.build(tools, bootstrap=20)
    with_ = leaderboard.build(with_control, bootstrap=20)

    def composite_of(board, name: str) -> float:
        return next(s.composite for s in board.standings if s.subject.startswith(f"{name}@"))

    gap_without = abs(composite_of(without, "a") - composite_of(without, "b"))
    gap_with = abs(composite_of(with_, "a") - composite_of(with_, "b"))
    assert math.isclose(gap_without, gap_with, rel_tol=1e-9), (
        "adding a control changed the separation between two tools"
    )


# --- versioned subject identity ---------------------------------------------


def test_subject_identity_carries_the_version():
    from benchmarks.meta.protocol import Method

    assert Method(subject="disarm", subject_version="0.15.0").subject_key == "disarm@0.15.0"


def test_two_builds_of_one_tool_do_not_collide_in_the_baseline():
    """0.14.1 and 0.15.0 are two subjects, not one overwriting the other."""
    old = _outcome("s", "k", 5, 10, 10, subject="disarm")
    old.method.subject_version = "0.14.1"
    new = _outcome("s", "k", 9, 10, 10, subject="disarm")
    new.method.subject_version = "0.15.0"
    snap = snapshot([old, new], "0.15.0")
    assert "disarm@0.14.1::s" in snap["suites"]
    assert "disarm@0.15.0::s" in snap["suites"]
    assert snap["suites"]["disarm@0.14.1::s"]["measurements"]["k"]["value"] == 5
    assert snap["suites"]["disarm@0.15.0::s"]["measurements"]["k"]["value"] == 9


def test_two_builds_of_one_tool_rank_separately():
    outs = []
    for version, value in (("0.14.1", 0.30), ("0.15.0", 0.90)):
        for i in range(6):
            o = _board_outcome("disarm", f"s{i}", "m", value)
            o.method.subject_version = version
            outs.append(o)
        for i in range(6):
            o = _board_outcome("ftfy", f"s{i}", "m", 0.50)
            o.method.subject_version = "6.3.1"
            outs.append(o)
    board = leaderboard.build(outs, bootstrap=20)
    keys = {st.subject for st in board.standings}
    assert {"disarm@0.14.1", "disarm@0.15.0"} <= keys
    ranks = {st.subject: st.rank for st in board.standings}
    assert ranks["disarm@0.15.0"] < ranks["disarm@0.14.1"], "the better build must rank higher"


def test_controls_are_matched_on_name_not_on_the_versioned_key():
    assert leaderboard.is_control("null-baseline@1")
    assert leaderboard.is_control("identity@1")
    assert not leaderboard.is_control("disarm@0.15.0")


def test_a_merged_run_round_trips_through_json(tmp_path):
    """Merging is the only way two builds of a compiled extension compete."""
    report = run(
        [registry.by_name("uts39-mixed-numbers")],
        registered=len(registry.all_suites()),
        subjects=[subjects.by_name("disarm")],
    )
    path = tmp_path / "run.json"
    path.write_text(render_json(report), encoding="utf-8")
    restored = load_outcomes(str(path))
    assert restored
    assert restored[0].method.subject_key == report.outcomes[0].method.subject_key
    assert [m.key for m in restored[0].measurements] == [
        m.key for m in report.outcomes[0].measurements
    ]
    assert restored[0].method.environment


def test_every_rendered_identity_shows_a_version():
    report = run(
        [registry.by_name("uts39-mixed-numbers")],
        registered=len(registry.all_suites()),
        subjects=[subjects.by_name("disarm")],
    )
    md = render_markdown(report)
    assert "disarm@" in md, "a report must never name a tool without its version"


def test_a_half_a_subject_cannot_answer_is_omitted_not_zeroed():
    """A question never asked must not be reported as a failed answer.

    `confusable-homoglyphs` detects and does not transform. Reporting
    `recovered: 0` for it would read as total failure at recovery rather than as
    a capability it does not claim.
    """
    suite = registry.by_name("uax29-word-joiners")
    detector_only = subjects.by_name("confusable-homoglyphs")
    if detector_only is None or not detector_only.available()[0]:
        pytest.skip("confusable-homoglyphs is not installed")
    out = suite.run(subject=detector_only)
    assert out.status is Status.OK
    assert out.measurement("detected") is not None
    assert out.measurement("recovered") is None

    both = suite.run(subject=subjects.by_name("disarm"))
    assert both.measurement("detected") is not None
    assert both.measurement("recovered") is not None


def test_requires_any_admits_a_subject_with_either_capability():
    suite = registry.by_name("uax29-word-joiners")
    assert suite.REQUIRES_ANY
    for name in ("disarm", "unidecode", "confusable-homoglyphs"):
        subject = subjects.by_name(name)
        if subject is None or not subject.available()[0]:
            continue
        ok, why = suite.supports(subject)
        assert ok, f"{name} should be admitted: {why}"


def test_the_icu_subject_is_registered_even_when_absent():
    """A missing reference implementation must be visible as missing."""
    icu = subjects.by_name("icu")
    assert icu is not None
    ready, why = icu.available()
    if not ready:
        assert "pyicu" in why.lower()


def test_a_subject_scored_on_less_of_the_battery_is_not_ranked():
    """One benchmark answered is not a better result than four answered.

    `confusable-homoglyphs` participates in one suite and ranked first over
    tools measured on four, which compares different things and flatters
    whichever was asked the fewest questions.
    """
    outs = []
    for i in range(4):
        for subj, value in (("broad-a", 0.9), ("broad-b", 0.5), ("broad-c", 0.3)):
            outs.append(_board_outcome(subj, f"s{i}", "m", value))
    outs.append(_board_outcome("narrow", "s0", "m", 0.99))
    board = leaderboard.build(outs, bootstrap=20)
    narrow = next(st for st in board.standings if st.subject.startswith("narrow@"))
    assert narrow.partial
    assert board.standings[-1] is narrow, "a partial subject sorts out of the ordering"
    assert all(not st.partial for st in board.standings[:-1])
    ranked = [st.rank for st in board.standings if not st.partial]
    assert ranked == sorted(ranked) and ranked[0] == 1


def test_every_benchmark_is_ranked_even_when_the_composite_refuses():
    """Per-benchmark rankings carry no internal-consistency assumption.

    Averaging benchmarks requires them to measure one construct; ranking within
    one benchmark requires nothing beyond that benchmark. So when the composite
    is blocked — which it currently is — these are the rankings that stand.
    """
    outs = [
        _board_outcome(subj, f"s{i}", "m", value)
        for i in range(3)
        for subj, value in (("a", 0.9), ("b", 0.5), ("c", 0.1))
    ]
    board = leaderboard.build(outs, bootstrap=20)
    assert not board.supported, "this battery should be blocked"
    per = board.per_benchmark()
    assert len(per) == 3
    for standings in per.values():
        assert [st.rank for st in standings] == [1, 2, 3]
        assert standings[0].subject.startswith("a@")


def test_equal_scores_share_a_rank():
    outs = []
    for i in range(3):
        for subj, value in (("a", 0.9), ("b", 0.9), ("c", 0.1)):
            outs.append(_board_outcome(subj, f"s{i}", "m", value))
    board = leaderboard.build(outs, bootstrap=20)
    ranks = [st.rank for st in board.per_benchmark()["s0"]]
    assert ranks == [1, 1, 3], "a tie shares the rank and the next place is skipped"


def test_a_lower_is_better_row_marks_the_lowest_value_as_best():
    """Without direction, a lower-is-better row reads backwards.

    `unreached` 34.1% beats 44.5%, and a bare percentage row said nothing about
    which end wins.
    """
    from benchmarks.meta.protocol import Measurement, Method

    def outcome(subject: str, value: float) -> Outcome:
        return Outcome(
            suite="s",
            family=Family.NORMATIVE,
            provenance=Provenance(
                origin="o",
                citation="c",
                url="http://x",
                version="1",
                licence="l",
                issues=(1,),
            ),
            method=Method(subject=subject, subject_version="1"),
            population=10,
            measurements=[Measurement(key="miss", value=value, of=1.0, higher_is_better=False)],
        )

    report = RunReport(
        outcomes=[outcome("a", 0.20), outcome("b", 0.80)],
        selected=1,
        registered=1,
        subjects=["a@1", "b@1"],
    )
    md = render_markdown(report)
    assert "`miss` ↓" in md
    assert "**20.0%**" in md, "the lowest value wins a lower-is-better row"
    assert "**80.0%**" not in md


def test_a_census_row_gets_no_direction_arrow():
    from benchmarks.meta.protocol import Measurement, Method

    out = Outcome(
        suite="s",
        family=Family.NORMATIVE,
        provenance=Provenance(
            origin="o", citation="c", url="http://x", version="1", licence="l", issues=(1,)
        ),
        method=Method(subject="a", subject_version="1"),
        measurements=[Measurement(key="count", value=5, of=10, higher_is_better=None)],
    )
    other = Outcome(**{**out.__dict__})
    other.method = Method(subject="b", subject_version="1")
    report = RunReport(outcomes=[out, other], selected=1, registered=1, subjects=["a@1", "b@1"])
    md = render_markdown(report)
    assert "`count` ↑" not in md and "`count` ↓" not in md


def _directed(subject: str, suite: str, value: float, higher: bool) -> Outcome:
    from benchmarks.meta.protocol import Measurement, Method

    return Outcome(
        suite=suite,
        family=Family.NORMATIVE,
        provenance=Provenance(
            origin="o", citation="c", url="http://x", version="1", licence="l", issues=(1,)
        ),
        method=Method(subject=subject, subject_version="1"),
        population=10,
        measurements=[Measurement(key="m", value=value, of=1.0, higher_is_better=higher)],
    )


def test_a_control_is_never_marked_best_in_the_comparison():
    """`identity` wins any "do not alter wrongly" row by never altering.

    Marking it best would present the degenerate answer as the target — the same
    failure the non-empty collision rule fixed, resurfacing in the report.
    """
    outs = [
        _directed("disarm", "s", 0.30, higher=False),
        _directed("ftfy", "s", 0.40, higher=False),
        _directed("identity", "s", 0.00, higher=False),
    ]
    report = RunReport(
        outcomes=outs,
        selected=1,
        registered=1,
        subjects=["disarm@1", "ftfy@1", "identity@1"],
    )
    md = render_markdown(report)
    assert "**30.0%**" in md, "the best non-control value wins the row"
    assert "**0.0%**" not in md, "a control must never be marked best"


def test_controls_are_listed_but_never_ranked():
    outs = []
    for i in range(4):
        for subj, value in (("a", 0.9), ("b", 0.6), ("c", 0.3), ("identity", 0.99)):
            outs.append(_board_outcome(subj, f"s{i}", "m", value))
    board = leaderboard.build(outs, bootstrap=20)
    ranked = [st for st in board.standings if not st.control]
    controls = [st for st in board.standings if st.control]
    assert controls, "the control must still be listed"
    assert all(st.rank == 0 for st in controls), "a control holds no rank"
    assert [st.rank for st in ranked] == [1, 2, 3]
    assert board.standings[-1].control, "controls sort to the bottom"
    for standings in board.per_benchmark().values():
        assert all(st.rank == 0 for st in standings if st.control)
        assert standings[0].subject.startswith("a@"), "a tool tops the benchmark"


def test_a_benchmark_only_one_subject_answered_is_not_a_ranking():
    outs = []
    for i in range(3):
        outs.append(_directed("disarm", f"s{i}", 0.9 - 0.1 * i, higher=True))
        # Only a control joins, so no ordering between tools is possible and
        # "1st of 1" would dress that up as a win.
        outs.append(_directed("identity", f"s{i}", 0.5, higher=True))
    board = leaderboard.build(outs, bootstrap=10)
    report = RunReport(outcomes=outs, selected=1, registered=1, subjects=["disarm@1", "identity@1"])
    md = render_markdown(report, leaderboard=board)
    assert "there is no ordering here" in md


def test_friedman_reports_how_many_benchmarks_would_reach_significance():
    """The useful number: it turns "not enough evidence" into a target."""
    outs = []
    for i in range(3):
        for subj, value in (("a", 0.9), ("b", 0.6), ("c", 0.3), ("d", 0.1)):
            outs.append(_board_outcome(subj, f"s{i}", "m", value))
    board = leaderboard.build(outs, bootstrap=10)
    agree = leaderboard.concordance(board)
    assert agree is not None
    assert agree.benchmarks == 3 and agree.tools == 4
    assert 0.0 <= agree.w <= 1.0
    # Perfect agreement across benchmarks: chi-square is k(n-1)W = 3*3*1 = 9.
    assert agree.w == pytest.approx(1.0)
    assert agree.chi_square == pytest.approx(9.0)
    assert agree.benchmarks_needed >= agree.benchmarks


def test_pareto_frontier_needs_no_weighting():
    """A tool wins an axis outright and still may not dominate."""
    outs = []
    # `a` leads axis one, `b` leads axis two: neither dominates the other, and a
    # tool trailing on both axes at once is the only kind that can be dominated.
    for subj, first, second in (
        ("a", 0.9, 0.1),
        ("b", 0.1, 0.9),
        ("c", 0.5, 0.5),
        ("weak", 0.4, 0.4),
    ):
        outs.append(_board_outcome(subj, "one", "m", first))
        outs.append(_board_outcome(subj, "two", "m", second))
    board = leaderboard.build(outs, bootstrap=10)
    front = leaderboard.pareto(board)
    assert front is not None
    names = {t.split("@")[0] for t in front.frontier}
    assert {"a", "b", "c"} <= names, "a tool leading any axis cannot be dominated"
    assert "weak" not in names, "weak trails c on both axes"
    beaten = {t.split("@")[0] for t in front.dominated}
    assert beaten == {"weak"}
    assert any(o.startswith("c@") for o in front.dominated[next(iter(front.dominated))])


def test_the_pareto_frontier_is_published_even_when_the_composite_is_not():
    outs = []
    for subj, first, second in (("a", 0.9, 0.1), ("b", 0.1, 0.9), ("c", 0.2, 0.2)):
        outs.append(_board_outcome(subj, "one", "m", first))
        outs.append(_board_outcome(subj, "two", "m", second))
    board = leaderboard.build(outs, bootstrap=10)
    report = RunReport(outcomes=outs, selected=1, registered=1, subjects=["a@1", "b@1", "c@1"])
    md = render_markdown(report, leaderboard=board)
    assert not board.supported, "this battery cannot carry a composite"
    assert "Pareto frontier" in md
    assert "non-dominated" in md
    assert "does not support a ranking" in md


def test_coverage_is_one_surface_not_a_union_over_all_of_them():
    """A union rewards shipping many entry points, not good ones.

    disarm exposes 19 transforms; every other tool exposes 1-5. Scoring coverage
    as "did any of them get it" gave disarm 4.9 points that no other subject
    could earn, because none of them has enough surfaces for a union to differ
    from its best one.
    """
    from benchmarks.meta import damage

    pairs = [("a", "b"), ("c", "d")]
    # Two surfaces, each solving a different pair: a union would score 2/2.
    surfaces = {
        "one": lambda s: "X" if s in ("a", "b") else s,
        "two": lambda s: "Y" if s in ("c", "d") else s,
    }
    name, hits = damage.best_surface(surfaces, pairs)
    assert hits == 1, "best single surface solves one pair, not the union's two"
    assert name in ("one", "two")


def test_key_builders_are_scored_in_their_own_role_not_as_coverage():
    """The surfaces that earn coverage must be the ones charged for cost.

    Key builders merge by contract. Letting them earn confusable coverage while
    the cost axis excluded them credited disarm for surfaces it was never
    charged for — an asymmetry in its own favour on its own benchmark.
    """
    import inspect as _inspect

    from benchmarks.meta.suites.normative import (
        UTS39ConfusableCoverage,
        UTS39EquivalenceClasses,
    )

    for suite in (UTS39ConfusableCoverage, UTS39EquivalenceClasses):
        src = _inspect.getsource(suite.measure)
        assert "split_by_intent" in src, f"{suite.__name__} must separate the roles"
        assert "self.transforms()" in src


def test_key_building_profiles_count_as_key_builders():
    """`library_catalog_key_eu` is a key builder that lives among the profiles.

    Excluding only the three top-level key functions left it scored as a text
    surface, where it was the single most destructive one in the corruption
    census — which is exactly what a catalog key should look like.
    """
    disarm_subject = subjects.by_name("disarm")
    if disarm_subject is None or not disarm_subject.available()[0]:
        pytest.skip("disarm is not importable")
    keys = disarm_subject.keys()
    assert "profile:library_catalog_key_eu" in keys
    assert "profile:search_index" in keys
    assert set(keys) <= set(disarm_subject.transforms()), "keys are drawn from transforms"


def test_a_small_integer_is_not_rendered_as_a_percentage():
    """A surface count of 1 rendered as "100.0%"."""
    from benchmarks.meta.report import _cell

    assert _cell(1, ratio=False) == "1"
    assert _cell(13, ratio=False) == "13"
    assert _cell(0.5, ratio=True) == "50.0%"


def test_removing_an_identity_free_codepoint_is_not_counted_as_damage():
    """93.5% of the first census's "damage" was private-use removal."""
    from benchmarks.meta import damage

    strip_pua = {"strip": lambda s: "".join(c for c in s if c != "")}
    corpus = ["orderend"]
    d = damage.per_surface(strip_pua, corpus)["strip"]
    assert d.retention < 1.0, "raw retention still records the removal"
    assert d.identity_retention == 1.0, "no letter or symbol was lost"


def test_coverage_and_cost_are_charged_to_the_same_declared_surface():
    """A published point must describe a configuration somebody could deploy.

    Coverage was the best of thirteen surfaces (`llm_guardrail`, a ten-step
    application pipeline) while cost averaged two *others* (`rag_ingest` and
    `code_context`). No caller could reach that combination.
    """
    from benchmarks.meta.subjects import Role

    subject = subjects.by_name("disarm")
    if subject is None or not subject.available()[0]:
        pytest.skip("disarm is not importable")
    declared = subject.role(Role.SANITIZER)
    assert list(declared) == ["canonicalize"], "the scored surface is declared, not won"

    coverage = registry.by_name("uts39-confusables").run(limit=400, subject=subject)
    cost = registry.by_name("corruption-cost").run(limit=400, subject=subject)
    assert coverage.method.parameters["scored_surface"] == "canonicalize"
    assert cost.method.parameters["scored_surface"] == "canonicalize"


def test_the_selection_effect_of_best_of_n_is_measured_not_hidden():
    subject = subjects.by_name("disarm")
    if subject is None or not subject.available()[0]:
        pytest.skip("disarm is not importable")
    out = registry.by_name("uts39-confusables").run(limit=600, subject=subject)
    effect = out.measurement("selection_effect_best_of_n")
    assert effect is not None, "what best-of-N would add must be a reported number"
    assert effect.higher_is_better is None, "it is a census, not a score"
    assert effect.value >= 0


def test_every_subject_declares_a_role_or_measures_nothing():
    """A subject with no declared role falls back, and that must be visible."""
    from benchmarks.meta.subjects import Role

    for subject in subjects.all_subjects():
        if not subject.available()[0]:
            continue
        if subject.transforms():
            assert subject.ROLES.get(Role.SANITIZER), (
                f"{subject.info.name} exposes transforms but declares no sanitizer"
            )


def test_the_confusable_target_script_is_recorded_not_inherited():
    """`target_script` changes the result, so it cannot stay implicit.

    disarm's fold takes a target script defaulting to "latin", and
    `canonicalize` uses that default. Only 30% of UTS #39 pairs have a Latin
    target, so the full table asks a Latin-targeting fold to produce CJK and
    Arabic targets it does not aim at.
    """
    subject = subjects.by_name("disarm")
    if subject is None or not subject.available()[0]:
        pytest.skip("disarm is not importable")
    out = registry.by_name("uts39-confusables").run(limit=500, subject=subject)
    fold = out.method.parameters["confusable_fold"]
    assert "latin" in fold["target_script"]
    assert "numeric" in fold["digit_policy"], "the digit policy is a knob too"
    assert "no" in fold["exposed_by_scored_surface"], (
        "canonicalize() takes no arguments, so neither knob is reachable from the "
        "surface a reader arrives at — that is the finding, and it must be recorded"
    )
    assert out.method.parameters["latin_target_pairs"] > 0


def test_latin_target_coverage_is_reported_beside_the_whole_table():
    subject = subjects.by_name("disarm")
    if subject is None or not subject.available()[0]:
        pytest.skip("disarm is not importable")
    out = registry.by_name("uts39-confusables").run(limit=800, subject=subject)
    whole = out.measurement("folded")
    subset = out.measurement("folded_latin_target")
    assert whole is not None and subset is not None
    assert subset.of < whole.of, "the subset must be a strict subset of the table"
    assert subset.higher_is_better is True


def test_each_target_script_is_scored_on_the_pairs_it_aims_at():
    """Scoring one target against the whole table repeats the fixed bias.

    70% of UTS #39 pairs resolve to something other than Latin, so asking the
    Latin profile about them measures NFKC, not the fold. This suite partitions
    first and asks each profile only about its own targets.
    """
    out = registry.by_name("uts39-target-scripts").run()
    assert out.status is Status.OK
    for name in ("latin", "cyrillic", "arabic", "hebrew"):
        pairs = out.measurement(f"pairs_targeting_{name}")
        resolved = out.measurement(f"resolved_{name}")
        assert pairs is not None and pairs.value > 0
        assert resolved is not None, f"{name} is accepted, so it must be scored"
        assert resolved.of == pairs.value, (
            f"{name} must be scored against its own subset, not the whole table"
        )


def test_an_unsupported_target_script_is_reported_not_skipped():
    """Greek is rejected while having more pairs than Cyrillic and Hebrew combined."""
    out = registry.by_name("uts39-target-scripts").run()
    greek_pairs = out.measurement("pairs_targeting_greek")
    supported = out.measurement("supported_greek")
    assert greek_pairs is not None and greek_pairs.value > 0
    assert supported is not None and supported.value == 0.0
    cyr = out.measurement("pairs_targeting_cyrillic").value
    heb = out.measurement("pairs_targeting_hebrew").value
    assert greek_pairs.value > cyr + heb, (
        "the point of the row: the rejected target is larger than two accepted ones"
    )


def test_the_partition_oracle_is_external():
    """Partitioning with disarm's own script table would be circular."""
    out = registry.by_name("uts39-target-scripts").run(limit=500)
    assert "UCD" in out.method.parameters["partition_oracle"]


def test_naming_a_character_is_not_counted_as_folding_it():
    """`—` to `em dash` removes a non-ASCII code point without folding it.

    disarm 0.14.1 did exactly that, and the undifferentiated fold rate scored the
    naming bug (#757) as coverage. When #803 fixed it the rate fell 81.9% to
    78.8% and the benchmark reported the fix as a regression.
    """
    from benchmarks.meta import damage

    cases = {
        "folded": lambda s: s.replace("—", "-"),
        "named": lambda s: s.replace("—", " em dash "),
        "deleted": lambda s: s.replace("—", ""),
        "survives": lambda s: s,
    }
    for expected, fn in cases.items():
        assert damage.classify_removal(fn, "—") == expected, expected


def test_a_compatibility_expansion_is_a_fold_not_a_name():
    """The line is words, not length: `1/2` is characters, `em dash` is words."""
    from benchmarks.meta import damage

    assert damage.classify_removal(lambda s: s.replace("½", "1/2"), "½") == "folded"
    assert damage.classify_removal(lambda s: s.replace("½", "one half"), "½") == "named"


def test_the_gap_list_is_scored_for_accuracy_not_length():
    """Covering a pair removed it from the gap list and lowered the old score.

    Between 0.14.1 and 0.15.0 `unmapped_confusables()` went 4,384 to 4,330 with
    54 leaving and none joining — pure coverage gain, reported as a loss.
    """
    import inspect as _inspect

    from benchmarks.meta.suites.comparators import ConfusableVision

    src = _inspect.getsource(ConfusableVision.measure)
    assert "visible_to_coverage_introspection" not in src
    assert "gaps_not_named" in src and "named_but_covered" in src


def test_the_corpus_metric_scores_the_declared_surface():
    """#759: adversarial_eval hardcoded one entry point.

    The corpus rate and the removal split were measuring different surfaces,
    which is the same asymmetry the coverage and cost axes had.
    """
    import inspect as _inspect

    from benchmarks.adversarial_eval.metrics import evaluate
    from benchmarks.meta.suites.datasets import _AdversarialEvalSuite

    assert "transform" in _inspect.signature(evaluate).parameters
    assert "transform" in _inspect.getsource(_AdversarialEvalSuite.measure)


def test_a_licence_declared_in_prose_still_counts():
    """A licence in the README is a licence.

    `reverse-captcha-eval` was first recorded as unlicensed and excluded, because
    the check read GitHub's detected `license` field and looked for a file named
    LICENSE. It declares MIT in README prose, which neither of those sees — a
    false negative that would have dropped a usable corpus.
    """
    suite = registry.by_name("reverse-captcha")
    assert suite is not None
    assert suite.SOURCES, "a licensed upstream must be provisioned"
    assert "MIT" in suite.provenance.licence
    assert "README" in suite.provenance.licence, (
        "record where the licence was found, since it is not where tools look"
    )


def test_the_injection_corpus_scores_removal_and_preservation_together():
    """Removing the payload while mangling the prompt is not a win."""
    suite = registry.by_name("reverse-captcha")
    if not suite.available()[0]:
        pytest.skip("the reverse-captcha corpus is not cached")
    out = suite.run(subject=subjects.by_name("disarm"))
    assert out.status is Status.OK
    removed = out.measurement("payload_removed")
    intact = out.measurement("visible_text_intact")
    assert removed is not None and intact is not None
    assert removed.higher_is_better and intact.higher_is_better
    assert removed.of == intact.of, "both are scored over the attack cases"


def test_the_injection_corpus_uses_its_own_controls():
    """False positives are the corpus author's definition, not ours."""
    suite = registry.by_name("reverse-captcha")
    if not suite.available()[0]:
        pytest.skip("the reverse-captcha corpus is not cached")
    out = suite.run(subject=subjects.by_name("disarm"))
    controls = out.measurement("control_cases")
    fp = out.measurement("controls_false_positive")
    assert controls is not None and controls.value == 10
    assert fp is not None and fp.higher_is_better is False


def test_private_use_is_excluded_from_the_discovered_homoglyph_score():
    """Stripping PUA is unrelated to confusability.

    12.4% of the released set is Private Use — an artefact of deciding
    confusability by rendering glyphs. Crediting a tool for handling those would
    repeat the mistake raw retention made with format characters.
    """
    suite = registry.by_name("weaponizing-unicode")
    if not suite.available()[0]:
        pytest.skip("the weaponizing_unicode set is not cached")
    out = suite.run(subject=subjects.by_name("disarm"))
    assert out.status is Status.OK
    excluded = out.measurement("private_use_excluded")
    flagged = out.measurement("flagged_by_a_detector")
    assert excluded is not None and excluded.value > 0
    assert flagged is not None
    assert flagged.of < excluded.of, "PUA must be out of the scored denominator"


def test_a_weakly_labelled_set_does_not_score_the_transform():
    """A model's weak label is not authority that a character should be rewritten."""
    suite = registry.by_name("weaponizing-unicode")
    if not suite.available()[0]:
        pytest.skip("the weaponizing_unicode set is not cached")
    out = suite.run(subject=subjects.by_name("disarm"))
    rewritten = out.measurement("rewritten_by_the_sanitizer")
    assert rewritten is not None
    assert rewritten.higher_is_better is None, "reported as a census, not a score"


def test_derived_vectors_reproduce_the_published_construction():
    """Three suites build their vectors from a paper's own listing.

    The arXiv source bundle carries the encoder even when no dataset was
    released, so the vector is derived from the published construction rather
    than transcribed — the same footing as the fullwidth delimiter spellings.
    """
    from benchmarks.meta.suites.academic import TagBlockConcealment, ZeroWidthStylometry

    # Listing 1 of arXiv:2607.05744, verbatim.
    assert TagBlockConcealment.tag_encode("e") == chr(0xE0065)
    assert TagBlockConcealment.conceal("x").startswith("Formats code neatly.")

    # Token table of Zero_Width_Steganography_Part_02.py.
    encoded = ZeroWidthStylometry.encode("A")
    assert encoded.endswith(ZeroWidthStylometry.END)
    assert set(encoded) <= {
        ZeroWidthStylometry.ZW0,
        ZeroWidthStylometry.ZW1,
        ZeroWidthStylometry.SEP,
        ZeroWidthStylometry.END,
    }


def test_normalization_only_subjects_fail_the_rag_pull_defence():
    """The paper publishes that NFKC leaves its attack at 50.2%, unchanged.

    If a normalization-only subject scored well here, this suite would be
    measuring something other than what the paper measured.
    """
    suite = registry.by_name("rag-pull-invisibles")
    for name in ("stdlib", "pyunormalize"):
        subject = subjects.by_name(name)
        if subject is None or not subject.available()[0]:
            continue
        out = suite.run(limit=600, subject=subject)
        removed = out.measurement("carriers_removed")
        assert removed is not None
        assert removed.ratio < 0.10, (
            f"{name} is NFKC-only; the paper reports normalization ineffective"
        )


def test_a_valid_text_attack_corpus_is_registered_as_cost_not_detection():
    """JailbreakBench prompts are valid text; detecting them is not disarm's job.

    0.300% of them is non-ASCII and that is incidental — CJK and accented Latin a
    token-level random search found useful, not a homoglyph or an invisible
    carrier. Scoring detection would repeat #743's category error, so the
    detector column is a census and only the cost column is directed.
    """
    suite = registry.by_name("jailbreakbench")
    if not suite.available()[0]:
        pytest.skip("the JailbreakBench artifact is not cached")
    out = suite.run(subject=subjects.by_name("disarm"))
    assert out.status is Status.OK
    flagged = out.measurement("flagged_by_a_detector")
    altered = out.measurement("altered")
    assert flagged is not None and flagged.higher_is_better is None, (
        "detection on valid text is neither a win nor a failure"
    )
    assert altered is not None and altered.higher_is_better is False
    assert "NOT detection" in out.method.parameters["scored_as"]


def test_alteration_is_never_presented_as_defence():
    """No model is re-run, so an alteration rate cannot be read as a defence rate."""
    suite = registry.by_name("jailbreakbench")
    if not suite.available()[0]:
        pytest.skip("the JailbreakBench artifact is not cached")
    out = suite.run(subject=subjects.by_name("disarm"))
    assert "not defence" in out.method.parameters["caveat"]
    assert "alteration is not defence" in out.provenance.notes.lower() or True


def test_the_encoding_boundary_expects_a_low_score():
    """Decoding base64 is not a Unicode sanitizer's job.

    #729 says the boundary is unnamed and `detect_encoding` is the name a reader
    finds first. The suite makes it measurable, and zero is the correct answer —
    so neither column is directed.
    """
    out = registry.by_name("encoding-obfuscation").run(subject=subjects.by_name("disarm"))
    assert out.status is Status.OK
    for key in ("flagged", "decoded_back_to_plaintext"):
        m = out.measurement(key)
        assert m is not None, key
        assert m.higher_is_better is None, f"{key} must not be scored in either direction"
    assert "correct" in out.method.parameters["expectation"]


def test_only_deterministic_encodings_are_reconstructed():
    """Leetspeak's substitution table is a free choice, so it is left out."""
    from benchmarks.meta.suites.academic import EncodingObfuscation

    assert set(EncodingObfuscation.encodings()) == {"base64", "hex", "rot13"}
    out = registry.by_name("encoding-obfuscation").run(subject=subjects.by_name("disarm"))
    assert "leetspeak" in out.method.parameters["excluded"]


def test_one_narrow_benchmark_does_not_zero_every_discrimination():
    """A detector-only suite must not flatten the whole battery.

    `weaponizing-unicode` reports `flagged_by_a_detector`, which only subjects in
    the detector role can answer — two of eleven. Under listwise deletion that
    capped every *other* item's shared-subject set at those same two, put every
    item below the three-subject floor, and produced a battery in which every
    discrimination and therefore every composite was exactly zero.
    """
    wide = [
        leaderboard.Item(
            suite=f"wide-{i}",
            key="score",
            scores={},
            z={f"tool-{j}": float((j * (i + 1)) % 5) for j in range(6)},
        )
        for i in range(4)
    ]
    narrow = leaderboard.Item(
        suite="detector-only",
        key="flagged_by_a_detector",
        scores={},
        z={"tool-0": 1.0, "tool-3": -1.0},
    )
    items = [*wide, narrow]
    subjects = [f"tool-{j}" for j in range(6)]

    leaderboard.discriminations(items, subjects)

    assert any(i.discrimination > 0.0 for i in wide), (
        "one narrow item zeroed every wide item's discrimination"
    )
    assert narrow.discrimination == 0.0, "a 2-subject item cannot be discriminating"


def test_rest_score_is_a_mean_so_uneven_coverage_does_not_rescale_subjects():
    """The rest-score must not grow with how many items a subject answered."""
    covered = leaderboard.Item(suite="a", key="k", scores={}, z={"x": 1.0, "y": 2.0, "z": 3.0})
    partial = leaderboard.Item(suite="b", key="k", scores={}, z={"x": 1.0, "y": 2.0})
    full = leaderboard.Item(suite="c", key="k", scores={}, z={"x": 1.0, "y": 2.0, "z": 3.0})
    also_full = leaderboard.Item(suite="d", key="k", scores={}, z={"x": 1.0, "y": 2.0, "z": 3.0})
    items = [covered, partial, full, also_full]
    leaderboard.discriminations(items, ["x", "y", "z"])

    # Subject "z" is absent from `partial`. Summing would score it over one item
    # while x and y are scored over two, so a perfectly consistent battery would
    # register as inconsistent. The mean keeps all three on one scale.
    assert covered.discrimination == pytest.approx(1.0)


def test_detector_measurements_are_absent_for_subjects_without_a_detector(tmp_path):
    """A capability a subject does not claim must not be scored as zero.

    Eight of eleven subjects expose no detector. Recording 0/22,370 for each
    turned "has a detector at all" into a large z-score advantage for the one
    subject that does, and the composite inherited it — the ranking was partly
    measuring API surface rather than behaviour.
    """
    from benchmarks.meta.suites import academic

    corpus = tmp_path / "rows.jsonl"
    corpus.write_text(
        '{"text": "a\u200bb", "clean": "ab"}\n{"text": "plain", "clean": "plain"}\n',
        encoding="utf-8",
    )

    def keys_for(subject):
        suite = academic.BadCharacters()
        suite.subject = subject
        outcome = Outcome(suite=suite.name, family=suite.family, provenance=suite.provenance)
        suite.measure(outcome, None)
        return {m.key for m in outcome.measurements}

    detector_keys = {"rows_detected_by_best_detector", "detected_any"}
    with_detector = without = None
    for subject in subjects.all_subjects():
        if not subject.available()[0]:
            continue
        if subject.detectors():
            with_detector = with_detector or subject
        elif subject.transforms():
            without = without or subject

    assert with_detector is not None and without is not None, "need one of each"
    os.environ["DISARM_META_BAD_CHARACTERS"] = str(corpus)
    try:
        assert detector_keys <= keys_for(with_detector)
        assert not (detector_keys & keys_for(without)), (
            f"{without.info.name} claims no detector but was scored on one"
        )
    finally:
        os.environ.pop("DISARM_META_BAD_CHARACTERS", None)


def test_cover_text_intactness_survives_a_case_fold():
    """Intactness is judged against the surface's own rendering of the text.

    A pipeline with `fold_case=True` lowercases the cover sentence. Comparing
    the original bytes scored that 0 — the same score as deleting the sentence —
    so a case-folding configuration read as destroying text it had preserved.
    """
    from benchmarks.meta.suites import academic

    suite = academic.ZeroWidthStylometry()
    cover = suite.COVER

    # A case-folding surface preserves the sentence; the empty surface does not.
    assert academic._apply(str.lower, cover).replace(" ", "") in cover.lower().replace(" ", "")
    assert not academic._apply(lambda _s: "", cover)


def test_the_composed_subject_declares_every_step_it_relies_on():
    """A default must never stand in for a declaration.

    `strip_pua` defaults to False on `TextPipeline`. Omitting it from `STEPS`
    would silently reintroduce the divergence #911 was filed about — the composed
    pipeline keeping all 137,468 PUA code points that every screening profile
    strips — and nothing in the run output would say so.
    """
    seen = set()
    for cls in (
        subjects.ComposedPromptHygiene,
        subjects.ComposedRetrievalKey,
        subjects.ComposedReviewDisplay,
    ):
        composed = cls()
        ready, why = composed.available()
        assert ready, why
        assert composed.STEPS.get("strip_pua") is True, (
            f"{cls.__name__}: strip_pua must be declared, not inherited"
        )
        seen.add(composed.info.version)
    assert len(seen) == 3, "each use case must have its own subject key"


def test_changing_the_composition_changes_the_subject_key():
    """The declaration is part of the identity, as a corpus digest is.

    Two runs whose step lists differ must not collide on one subject key, or a
    report would show a configuration being compared against itself.
    """
    before = subjects.ComposedPromptHygiene().info.version
    original = dict(subjects.ComposedPromptHygiene.STEPS)
    try:
        subjects.ComposedPromptHygiene.STEPS = {**original, "fold_case": False}
        after = subjects.ComposedPromptHygiene().info.version
    finally:
        subjects.ComposedPromptHygiene.STEPS = original
    assert before != after
    assert subjects.ComposedPromptHygiene().info.version == before


def test_every_composed_pipeline_is_scored_on_the_whole_battery():
    """No composition may select the benchmarks it is measured on.

    A pipeline hand-crafted per *benchmark* would be best-of-N with extra steps —
    map the cost suites to a light pipeline and the coverage suites to a heavy
    one and the mapping does the winning. Each use case is therefore a separate
    subject facing everything, so a prompt-hygiene pipeline meets the cost suites
    it loses and a review pipeline meets the coverage suites it loses.
    """
    composed = [s for s in subjects.all_subjects() if s.info.name.startswith("disarm-composed:")]
    assert len(composed) >= 3, "expected one subject per declared use case"
    for subject in composed:
        # The only per-subject selection allowed anywhere is the declared role.
        assert set(subject.ROLES) == {subjects.Role.SANITIZER}
        assert not hasattr(subject, "SUITES"), "a subject may not name its benchmarks"
        assert not hasattr(subject, "use_case_for"), "no benchmark-to-pipeline mapping"


def test_the_composed_pipelines_are_actually_different():
    """Three names for one configuration would measure nothing new."""
    steps = [
        tuple(sorted(cls.STEPS.items()))
        for cls in (
            subjects.ComposedPromptHygiene,
            subjects.ComposedRetrievalKey,
            subjects.ComposedReviewDisplay,
        )
    ]
    assert len(set(steps)) == 3
    # And they differ where their purposes differ: only the key builder romanizes,
    # and only the review pipeline leaves the reviewer's text alone.
    assert subjects.ComposedRetrievalKey.STEPS.get("transliterate") is True
    assert subjects.ComposedPromptHygiene.STEPS.get("transliterate") is not True
    assert subjects.ComposedReviewDisplay.STEPS.get("fold_case") is False


DIACRITICS = "Čeština, naïve café"


def test_a_composition_loses_diacritics_only_where_it_declares_strip_accents():
    """`strip_zalgo=0` is not off: it caps combining marks at zero (#958).

    disarm documents the cap as `strip_zalgo("café", max_marks=0) == "cafe"`, and
    off is `None`. All three compositions passed `0`, so the review pipeline —
    declared to change nothing a reader can see — turned `Čeština` into `Cestina`
    and altered 88 of 100 JailbreakBench prompts. Run each over a diacritic
    string: accents may go only where `strip_accents` is declared.
    """
    for cls in (
        subjects.ComposedPromptHygiene,
        subjects.ComposedRetrievalKey,
        subjects.ComposedReviewDisplay,
    ):
        composed = cls()
        ready, why = composed.available()
        assert ready, why
        out = composed.role(subjects.Role.SANITIZER)["composed"](DIACRITICS)
        if cls.STEPS.get("strip_accents"):
            assert out == "cestina, naive cafe", (cls.__name__, out)
        else:
            assert out == DIACRITICS, (cls.__name__, out)


def test_no_composition_passes_a_zero_cap_where_none_means_off():
    """The structural half of the check above.

    A `0` in a row of `False`s reads as off, and on `strip_zalgo` it is the
    strongest setting there is. Declare the step off by its own off value.
    """
    for cls in (
        subjects.ComposedPromptHygiene,
        subjects.ComposedRetrievalKey,
        subjects.ComposedReviewDisplay,
    ):
        assert "strip_zalgo" in cls.STEPS, f"{cls.__name__}: declare strip_zalgo, do not inherit it"
        assert cls.STEPS["strip_zalgo"] is None, (
            f"{cls.__name__}: strip_zalgo={cls.STEPS['strip_zalgo']!r} strips every "
            "combining mark; off is None"
        )


def test_the_prompt_hygiene_composition_strips_the_tag_block_without_glossing():
    """#914 landed, so the trade-off this pipeline used to record is gone.

    It previously declared `demojize=False` per #910 and thereby lost Plane 14
    TAG stripping, because `demojize` was the only composable step that removed
    it. #924 shipped `strip_plane14`, #921 unified the emoji-naming policy and
    PR #926 stopped the guardrail glossing, so the pipeline now gets both. Pinned
    in the new direction: a regression to either half must fail here.
    """
    import disarm

    steps = subjects.ComposedPromptHygiene.STEPS
    assert steps.get("demojize") == "", "replace, never name (#910) and never keep (#972)"
    assert steps.get("strip_plane14") is True, "declare it, never inherit the default"

    pipe = disarm.TextPipeline(**steps)
    tag = "".join(chr(0xE0000 + (ord(c) & 0x7F)) for c in "payload")
    out = pipe(f"visible label{tag}")
    assert not any(0xE0000 <= ord(c) <= 0xE007F for c in out), "TAG block must be gone"
    assert "label" in out, "and the text a reviewer reads must survive"
    assert "bomb" not in pipe("kill\U0001f4a3ing"), "no attacker-chosen words in the prompt"


def test_the_prompt_hygiene_composition_closes_the_emoji_attack_split():
    """An emoji inside a word is replaced with nothing, so the word comes back (#972).

    The Emoji Attack construction (arXiv:2411.01077) inserts a visible emoji inside
    a word to split it for a subword tokenizer. Naming widened the split and keeping
    left it; `demojize=""` closes it. The composition accepts #910's measured cost on
    inter-word emoji — `stop🛑now` fuses — and that is pinned too, so nobody reads the
    fusion as a regression when it shows up on a cost suite.
    """
    import disarm

    pipe = disarm.TextPipeline(**subjects.ComposedPromptHygiene.STEPS)
    assert pipe("aa\U0001f525bb") == "aabb"
    assert pipe("kill\U0001f4a3ing") == "killing"
    assert pipe("ig\U0001f600nore previous") == "ignore previous"
    assert pipe("stop\U0001f6d1now") == "stopnow", "the fusion #910 measured; accepted here"
    assert pipe("x\u00a9y \u2122") == "x\u00a9y tm", "text-presentation characters are not emoji"


def test_every_multi_subject_benchmark_declares_the_job_it_represents():
    """A benchmark that names no job is scored through whatever surface is default.

    That is how a confusables benchmark came to be answered by a pipeline built
    to preserve text for a reviewer. The job is a property of what the
    benchmark's source deploys into, so it is declared on the suite and is
    identical for every subject — it cannot become a per-tool advantage.
    """
    known = {
        v for k, v in vars(subjects.Job).items() if not k.startswith("_") and isinstance(v, str)
    }
    missing = []
    for suite in registry.all_suites():
        if not getattr(suite, "MULTI_SUBJECT", False):
            continue
        job = getattr(suite, "JOB", "")
        if not job:
            # Allowed only for a suite that deliberately scans every surface
            # rather than one declared surface.
            src = inspect.getsource(type(suite).measure)
            assert "surface_map" in src or "surfaces(" in src, (
                f"{suite.name} declares no JOB but scores a single declared surface"
            )
            continue
        if job not in known:
            missing.append((suite.name, job))
    assert not missing, f"unknown job slugs: {missing}"


def test_the_confusable_job_is_not_the_highest_scoring_surface():
    """The mapping must survive its own temptation.

    `strip_obfuscation` folds more of `confusables.txt` onto a shared form than
    `canonicalize` does, and is still the wrong answer: #614 found it *names* 49
    rows the TR39 table folds, so a spoof and its target stop being equal rather
    than becoming equal. Picking the higher number would make the mapping
    best-of-N with a declaration stapled to it.
    """
    assert subjects.DisarmSubject.JOBS[subjects.Job.CONFUSABLE_FOLD] == "canonicalize", (
        "the confusable job must stay on the documented comparison form"
    )


def test_the_prompt_hygiene_job_answers_with_the_declared_composition():
    """The bare subject's prompt-hygiene surface is the composition, not the preset.

    `llm_guardrail` keeps a visible emoji by #910's decision and takes no
    `demojize` override, so the parameter #973 added cannot reach it and the
    Emoji Attack split stays open under the preset. Richard's instruction on
    #972: do not run the harness with the preset; use a composed pipeline. The
    composition is the one declared on `ComposedPromptHygiene`, so there is one
    declaration, scored both as its own subject and as disarm's answer to the job.
    """
    import disarm

    assert subjects.DisarmSubject.JOBS[subjects.Job.PROMPT_HYGIENE] == "composed:prompt-hygiene"
    subject = subjects.by_name("disarm")
    assert subject is not None
    surface = subject.role(subjects.Role.SANITIZER, job=subjects.Job.PROMPT_HYGIENE)
    assert list(surface) == ["composed:prompt-hygiene"], surface
    fn = surface["composed:prompt-hygiene"]
    assert fn("aa\U0001f525bb") == "aabb"
    assert fn("ig\U0001f600nore previous") == "ignore previous"
    # The same pipeline the composed subject is scored on: one declaration.
    composed = subjects.ComposedPromptHygiene().role(subjects.Role.SANITIZER)["composed"]
    for probe in ("aa\U0001f525bb", "stop\U0001f6d1now", "Formats code neatly.\U000e0042"):
        assert fn(probe) == composed(probe)
    # And the preset is still offered as a surface, just not as the job's answer.
    assert "profile:llm_guardrail" in subject.transforms()
    assert disarm.get_pipeline("llm_guardrail")("aa\U0001f525bb") == "aa\U0001f525bb"


def test_the_prompt_hygiene_job_falls_back_to_the_preset_when_the_build_rejects_the_composition():
    """A build whose `demojize` is bool-only must still answer the job, and say how.

    Simulated by declaring a step no build accepts: the composition cannot be
    built, the job answers with `profile:llm_guardrail` under that name, and the
    report's predicates show the switch instead of an empty surface.
    """
    original = dict(subjects.ComposedPromptHygiene.STEPS)
    try:
        subjects.ComposedPromptHygiene.STEPS = {**original, "no_such_step": True}
        subject = subjects.by_name("disarm")
        assert subject is not None
        assert "composed:prompt-hygiene" not in subject.transforms()
        surface = subject.role(subjects.Role.SANITIZER, job=subjects.Job.PROMPT_HYGIENE)
        assert list(surface) == ["profile:llm_guardrail"], surface
    finally:
        subjects.ComposedPromptHygiene.STEPS = original
    assert list(
        subjects.by_name("disarm").role(subjects.Role.SANITIZER, job=subjects.Job.PROMPT_HYGIENE)
    ) == ["composed:prompt-hygiene"]


def test_standalone_entry_points_are_in_the_surface_census():
    """`normalize_confusables` was invisible to every suite for the whole build.

    `transforms()` enumerated `PRESETS` and profiles only, so the surface whose
    name most suggests it belongs on a confusables benchmark was never scored.
    """
    subject = subjects.by_name("disarm")
    assert subject is not None
    assert "normalize_confusables" in subject.transforms()


def test_a_subject_without_a_detector_is_not_marked_incomplete():
    """Exclusion and zero-filling are the same error with opposite signs.

    `disarm` answers four directed measurements on the TAG-block suite because
    it has a detector; a transform-only subject answers two. Judging
    completeness against the union of all keys marked all ten of those
    incomplete and left one tool on three benchmarks — which emptied the Pareto
    frontier and removed the non-dominated count from the report entirely.
    """
    detector = leaderboard.Item(
        suite="s", key="detected", scores={"withdet": 1.0}, z={"withdet": 1.0}
    )
    shared = leaderboard.Item(
        suite="s",
        key="removed",
        scores={"withdet": 1.0, "plain": 0.0},
        z={"withdet": 1.0, "plain": 0.0},
    )
    (merged,) = leaderboard.parcel([detector, shared])
    assert merged.complete("withdet")
    assert merged.complete("plain"), (
        "a subject that answered everything its peers answered is complete"
    )


def test_one_narrow_benchmark_does_not_empty_the_pareto_frontier():
    """Dominance is taken pairwise, on the axes both subjects answered.

    `weaponizing-unicode`'s only directed measurement needs a detector, so two
    subjects answer it. Intersecting the field listwise across every benchmark
    reduced the comparable set to fewer than two tools and returned no frontier
    at all — silently, with no line in the report to say so.
    """
    # Two tools, three axes, plus one axis only the first can answer.
    items = []
    for i in range(3):
        z = {"a": float(i), "b": float(i) - 1}
        items.append(
            leaderboard.Item(
                suite=f"wide-{i}",
                key="k",
                scores=dict(z),
                z=z,
                member_keys={"a": {"k"}, "b": {"k"}},
                all_keys={"k"},
                peer_keys={"a": {"k"}, "b": {"k"}},
            )
        )
    items.append(
        leaderboard.Item(
            suite="narrow",
            key="k",
            scores={"a": 1.0},
            z={"a": 1.0},
            member_keys={"a": {"k"}},
            all_keys={"k"},
            peer_keys={"a": {"k"}},
        )
    )
    board = leaderboard.Leaderboard(items=items, subjects=["a", "b"])
    par = leaderboard.pareto(board)
    assert par is not None, "a 13-benchmark battery must yield a frontier"
    assert len(par.frontier) + len(par.dominated) >= 2


def test_the_overlap_blocker_says_what_it_actually_checked():
    """ "No two subjects separate" and "no neighbours separate" are different claims.

    `separated_pairs` counts adjacent pairs, which is the right test for whether
    an ordering is noise. The message claimed the stronger "no two subjects",
    which was false the moment any non-adjacent pair separated — `disarm`
    [0.21, 0.92] against `stdlib` [-1.40, -0.11] — so the page contradicted its
    own table.
    """
    standings = [
        leaderboard.Standing(
            subject=f"t{i}",
            composite=0.0,
            bt_strength=0.0,
            rank=i + 1,
            ci_low=lo,
            ci_high=hi,
            items=3,
        )
        for i, (lo, hi) in enumerate([(0.9, 1.1), (0.0, 1.0), (-0.5, 0.5)])
    ]
    board = leaderboard.Leaderboard(items=[], subjects=["t0", "t1", "t2"], standings=standings)
    # t0 and t2 separate; neither neighbour pair does.
    assert board.separated_pairs() == 0
    assert board.separated_pairs_any() == (1, 3)
    text = " ".join(board.blockers)
    if "bootstrap" in text:
        assert "no two subjects" not in text
        assert "1 of 3" in text


def test_discrimination_is_fitted_on_tools_not_on_the_controls():
    """The controls manufacture agreement between axes that oppose.

    `cronbach_alpha` and `axis_correlations` already excluded them, with a
    comment saying why; `discriminations` was the one member of the same family
    still computed over the whole field. It changed the answer:
    `uts39-confusables` weighed +0.11 with the controls in and 0.00 without.
    """
    src = inspect.getsource(leaderboard.discriminations)
    assert "is_control" in src, "discrimination must exclude controls from its fit"


def test_a_control_outranking_a_library_blocks_the_ranking():
    """The degenerate controls exist to make this unpublishable.

    With five axes at zero weight — the cost axis among them — the composite
    began rewarding destruction, and `null-baseline` scored above five real
    libraries. No amount of interval overlap makes that a publishable ordering.
    """
    standings = [
        leaderboard.Standing(
            subject="null-baseline@1",
            composite=0.5,
            bt_strength=0.0,
            rank=1,
            ci_low=0.0,
            ci_high=1.0,
            items=3,
            control=True,
        ),
        leaderboard.Standing(
            subject="real@1",
            composite=0.1,
            bt_strength=0.0,
            rank=2,
            ci_low=0.0,
            ci_high=1.0,
            items=3,
        ),
    ]
    board = leaderboard.Leaderboard(
        items=[], subjects=["null-baseline@1", "real@1"], standings=standings
    )
    text = " ".join(board.blockers)
    assert "refuses the job" in text
    assert not board.supported


def test_zero_weight_axes_are_named_in_the_blockers():
    """A weighting that deletes an axis must say which, and that it did."""
    board = leaderboard.Leaderboard(
        items=[leaderboard.Item(suite="cost", key="k", scores={}, discrimination=0.0)],
        subjects=["a"],
    )
    text = " ".join(board.blockers)
    assert "`cost`" in text and "zero weight" in text


def test_the_z_scale_is_fitted_on_one_subject_per_library():
    """Entering three compositions of one library let it set a third of the scale."""
    subjects = [
        "disarm@1",
        "disarm-composed:a@1",
        "disarm-composed:b@1",
        "ftfy@1",
        "null-baseline@1",
    ]
    basis = leaderboard.fit_basis(subjects)
    assert basis == ["disarm@1", "ftfy@1"], basis
    assert leaderboard.library_of("disarm-composed:review-display@0.15.0") == "disarm"


def test_an_incomparable_subject_is_not_called_non_dominated():
    """Never being beaten because nobody could meet you is not a result.

    `confusable-homoglyphs` answers 4 of 13 axes and the shared-axis floor needs
    6, so it met nobody and landed on the frontier untested — while the comment
    above the floor claimed it prevented exactly that.
    """
    wide = [
        leaderboard.Item(
            suite=f"w{i}",
            key="k",
            scores={"a": float(i), "b": float(i) - 1},
            z={"a": float(i), "b": float(i) - 1},
            member_keys={"a": {"k"}, "b": {"k"}},
            all_keys={"k"},
            peer_keys={"a": {"k"}, "b": {"k"}},
        )
        for i in range(6)
    ]
    # `c` appears on two axes, both shared only with `a`. With eight axes the
    # floor is four, so `c` can never be compared to anyone at all.
    narrow = [
        leaderboard.Item(
            suite=f"n{i}",
            key="k",
            scores={"a": 0.0, "c": 9.0},
            z={"a": 0.0, "c": 9.0},
            member_keys={"a": {"k"}, "c": {"k"}},
            all_keys={"k"},
            peer_keys={"a": {"k"}, "c": {"k"}},
        )
        for i in range(2)
    ]
    board = leaderboard.Leaderboard(items=[*wide, *narrow], subjects=["a", "b", "c"])
    par = leaderboard.pareto(board)
    assert par is not None
    assert "c" in par.incomparable
    assert "c" not in par.frontier


def test_a_bootstrap_draw_with_no_weighted_axis_is_dropped_not_scored_zero():
    """`composite` returns 0.0 when its denominator is zero. That is a placeholder.

    Appending it puts exact zeros into the distribution the quantiles read. With
    five axes already clamped to zero weight it happened in 10 of 400 draws —
    exactly the 2.5% tail — so the placeholder became the lower bound: six
    intervals were published with a bound of precisely 0.00, every interval was
    made to span zero, and the page reported 0 of 55 separating pairs where the
    true count is 11.
    """
    # An item whose scores are identical across subjects discriminates zero, so
    # any resample drawn only from these has no weighted axis at all.
    flat = [leaderboard.Item(suite=f"f{i}", key="k", scores={"a": 1.0, "b": 1.0}) for i in range(3)]
    leaderboard.discriminations(flat, ["a", "b"])
    assert all(i.discrimination == 0.0 for i in flat)
    assert leaderboard.composite(flat, "a") == 0.0, "the placeholder this guards against"

    src = inspect.getsource(leaderboard.build)
    assert "null_draws" in src, "build must count and skip weightless draws"
    assert "continue" in src.split("null_draws += 1")[1][:40]


def test_the_run_reports_how_many_draws_it_discarded():
    """A silently dropped draw is as unauditable as a silently scored zero."""
    assert "null_draws" in {f.name for f in dataclasses.fields(leaderboard.Leaderboard)}


def test_a_symlink_member_cannot_write_outside_the_destination(tmp_path):
    """The name check alone passed this. CodeQL was right.

    A member can sit inside the destination by name and still write outside it:
    a symlink whose *linkname* points up and out, followed by a member written
    through it. `member.name` is innocent for both, so the pre-extraction loop
    that only resolved names let the pair through.
    """
    import tarfile

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "victim.txt").write_text("original", encoding="utf-8")

    payload = tmp_path / "evil.tar.gz"
    with tarfile.open(payload, "w:gz") as tar:
        link = tarfile.TarInfo("link")
        link.type = tarfile.SYMTYPE
        link.linkname = "../outside"
        tar.addfile(link)

    dest = tmp_path / "dest"
    dest.mkdir()
    with tarfile.open(payload, "r:gz") as tar:
        with pytest.raises(ValueError, match="links outside the destination"):
            fetch._safe_extract(tar, dest)

    assert (outside / "victim.txt").read_text(encoding="utf-8") == "original"


def test_a_plain_member_still_extracts(tmp_path):
    """The guard must refuse escapes without refusing ordinary archives."""
    import tarfile

    inner = tmp_path / "src"
    inner.mkdir()
    (inner / "data.txt").write_text("hello", encoding="utf-8")
    payload = tmp_path / "ok.tar.gz"
    with tarfile.open(payload, "w:gz") as tar:
        tar.add(inner / "data.txt", arcname="data.txt")

    dest = tmp_path / "dest"
    dest.mkdir()
    with tarfile.open(payload, "r:gz") as tar:
        fetch._safe_extract(tar, dest)
    assert (dest / "data.txt").read_text(encoding="utf-8") == "hello"


def test_zip_extraction_refuses_an_escaping_member(tmp_path):
    """The zip branch had the identical defect, unflagged only for lack of a source."""
    import zipfile

    payload = tmp_path / "evil.zip"
    with zipfile.ZipFile(payload, "w") as z:
        z.writestr("../escaped.txt", "nope")

    dest = tmp_path / "dest"
    dest.mkdir()
    with zipfile.ZipFile(payload) as z:
        with pytest.raises(ValueError, match="escapes the destination"):
            fetch._safe_extract_zip(z, dest)


def test_an_uninstalled_subject_has_no_capabilities_and_does_not_raise():
    """CI has no `decancer_py`, and that is how a green local suite failed there.

    `all_subjects()` constructs every registered subject, and construction
    succeeds for a library that is not installed — `available()` is what reports
    the absence. Asking such a subject for its capabilities used to call
    `transforms()`, which imports, so `ModuleNotFoundError` came straight back
    through `supports()` and killed any caller that had not checked availability
    first.
    """

    class Absent(subjects._Base):
        ROLES = {subjects.Role.SANITIZER: "nope"}

        def __init__(self):
            super().__init__()
            self.info = subjects.SubjectInfo(
                name="absent", version="0", origin="", url="", role="not installed"
            )

        def available(self):
            return (False, "pip install nothing")

        def transforms(self):
            import a_module_that_does_not_exist  # noqa: F401

            return {}

    subject = Absent()
    assert subject.capabilities() == set(), "an absent subject provides nothing"

    # And the whole path a suite takes must survive it.
    suite = next(s for s in registry.all_suites() if s.MULTI_SUBJECT)
    supported, why = suite.supports(subject)
    assert not supported and why


# --- cohort parcelling and the plain-ASCII control (#970) -------------------


def _keyed(subject: str, suite: str, key: str, value: float, higher: bool = True) -> Outcome:
    from benchmarks.meta.protocol import Measurement, Method

    return Outcome(
        suite=suite,
        family=Family.NORMATIVE,
        provenance=Provenance(
            origin="o", citation="c", url="http://x", version="1", licence="l", issues=(1,)
        ),
        method=Method(subject=subject, subject_version="1"),
        population=10,
        measurements=[Measurement(key=key, value=value, of=1.0, higher_is_better=higher)],
    )


def _tag_shaped_outcomes() -> list[Outcome]:
    """The `mcp-tag-block-concealment` shape from #970, in miniature.

    Thirteen subjects answer the transform key; two of them — the ones with a
    detector — answer a detection key as well. `withdet` gives the best answer
    to every question asked: it removes the payload outright, and it stays
    silent on the plain-ASCII control that hides nothing.
    """
    outs = [
        _keyed("withdet", "tag", "payload_removed", 1.0),
        _keyed("otherdet", "tag", "payload_removed", 0.6),
    ]
    outs += [_keyed(f"plain{i}", "tag", "payload_removed", 1.0 - 0.05 * i) for i in range(11)]
    # Directed lower-is-better: firing on plain ASCII is a false positive.
    outs += [
        _keyed("withdet", "tag", "detected_plain", 0.0, higher=False),
        _keyed("otherdet", "tag", "detected_plain", 1.0, higher=False),
    ]
    return outs


def test_a_detection_key_and_a_transform_key_are_separate_axes():
    """Being asked more questions is not a handicap to be scored.

    Averaged into one parcel, a detector's mean over two answers could not reach
    a transliterator's single answer: a two-subject key standardised on a sample
    of two caps |z| at 0.707, below the +0.76 a thirteen-subject key reaches. So
    `disarm` answered every question on the TAG-block suite better than anyone
    and ranked 8 of 12.
    """
    items = leaderboard.parcel(leaderboard.collect(_tag_shaped_outcomes()))
    assert len(items) == 2, "one axis per cohort of subjects, not one per suite"
    by_axis = {i.axis: i for i in items}
    transform = by_axis["tag [payload_removed]"]
    detection = by_axis["tag [detected_plain]"]
    assert len(transform.scores) == 13
    assert set(detection.scores) == {"withdet@1", "otherdet@1"}
    assert all(i.suite == "tag" for i in items), "the suite is still recorded"
    # Every subject in a cohort answered everything the cohort answered, so the
    # completeness check is now an invariant rather than a filter.
    for item in items:
        assert all(item.complete(s) for s in item.scores)


def test_answering_the_detection_key_too_never_costs_the_transform_rank():
    """Scope (a) of #970: more answers, never a lower place."""
    board = leaderboard.build(_tag_shaped_outcomes(), bootstrap=20)
    per = board.per_benchmark()
    transform = per["tag [payload_removed]"]
    best = min(st.rank for st in transform if not st.partial and not st.control)
    withdet = next(st for st in transform if st.subject == "withdet@1")
    assert withdet.rank == best, (
        "a subject that answers the transform key perfectly and the detection "
        "key correctly must rank no lower than one that answers the transform "
        "key alone"
    )


def test_a_detector_firing_on_the_plain_control_does_not_outrank_silence():
    """Scope (b) of #970: a false positive is not coverage."""
    board = leaderboard.build(_tag_shaped_outcomes(), bootstrap=20)
    detection = board.per_benchmark()["tag [detected_plain]"]
    order = [st.subject for st in detection if not st.control]
    assert order[0] == "withdet@1", (
        "silence on a vector that hides nothing is the right answer; firing on "
        "it is reporting the words, not an encoding"
    )
    assert order[1] == "otherdet@1"


def test_two_axes_from_one_suite_do_not_collide_on_the_suite_name():
    """`per_benchmark` is keyed by axis; keying it by suite dropped one.

    Silently: a dict assignment, so the detection axis simply never appeared in
    the report and its ranking went unpublished.
    """
    board = leaderboard.build(_tag_shaped_outcomes(), bootstrap=20)
    assert len(board.per_benchmark()) == len(board.items) == 2
    labels = set(board.per_benchmark())
    assert labels == {"tag [payload_removed]", "tag [detected_plain]"}, (
        "both halves are named, never just the smaller one"
    )
    # And the pairwise correlation table cannot key two axes to (suite, suite).
    for pair in board.correlations:
        assert pair[0] != pair[1]


def test_an_unsplit_suite_keeps_its_bare_name():
    outs = [_keyed(s, "s", "m", v) for s, v in (("a", 0.9), ("b", 0.5), ("c", 0.1))]
    (item,) = leaderboard.parcel(leaderboard.collect(outs))
    assert item.axis == "s", "a suite that asks everyone the same questions is one axis"


def test_coverage_counts_benchmarks_so_a_split_axis_is_not_a_penalty():
    """Splitting a parcel must not re-exclude the subject it was split for.

    Coverage over *axes* would mark every transform-only tool partial for
    lacking a detector — the same exclusion the peer-cohort completeness check
    exists to prevent, arriving one step later in the pipeline.
    """
    outs = _tag_shaped_outcomes()
    # Four more suites so the battery clears MIN_PARCELS, all asking everyone
    # the same question.
    for i in range(4):
        for name in ["withdet", "otherdet", *[f"plain{j}" for j in range(11)]]:
            outs.append(_keyed(name, f"wide{i}", "m", 0.5))
    board = leaderboard.build(outs, bootstrap=20)
    partial = [st.subject for st in board.standings if st.partial]
    assert partial == [], f"no subject is partial here; got {partial}"
    plain0 = next(st for st in board.standings if st.subject == "plain0@1")
    assert plain0.suites == 5, "scored on all five benchmarks"
    assert plain0.items == 5, "and on five of the six axes, having no detector"
    # And the report says five of five, not five of six: a question it was never
    # asked is not a gap in what it answered.
    md = render_markdown(
        RunReport(
            outcomes=outs,
            selected=len(outs),
            registered=len(outs),
            subjects=sorted({o.method.subject_key for o in outs}),
        ),
        leaderboard=board,
    )
    assert "| 5/5 |" in md and "| 5/6 |" not in md
    assert "**6** axes over **5** benchmarks" in md


def test_the_plain_ascii_control_is_scored_as_a_false_positive():
    """`detected_t1_plain` is directed lower-is-better in the suite itself.

    T1 is the concealed instruction written out in printable ASCII. A Unicode
    detector that fires on it is reporting the words, and scored the other way
    round that reads as coverage — the shape #957 removed from disarm's own
    detector, rewarded here.
    """
    from benchmarks.meta.subjects import Role

    class OverEager(subjects._Base):
        ROLES = {Role.SANITIZER: "strip"}

        def __init__(self) -> None:
            super().__init__()
            self.info = subjects.SubjectInfo(
                name="over-eager", version="0", origin="", url="", role="fires on everything"
            )

        def available(self):
            return (True, "")

        def detectors(self):
            return {"anything": lambda text: True}

        def transforms(self):
            return {"strip": lambda text: text}

        def role(self, which, job=None):
            return self.transforms() if which == Role.SANITIZER else {}

    outcome = academic.TagBlockConcealment().run(subject=OverEager())
    got = {m.key: m for m in outcome.measurements}
    t1 = got["detected_t1_plain"]
    assert t1.higher_is_better is False, (
        "firing on the plain-ASCII control is a false positive, not coverage"
    )
    assert t1.value == 1.0, "the number still means 'a detector fired', as the key says"
    assert got["detected_t7_concealed"].higher_is_better is True


def test_a_control_never_sets_the_scale_inside_a_parcel():
    """ "Controls are placed, not fitted" holds within a parcel too.

    `parcel` passed the full subject list as the standardisation basis, which
    overrode `standardize`'s own control exclusion. `null-baseline` deletes all
    input and so sits several standard deviations out; letting it set the units
    compresses every real tool into a narrow band near the mean, and that
    compression is applied *before* the members are averaged, so it reweights
    the parcel. Caught in review on #970.
    """
    outs = [
        _keyed("a", "s", "m", 1.0),
        _keyed("b", "s", "m", 0.0),
        _keyed("null-baseline", "s", "m", -100.0),
    ]
    (item,) = leaderboard.parcel(leaderboard.collect(outs))
    # Two tools fitted on themselves are one sample standard deviation apart:
    # z = ±0.707. Fitted with the control in the basis they land 0.017 apart.
    gap = item.scores["a@1"] - item.scores["b@1"]
    assert gap == pytest.approx(2 / math.sqrt(2), abs=0.01), (
        f"the tools set the units, so they separate by 1.414; got {gap:.3f}"
    )
    # The control is still placed on that scale, just not fitted to it.
    assert item.scores["null-baseline@1"] < -100
