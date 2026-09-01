"""Tests for the meta-benchmark harness (``benchmarks/meta``).

The harness itself never reaches the network and never needs an external
corpus: everything asserted here runs off the registry, the selection logic and
the two suite tiers whose data is vendored or derived. Suites whose artifact is
absent must report SKIPPED, and that is asserted rather than assumed — a silent
pass on a missing corpus is the one failure mode this harness exists to prevent.
"""

from __future__ import annotations

import inspect
import json
import os

import pytest

from benchmarks.meta import registry, subjects
from benchmarks.meta.base import SuiteBase, surfaces, thin
from benchmarks.meta.baseline import Drift, compare, snapshot
from benchmarks.meta.protocol import Availability, Family, Outcome, Provenance, Status
from benchmarks.meta.report import render_json, render_markdown
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
    assert "disarm::s" in round_tripped["suites"]
    assert round_tripped["suites"]["disarm::s"]["measurements"]["k"]["value"] == 5
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
    forbidden = ("confusables_lgr.tsv", "confusables_supplement.tsv", "confusables_attested.tsv")
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
    assert identity.measurement("destroyed_worst_surface").value == 0
    assert identity.measurement("destroyed_gentlest_surface").value == 0
    assert identity.measurement("clean_ascii_altered_worst").value == 0
    assert identity.measurement("degenerate").value == 0


def test_the_degenerate_flag_fires_only_on_the_null_baseline():
    flagged = set()
    for subject in subjects.all_subjects():
        out = registry.by_name("corruption-cost").run(subject=subject)
        if out.measurement("degenerate").value:
            flagged.add(subject.info.name)
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
