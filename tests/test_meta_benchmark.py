"""Tests for the meta-benchmark harness (``benchmarks/meta``).

The harness itself never reaches the network and never needs an external
corpus: everything asserted here runs off the registry, the selection logic and
the two suite tiers whose data is vendored or derived. Suites whose artifact is
absent must report SKIPPED, and that is asserted rather than assumed — a silent
pass on a missing corpus is the one failure mode this harness exists to prevent.
"""

from __future__ import annotations

import json

import pytest

from benchmarks.meta import registry
from benchmarks.meta.base import surfaces, thin
from benchmarks.meta.baseline import Drift, compare, snapshot
from benchmarks.meta.protocol import Availability, Family, Outcome, Provenance, Status
from benchmarks.meta.report import render_json, render_markdown
from benchmarks.meta.runner import run

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


def test_a_missing_artifact_skips_and_never_passes_silently():
    absent = [s for s in registry.all_suites() if not s.available()[0]]
    assert absent, "expected at least one suite to be missing its artifact"
    report = run(absent[:2], registered=len(registry.all_suites()))
    for outcome in report.outcomes:
        assert outcome.status is Status.SKIPPED
        assert not outcome.measurements
        assert outcome.skip_reason


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

        def run(self, limit=None):
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


def _outcome(name: str, key: str, value: float, of: float, population: int) -> Outcome:
    from benchmarks.meta.protocol import Measurement

    return Outcome(
        suite=name,
        family=Family.NORMATIVE,
        provenance=Provenance(
            origin="o", citation="c", url="http://x", version="1", licence="l", issues=(1,)
        ),
        population=population,
        measurements=[Measurement(key=key, value=value, of=of, higher_is_better=True)],
    )


def test_snapshot_round_trips_through_json():
    snap = snapshot([_outcome("s", "k", 5, 10, 10)], "0.0.0")
    assert json.loads(json.dumps(snap))["suites"]["s"]["measurements"]["k"]["value"] == 5


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
    assert "Measured now" in md
    for outcome in report.ran:
        if outcome.provenance.finding:
            assert "**Found during the cycle.**" in md
            break


def test_markdown_names_every_skipped_suite_and_why():
    absent = [s for s in registry.all_suites() if not s.available()[0]]
    report = run(absent[:3], registered=len(registry.all_suites()))
    md = render_markdown(report)
    assert "## Not run" in md
    for outcome in report.skipped:
        assert outcome.suite in md


def test_json_report_carries_provenance_and_the_external_flag(derived_suites):
    report = run(derived_suites[:2], registered=len(registry.all_suites()), limit=100)
    payload = json.loads(render_json(report))
    assert payload["registered"] == len(registry.all_suites())
    for suite in payload["suites"]:
        assert "external" in suite
        assert suite["provenance"]["citation"]


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
