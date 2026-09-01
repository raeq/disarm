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
import math
import os

import pytest

from benchmarks.meta import leaderboard, registry, subjects
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
    scored = 0
    for subject in subjects.all_subjects():
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
