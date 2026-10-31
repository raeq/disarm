"""Tests for the practitioner tier of the meta-benchmark.

The tier's rules are the point of it, so they are asserted here: a known answer
scores, an unlabelled corpus stays a census, the delete-everything control runs on
every run, and a copyleft source is cached from a pinned commit and never vendored.

Nothing here reaches the network or needs the real corpora. Upstream's transforms
are replaced by stubs, and the fixture corpus is synthetic. The driver tests need
Node with its permission model and skip without it, except in CI's sandbox job, which
sets `DISARM_REQUIRE_NODE` so that a missing or old Node fails. A test that reads a
cached upstream skips when it is absent.
"""

from __future__ import annotations

import fnmatch
import io
import json
import os
import re
import shutil
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path

import pytest
import yaml

import disarm
from benchmarks.meta import fetch, registry, subjects
from benchmarks.meta.base import REPO_ROOT
from benchmarks.meta.protocol import (
    Availability,
    Evidence,
    Family,
    Measurement,
    Outcome,
    Provenance,
    Status,
)
from benchmarks.meta.report import load_outcomes, render_json, render_markdown
from benchmarks.meta.runner import run
from benchmarks.meta.suites import practitioner
from benchmarks.meta.suites.practitioner import (
    ArcanumTaxonomy,
    BenignControls,
    GarakAnsiEscapes,
    GhostcharsLabels,
    L1b3rt4sFixtures,
    LabelFreeInvariants,
    P4rs3lt0ngv3Transforms,
    St3ggTextExamples,
    TokenSmugglingConstructions,
    _FixtureSuite,
    _KnownAnswerSuite,
    classify_transform,
    literal_constants,
    tree_digest,
)

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

DISARM = "disarm"
CONTROLS = ("null-baseline", "identity")
SANDBOX_JOB = "practitioner-sandbox"
REQUIRE_NODE = "DISARM_REQUIRE_NODE"
PROVENANCE = Provenance(
    origin="test",
    citation="test",
    url="https://example.com",
    version="1",
    licence="MIT",
    issues=(1,),
)


def _fullwidth(text: str) -> str:
    return "".join(chr(ord(c) + 0xFEE0) if 0x21 <= ord(c) <= 0x7E else c for c in text)


def _tag_run(text: str) -> str:
    return "".join(chr(0xE0000 + ord(c)) for c in text)


def _selector_run(text: str) -> str:
    return "".join(
        chr(0xFE00 + b) if b < 16 else chr(0xE0100 + b - 16) for b in text.encode("utf-8")
    )


def _stubbed_generator(tmp_path: Path, transforms: dict) -> P4rs3lt0ngv3Transforms:
    """A generator suite whose transforms are Python functions and whose Node is absent."""
    suite = P4rs3lt0ngv3Transforms()
    suite.available = lambda: (True, "")
    suite.locate = lambda: tmp_path
    suite.discover = lambda _root: sorted(transforms)

    def generate(_root, chosen, texts):
        return {
            name: {"outputs": [transforms[name](t) for t in texts], "error": None}
            for name in chosen
        }

    suite.generate = generate
    return suite


def _measured(outcome: Outcome, key: str) -> tuple[float, float | None]:
    found = outcome.measurement(key)
    assert found is not None, key
    return found.value, found.of


def _stubs() -> dict:
    return {
        "unicode/fullwidth.js": _fullwidth,
        "unicode/unchanged.js": lambda text: text,
        "concealment/invisible-text.js": _tag_run,
        "cipher/rot13.js": lambda text: text.translate(
            str.maketrans("abcdefghijklmnopqrstuvwxyz", "nopqrstuvwxyzabcdefghijklm")
        ),
        "case/uppercase-all.js": str.upper,
    }


# --- the family -------------------------------------------------------------


def test_the_tier_is_registered_external_and_selectable():
    names = {s.name for s in registry.select(families=["practitioner"])}
    assert names == {
        "p4rs3lt0ngv3-transforms",
        "garak-ansi-escapes",
        "l1b3rt4s-fixtures",
        "label-free-invariants",
        "benign-controls",
        "ghostchars-labels",
        "token-smuggling-constructions",
        "st3gg-text-examples",
        "arcanum-taxonomy",
    }
    for suite in practitioner.SUITES:
        assert suite.family is Family.PRACTITIONER
        assert suite.provenance.external


def test_evidence_is_declared_on_this_family_and_on_no_other():
    for suite in registry.all_suites():
        declared = suite.provenance.evidence is not None
        assert declared is (suite.family is Family.PRACTITIONER), suite.name


def test_the_evidence_declared_matches_the_base_class_that_enforces_it():
    for suite in practitioner.SUITES:
        if suite.provenance.evidence is Evidence.FIXTURE:
            assert isinstance(suite, _FixtureSuite), suite.name
        else:
            assert isinstance(suite, _KnownAnswerSuite), suite.name


def test_evidence_survives_the_json_round_trip_and_reaches_the_report(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "README.md").write_text("plain text", encoding="utf-8")
    suite = L1b3rt4sFixtures()
    suite.locate = lambda: corpus
    suite.available = lambda: (True, "")
    report = run([suite], registered=1, subjects=[subjects.by_name(DISARM)])
    assert "**Evidence.** fixture" in render_markdown(report)
    assert "Practitioner tools and corpora" in render_markdown(report)
    path = tmp_path / "run.json"
    path.write_text(render_json(report), encoding="utf-8")
    assert load_outcomes(str(path))[0].provenance.evidence is Evidence.FIXTURE


# --- rule 1: a known answer scores ------------------------------------------


@pytest.mark.parametrize(
    ("relative", "expected"),
    [
        ("unicode/bold.js", "style"),
        ("concealment/homoglyph.js", "style"),
        ("concealment/invisible-text.js", "carrier"),
        ("concealment/zerowidth-steganography.js", "carrier"),
        ("concealment/acrostic.js", "boundary"),
        ("cipher/rot13.js", "boundary"),
        ("encoding/base64.js", "boundary"),
        ("case/uppercase-all.js", "excluded"),
        ("format/reverse.js", "excluded"),
    ],
)
def test_a_transform_is_classified_by_upstreams_directory(relative, expected):
    assert classify_transform(relative) == expected


def test_an_unknown_transform_is_an_error_not_a_guess():
    with pytest.raises(ValueError, match="unclassified"):
        classify_transform("newfolder/thing.js")


def test_restyling_counts_only_when_both_sides_land_on_one_form(tmp_path):
    suite = _stubbed_generator(tmp_path, _stubs())
    outcome = suite.run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.OK, outcome.error
    assert _measured(outcome, "styles_recovered") == (2, 2)
    assert _measured(outcome, "carriers_removed") == (4, 4)


def test_a_transform_that_changes_nothing_is_held_out_of_the_denominator(tmp_path):
    suite = _stubbed_generator(tmp_path, _stubs())
    outcome = suite.run(subject=subjects.by_name("identity"))
    assert _measured(outcome, "pairs_held_out_unchanged")[0] == 2
    assert _measured(outcome, "styles_recovered") == (0, 2)


def test_a_cipher_is_counted_and_never_directed(tmp_path):
    suite = _stubbed_generator(tmp_path, _stubs())
    outcome = suite.run(subject=subjects.by_name(DISARM))
    assert outcome.measurement("boundary_recovered").higher_is_better is None


def test_a_transform_that_failed_to_run_is_counted(tmp_path):
    def broken(_root, chosen, texts):
        return {name: {"outputs": [], "error": "boom"} for name in chosen}

    suite = _stubbed_generator(tmp_path, {"unicode/fullwidth.js": _fullwidth, **_stubs()})
    healthy = suite.generate

    def partly(root, chosen, texts):
        out = healthy(root, chosen, texts)
        out["unicode/fullwidth.js"] = broken(root, ["x"], texts)["x"]
        return out

    suite.generate = partly
    outcome = suite.run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "transforms_that_failed_to_run")[0] == 1


def test_the_limit_samples_transforms_by_stride(tmp_path):
    transforms = {f"unicode/t{i:02}.js": _fullwidth for i in range(20)}
    suite = _stubbed_generator(tmp_path, transforms)
    outcome = suite.run(limit=5, subject=subjects.by_name(DISARM))
    assert _measured(outcome, "transforms")[0] == 5
    assert set(outcome.extra["recovered_of_pairs_by_transform"]) >= {"unicode/t00", "unicode/t12"}


def test_the_report_carries_transform_names_and_no_generated_text(tmp_path):
    suite = _stubbed_generator(tmp_path, _stubs())
    report = run([suite], registered=1, subjects=[subjects.by_name(DISARM)])
    rendered = render_json(report)
    assert _fullwidth("quick") not in rendered


# --- rule 2: an unlabelled corpus stays a fixture ---------------------------


class _FixtureThatScores(_FixtureSuite):
    name = "fixture-that-scores"
    availability = Availability.DERIVED
    provenance = PROVENANCE

    def census(self, outcome, limit):
        outcome.population = 1
        outcome.measurements.append(_directed("control_delete_everything_x"))
        outcome.measurements.append(_directed("score", higher_is_better=True))


def _directed(key, higher_is_better=None):
    return Measurement(key=key, value=1, of=1, higher_is_better=higher_is_better)


class _FixtureWithoutControl(_FixtureSuite):
    name = "fixture-without-control"
    availability = Availability.DERIVED
    provenance = PROVENANCE

    def census(self, outcome, limit):
        outcome.population = 1
        outcome.measurements.append(_directed("a_count"))


def test_a_fixture_that_reports_a_score_is_an_error():
    outcome = _FixtureThatScores().run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.ERROR
    assert "cannot score" in outcome.error


def test_a_fixture_without_the_control_is_an_error():
    outcome = _FixtureWithoutControl().run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.ERROR
    assert "delete-everything" in outcome.error


@pytest.fixture
def synthetic_corpus(tmp_path):
    """A corpus shaped like the real one and built here. No upstream byte is in it."""
    root = tmp_path / "corpus"
    root.mkdir()
    secret = "SYNTHETICSECRETWORD"
    (root / "README.md").write_text(f"cover text{_selector_run(secret)}\n", encoding="utf-8")
    (root / "TAGGED.md").write_text(f"more cover{_tag_run(secret)}\n", encoding="utf-8")
    template = "share one template between every styled line " * 30
    lines = [template, _fullwidth(template), template.upper()]
    (root / "GROK-MEGA.mkd").write_text("\n".join(lines), encoding="utf-8")
    (root / "TOKEN80M8.mkd").write_text(chr(0xFE00) * 5000, encoding="utf-8")
    return root, secret


def _fixture_suite(root: Path) -> L1b3rt4sFixtures:
    suite = L1b3rt4sFixtures()
    suite.locate = lambda: root
    suite.available = lambda: (True, "")
    return suite


@pytest.mark.parametrize("subject", [DISARM, *CONTROLS])
def test_every_number_from_the_fixture_is_a_census(synthetic_corpus, subject):
    root, _ = synthetic_corpus
    outcome = _fixture_suite(root).run(subject=subjects.by_name(subject))
    assert outcome.status is Status.OK, outcome.error
    assert outcome.measurements
    assert all(m.higher_is_better is None for m in outcome.measurements)


def test_the_fixture_shows_why_it_cannot_rank(synthetic_corpus):
    """Deleting everything looks perfect on both of its headline numbers."""
    root, _ = synthetic_corpus
    outcome = _fixture_suite(root).run(subject=subjects.by_name("null-baseline"))
    assert _measured(outcome, "carriers_left")[0] == 0
    assert _measured(outcome, "convergence_median")[0] == 1
    assert _measured(outcome, "control_delete_everything_convergence_median")[0] == 1
    assert _measured(outcome, "convergence_chars_kept")[0] == 0


def test_an_independent_decoder_agrees_with_decode_smuggled(synthetic_corpus):
    root, _ = synthetic_corpus
    outcome = _fixture_suite(root).run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "smuggled_runs")[0] == 2
    assert _measured(outcome, "decoder_agrees_on_runs") == (2, 2)


def test_the_stress_file_is_counted_and_kept_out_of_the_smuggled_census(synthetic_corpus):
    root, _ = synthetic_corpus
    outcome = _fixture_suite(root).run(subject=subjects.by_name("identity"))
    assert _measured(outcome, "stress_code_points")[0] == 5000
    assert _measured(outcome, "stress_completed") == (1, 1)
    assert _measured(outcome, "stress_carriers_left") == (5000, 5000)
    left, of = _measured(outcome, "carriers_left")
    assert left == of < 5000


def test_no_corpus_text_reaches_the_report(synthetic_corpus):
    root, secret = synthetic_corpus
    report = run(
        [_fixture_suite(root)],
        registered=1,
        subjects=[subjects.by_name(DISARM), subjects.by_name("identity")],
    )
    for rendered in (render_json(report), render_markdown(report)):
        assert secret not in rendered
        assert "styled line" not in rendered


# --- rule 3: the control runs on every run ----------------------------------


class _ControlThatScores(_KnownAnswerSuite):
    name = "control-that-scores"
    availability = Availability.DERIVED
    provenance = PROVENANCE

    def scored(self, outcome, limit):
        outcome.population = 1
        outcome.measurements.append(_directed("control_delete_everything"))


class _ControlMissing(_KnownAnswerSuite):
    name = "control-missing"
    availability = Availability.DERIVED
    provenance = PROVENANCE

    def scored(self, outcome, limit):
        outcome.population = 1
        outcome.measurements.append(_directed("score", higher_is_better=True))


def test_a_metric_the_control_can_pass_reports_nothing():
    outcome = _ControlThatScores().run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.ERROR
    assert "cannot fail" in outcome.error


def test_a_known_answer_suite_without_the_control_is_an_error():
    outcome = _ControlMissing().run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.ERROR
    assert "delete-everything" in outcome.error


@pytest.mark.parametrize("control", CONTROLS)
def test_neither_control_recovers_anything(tmp_path, control):
    suite = _stubbed_generator(tmp_path, _stubs())
    outcome = suite.run(subject=subjects.by_name(control))
    assert outcome.status is Status.OK, outcome.error
    for key in ("styles_recovered", "carriers_removed", "boundary_recovered"):
        assert _measured(outcome, key)[0] == 0, key


def test_the_controls_are_measured_in_a_run_that_scores_only_disarm(tmp_path):
    suite = _stubbed_generator(tmp_path, _stubs())
    outcome = suite.run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "control_delete_everything")[0] == 0
    assert _measured(outcome, "control_identity")[0] == 0


# --- garak ------------------------------------------------------------------

GARAK_SOURCE = r"""
raise SystemExit("this file is parsed and must never run")
TOKENS = ["\x1b[", "\x9b"]
LIVE_PAYLOADS = TOKENS + ["Hello \x1b[32mGREEN\x1b[0m\x07"]
RAW_SEQS = ["\x9b"]
RAW_COMMANDS = ["\033", "\x1b"]
IGNORED = set([r"\x1b"])
"""


def test_the_garak_file_is_read_without_being_run():
    constants = literal_constants(GARAK_SOURCE)
    assert len(constants["LIVE_PAYLOADS"]) == 3
    assert constants["RAW_COMMANDS"] == [chr(0x1B), chr(0x1B)]
    assert "IGNORED" not in constants


def _garak_suite(tmp_path: Path) -> GarakAnsiEscapes:
    path = tmp_path / "ansi.py"
    path.write_text(GARAK_SOURCE, encoding="utf-8")
    suite = GarakAnsiEscapes()
    suite.locate = lambda: path
    suite.available = lambda: (True, "")
    return suite


def test_an_escape_counts_as_neutralized_only_with_the_cover_intact(tmp_path):
    outcome = _garak_suite(tmp_path).run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.OK, outcome.error
    assert _measured(outcome, "escapes_neutralized") == (3, 3)
    assert _measured(outcome, "control_delete_everything") == (0, 3)
    assert _measured(outcome, "control_identity") == (0, 3)


@pytest.mark.parametrize("control", CONTROLS)
def test_neither_control_neutralizes_an_escape(tmp_path, control):
    outcome = _garak_suite(tmp_path).run(subject=subjects.by_name(control))
    assert _measured(outcome, "escapes_neutralized")[0] == 0


# --- rule 4: cached from a pinned commit, never vendored --------------------


@pytest.mark.parametrize("suite", practitioner.SUITES, ids=lambda s: s.name)
def test_every_source_is_cached_from_a_pinned_commit(suite):
    if suite.availability is Availability.DERIVED:
        assert not suite.SOURCES, "a suite that downloads something is not derived"
        return
    assert suite.availability is Availability.NETWORK
    assert suite.SOURCES
    for source in suite.SOURCES:
        assert re.search(r"/[0-9a-f]{40}(/|$)", source.url), source.url
        assert "refs/heads" not in source.url
        assert source.licence


def test_nothing_from_a_copyleft_source_is_vendored():
    """Their distinctive file names, anywhere a vendored copy could plausibly sit."""
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    if tracked.returncode != 0:
        pytest.skip("not a git checkout")
    distinctive = {"BaseTransformer.js", "TOKEN80M8.mkd", "GROK-MEGA.mkd", "#MOTHERLOAD.txt"}
    for line in tracked.stdout.splitlines():
        assert Path(line).name not in distinctive, line
        assert "P4RS3LT0NGV3" not in line, line
        assert "L1B3RT4S" not in line, line


def test_the_copyleft_licence_is_recorded_on_the_copyleft_sources():
    for suite in (P4rs3lt0ngv3Transforms(), L1b3rt4sFixtures()):
        assert "AGPL-3.0" in suite.provenance.licence
        assert all(source.licence == "AGPL-3.0" for source in suite.SOURCES)


@pytest.mark.parametrize("suite", practitioner.SUITES, ids=lambda s: s.name)
def test_the_provenance_text_is_plain(suite):
    """A hidden character in a record of hidden characters would be the attack itself."""
    p = suite.provenance
    for text in (p.origin, p.citation, p.licence, p.notes, p.finding, suite.summary):
        assert text.isascii(), f"{suite.name}: {text[:50]!r}"


# --- running upstream's code ------------------------------------------------


def test_a_tree_that_moved_is_refused_before_anything_runs(tmp_path, monkeypatch):
    (tmp_path / "unicode").mkdir()
    (tmp_path / "unicode" / "t.js").write_text("export default 1;", encoding="utf-8")
    suite = P4rs3lt0ngv3Transforms()
    suite.locate = lambda: tmp_path
    monkeypatch.setattr(practitioner.shutil, "which", lambda _name: "/usr/bin/node")
    monkeypatch.setattr(P4rs3lt0ngv3Transforms, "_node_major", staticmethod(lambda _n: 99))

    def must_not_run(*_args):
        raise AssertionError("generate ran against an unpinned tree")

    suite.generate = must_not_run
    outcome = suite.run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.SKIPPED
    assert "refusing to execute" in outcome.skip_reason


@pytest.mark.parametrize("major", [None, 24])
def test_an_old_or_absent_node_skips_and_says_why(tmp_path, monkeypatch, major):
    suite = P4rs3lt0ngv3Transforms()
    suite.locate = lambda: tmp_path
    monkeypatch.setattr(practitioner.shutil, "which", lambda _name: "/usr/bin/node")
    monkeypatch.setattr(P4rs3lt0ngv3Transforms, "_node_major", staticmethod(lambda _n: major))
    ready, reason = suite.available()
    assert not ready
    assert "permission model" in reason


def test_the_tree_digest_covers_names_bytes_and_symlinks(tmp_path):
    (tmp_path / "a.js").write_text("one", encoding="utf-8")
    first = tree_digest(tmp_path)
    (tmp_path / "a.js").write_text("two", encoding="utf-8")
    second = tree_digest(tmp_path)
    assert first != second
    (tmp_path / "a.js").rename(tmp_path / "b.js")
    assert tree_digest(tmp_path) != second
    (tmp_path / "link.js").symlink_to(tmp_path / "b.js")
    assert tree_digest(tmp_path) != second


def _node_or_skip() -> None:
    node = shutil.which("node")
    major = P4rs3lt0ngv3Transforms._node_major(node) if node else None
    if major is None or major < P4rs3lt0ngv3Transforms.MIN_NODE_MAJOR:
        if os.environ.get(REQUIRE_NODE):
            pytest.fail(f"{REQUIRE_NODE} is set and Node's major version is {major}")
        pytest.skip("needs Node with the permission model")


BASE_STUB = """
export class BaseTransformer { constructor(config) { Object.assign(this, config); } }
export default BaseTransformer;
"""


def _module(body: str) -> str:
    return (
        "import BaseTransformer from '../BaseTransformer.js';\n"
        f"export default new BaseTransformer({{ name: 't', func: function(text) {{ {body} }} }});\n"
    )


@pytest.fixture
def stub_tree(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("OUTSIDE-THE-ROOT", encoding="utf-8")
    root = tmp_path / "root"
    (root / "unicode").mkdir(parents=True)
    (root / "BaseTransformer.js").write_text(BASE_STUB, encoding="utf-8")
    bodies = {
        "bang": "return text + '!';",
        "random": "return text + Math.random();",
        "emoji": "return window.EmojiUtils.splitEmojis(text).join('-');",
        "encoder": "return String(new TextEncoder().encode(text).length);",
        "number": "return 7;",
        "loop": "while (true) {}",
        "read": (
            "const p = TextEncoder.constructor.constructor('return process')();"
            f"return p.getBuiltinModule('fs').readFileSync({json.dumps(str(outside))}, 'utf8');"
        ),
        "spawn": (
            "const p = TextEncoder.constructor.constructor('return process')();"
            "p.getBuiltinModule('child_process').execSync('true'); return 'spawned';"
        ),
        "write": (
            "const p = TextEncoder.constructor.constructor('return process')();"
            f"p.getBuiltinModule('fs').writeFileSync({json.dumps(str(tmp_path / 'w'))}, 'x');"
            "return 'wrote';"
        ),
    }
    for name, body in bodies.items():
        (root / "unicode" / f"{name}.js").write_text(_module(body), encoding="utf-8")
    return root, tmp_path


def _generate(root: Path, *names: str) -> dict:
    return P4rs3lt0ngv3Transforms().generate(root, [f"unicode/{n}.js" for n in names], ["abc"])


def test_the_driver_runs_a_module_on_our_text(stub_tree):
    _node_or_skip()
    root, _ = stub_tree
    result = _generate(root, "bang", "emoji", "encoder")
    assert result["unicode/bang.js"] == {"outputs": ["abc!"], "error": None}
    assert result["unicode/emoji.js"]["outputs"] == ["a-b-c"]
    assert result["unicode/encoder.js"]["outputs"] == ["3"]


def test_a_transform_that_draws_random_numbers_is_repeatable(stub_tree):
    _node_or_skip()
    root, _ = stub_tree
    first = _generate(root, "random")["unicode/random.js"]["outputs"]
    second = _generate(root, "bang", "random")["unicode/random.js"]["outputs"]
    assert first == second


def test_a_bad_transform_fails_alone(stub_tree):
    _node_or_skip()
    root, _ = stub_tree
    result = _generate(root, "number", "loop", "bang")
    assert "number" in result["unicode/number.js"]["error"]
    assert result["unicode/loop.js"]["error"]
    assert result["unicode/bang.js"]["outputs"] == ["abc!"]


@pytest.mark.parametrize("name", ["read", "spawn", "write"])
def test_the_permission_model_stops_an_escape_from_the_context(stub_tree, name):
    """The `vm` context is not the boundary, and these get out of it on purpose."""
    _node_or_skip()
    root, parent = stub_tree
    result = _generate(root, name)[f"unicode/{name}.js"]
    assert result["outputs"] == []
    assert "restricted" in result["error"]
    assert not (parent / "w").exists()


# --- label-free invariants (#1163) ------------------------------------------

#: A clean Russian word. `canonicalize` folds part of it, so its output reports `mixed_script`.
RUSSIAN = "\u043f\u0440\u0438\u0432\u0435\u0442"
SECRET = "UNIQUEMARKERXYZ"


def _invariants(*surfaces: dict, corpora: dict | None = None) -> LabelFreeInvariants:
    suite = LabelFreeInvariants()
    suite.locate = lambda: None
    suite.available = lambda: (True, "")
    suite.read_corpora = lambda: corpora or {"one": ["plain", SECRET], "two": [RUSSIAN]}
    if surfaces:
        suite.transforms = lambda: surfaces[0]
    return suite


def _raises(_text: str) -> str:
    raise ValueError("this surface always raises")


def _grows(text: str) -> str:
    return text + "x"


def test_the_sweep_counts_a_call_per_text_and_surface():
    surfaces = {"same": str, "other": str}
    outcome = _invariants(surfaces).run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.OK, outcome.error
    assert _measured(outcome, "texts")[0] == 3
    assert _measured(outcome, "surfaces")[0] == 2
    assert _measured(outcome, "calls")[0] == 6
    assert _measured(outcome, "corpora_read")[0] == 2


def test_a_surface_that_raises_is_counted_per_surface():
    surfaces = {"boom": _raises, "fine": str}
    outcome = _invariants(surfaces).run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "raised:boom") == (3, 3)
    assert _measured(outcome, "raised:fine") == (0, 3)
    assert _measured(outcome, "raised") == (3, 6)


def test_a_surface_that_is_not_a_fixed_point_is_counted_per_surface():
    surfaces = {"grows": _grows, "fine": str}
    outcome = _invariants(surfaces).run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "not_fixed_point:grows") == (3, 3)
    assert _measured(outcome, "not_fixed_point:fine") == (0, 3)
    assert _measured(outcome, "not_fixed_point") == (3, 6)


def test_a_sweep_whose_call_count_is_wrong_fails_loudly(monkeypatch):
    """An earlier sweep printed 0 moved because a broad `except` hid every failure."""
    real = LabelFreeInvariants._sweep

    def short(surface, texts):
        """Honest on the one-text probe, so only the count can catch it."""
        return real(surface, texts) if len(texts) == 1 else (0, 0, 0)

    monkeypatch.setattr(LabelFreeInvariants, "_sweep", staticmethod(short))
    outcome = _invariants({"fine": str}).run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.ERROR
    assert "calls" in outcome.error


def test_a_sweep_that_cannot_see_a_failure_fails_loudly(monkeypatch):
    """The call count is right here, and the sweep still reports nothing it could not see."""

    def blind(_surface, texts):
        return len(texts), 0, 0

    monkeypatch.setattr(LabelFreeInvariants, "_sweep", staticmethod(blind))
    outcome = _invariants({"fine": str}).run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.ERROR
    assert "cannot see" in outcome.error


def test_a_limit_caps_the_texts_a_sweep_reads():
    outcome = _invariants({"fine": str}).run(limit=1, subject=subjects.by_name(DISARM))
    assert _measured(outcome, "texts")[0] == 1
    assert _measured(outcome, "calls")[0] == 1


def test_no_surfaces_is_an_error_and_not_a_clean_result():
    outcome = _invariants({}).run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.ERROR


def test_no_texts_is_an_error_and_not_a_clean_result():
    suite = _invariants({"fine": str}, corpora={"one": []})
    assert suite.run(subject=subjects.by_name(DISARM)).status is Status.ERROR


@pytest.mark.parametrize("subject", [DISARM, *CONTROLS])
def test_every_invariant_is_a_census(subject):
    """They have a right answer, and deleting everything earns it, so they cannot rank."""
    outcome = _invariants().run(subject=subjects.by_name(subject))
    assert outcome.status is Status.OK, outcome.error
    assert all(m.higher_is_better is None for m in outcome.measurements)


def test_the_invariants_run_the_delete_everything_control():
    outcome = _invariants({"fine": str}).run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "control_delete_everything_raised") == (0, 3)
    assert _measured(outcome, "control_delete_everything_not_fixed_point") == (0, 3)


def test_a_sanitizer_gaining_a_kind_is_reported_per_kind():
    outcome = _invariants().run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "gained_a_kind:canonicalize") == (1, 3)
    assert _measured(outcome, "gained_kind:canonicalize:mixed_script") == (1, 3)
    assert _measured(outcome, "output_reports:canonicalize") == (1, 3)


def test_a_sanitizer_that_gains_nothing_says_so():
    outcome = _invariants().run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "gained_a_kind:profile:rag_ingest") == (0, 3)
    assert _measured(outcome, "output_reports:profile:rag_ingest") == (0, 3)


def test_a_sanitizer_that_raises_is_counted_and_does_not_end_the_run():
    """A raise is what `raised:<surface>` exists to report, for a sanitizer as for any other."""
    outcome = _invariants({"canonicalize": _raises}).run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.OK, outcome.error
    assert _measured(outcome, "raised:canonicalize") == (3, 3)
    assert _measured(outcome, "gained_a_kind:canonicalize") == (0, 3)
    assert _measured(outcome, "output_reports:canonicalize") == (0, 3)


def test_a_subject_with_no_detector_omits_the_gained_kinds():
    """Scoring another tool's output with disarm's own detector would be circular."""
    surfaces = {"canonicalize": str}
    outcome = _invariants(surfaces).run(subject=subjects.by_name("identity"))
    assert outcome.status is Status.OK, outcome.error
    assert not [m.key for m in outcome.measurements if "gained" in m.key or "output_" in m.key]


def test_a_corpus_text_never_reaches_a_report():
    report = run([_invariants()], registered=1, subjects=[subjects.by_name(DISARM)])
    assert report.outcomes[0].status is Status.OK
    assert SECRET not in render_markdown(report)
    assert SECRET not in render_json(report)


def test_the_invariants_skip_with_a_reason_when_nothing_is_provisioned(monkeypatch):
    suite = LabelFreeInvariants()
    monkeypatch.setattr(suite, "locate", lambda: None)
    outcome = suite.run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.SKIPPED
    assert outcome.skip_reason


def test_the_invariants_read_only_the_corpora_that_are_provisioned(tmp_path, monkeypatch):
    monkeypatch.setattr(practitioner, "FETCH_CACHE", tmp_path)
    suite = LabelFreeInvariants()
    corpus = next(c for c in suite.CORPORA if c.source.filename.endswith("benign_prompts.txt"))
    path = tmp_path / corpus.source.filename
    path.parent.mkdir(parents=True)
    path.write_text("first\n\nsecond\n", encoding="utf-8")
    assert suite.read_corpora() == {corpus.name: ["first", "second"]}


def test_each_corpus_is_pinned_to_a_commit_and_a_digest():
    for corpus in LabelFreeInvariants().CORPORA:
        assert re.search(r"/[0-9a-f]{40}/", corpus.source.url), corpus.source.url
        assert re.fullmatch(r"[0-9a-f]{64}", corpus.source.sha256 or ""), corpus.name
        assert corpus.source.licence


def test_a_csv_corpus_reads_the_prompt_column(tmp_path):
    path = tmp_path / "prompts.csv"
    path.write_text('id,prompt\n1,"one, with a comma"\n2,\n3,three\n', encoding="utf-8")
    assert practitioner._csv_prompts(path) == ["one, with a comma", "three"]


def test_a_jsonl_corpus_reads_the_text_field(tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_text('{"text": "one"}\n\n{"text": "two"}\n', encoding="utf-8")
    assert practitioner._jsonl_text(path) == ["one", "two"]


@pytest.mark.parametrize(
    "shape",
    [
        lambda items: items,
        lambda items: {"title": "not this", "items": items},
    ],
)
def test_a_taxonomy_corpus_reads_every_example(tmp_path, shape):
    items = [{"examples": ["one", {"a": 1}]}, {"examples": ["two"]}, {"title": "none"}]
    path = tmp_path / "taxonomy.json"
    path.write_text(json.dumps({"evasions": shape(items)}), encoding="utf-8")
    assert practitioner._taxonomy_examples(path) == ["one", '{"a": 1}', "two"]


def test_the_readme_says_what_an_unlabelled_corpus_can_answer():
    readme = (REPO_ROOT / "benchmarks/meta/README.md").read_text(encoding="utf-8")
    flat = " ".join(readme.split())
    assert (
        "It can still answer three questions that need no label: whether a surface raises, "
        "whether its output is a fixed point, and whether a sanitizer's output reports what "
        "its input did not. None of them can rank a tool, and all of them can catch a "
        "regression."
    ) in flat
    assert "`label-free-invariants`" in readme


# --- benign controls (#1154) -------------------------------------------------

CURLY = "don\u2019t"
SETS = {"plain": ["hello there", "nothing to see"], "typed": [CURLY, "well\u2026", "hello there"]}


def _benign(corpora: dict | None = None) -> BenignControls:
    suite = BenignControls()
    suite.locate = lambda: None
    suite.available = lambda: (True, "")
    suite.read_corpora = lambda: corpora or SETS
    return suite


def test_each_benign_set_is_reported_alone():
    """Pooling would let 13,735 rows hide 24."""
    outcome = _benign().run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.OK, outcome.error
    assert _measured(outcome, "rows:plain")[0] == 2
    assert _measured(outcome, "rows:typed")[0] == 3
    assert _measured(outcome, "non_ascii:plain") == (0, 2)
    assert _measured(outcome, "non_ascii:typed") == (2, 3)


def test_a_detector_firing_on_a_benign_set_is_counted_per_set():
    outcome = _benign().run(subject=subjects.by_name(DISARM))
    expected = sum(map(disarm.has_anomalies, SETS["typed"]))
    assert _measured(outcome, "fires:has_anomalies:typed") == (expected, 3)
    assert _measured(outcome, "fires:has_anomalies:plain") == (0, 2)


def test_a_rewrite_of_a_benign_text_is_counted_per_set():
    outcome = _benign().run(subject=subjects.by_name(DISARM))
    expected = sum(disarm.canonicalize(text) != text for text in SETS["typed"])
    assert _measured(outcome, "rewritten:typed") == (expected, 3)
    assert _measured(outcome, "rewritten:plain") == (0, 2)


def test_silence_on_benign_text_is_shown_beside_a_detection_measure():
    """A detector that never fires reads perfect on a false-positive rate alone."""
    outcome = _benign().run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "planted_detected:has_anomalies:plain") == (2, 2)


def test_a_text_with_no_word_to_plant_in_is_left_out_of_that_denominator():
    corpora = {"short": ["hello there", "\u4f60\u597d", "a b"]}
    outcome = _benign(corpora).run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "planted_detected:has_anomalies:short") == (1, 1)


@pytest.mark.parametrize("subject", [DISARM, *CONTROLS])
def test_every_benign_number_is_a_census(subject):
    """The label says regular, not free of obfuscation, so a rate here is a ceiling."""
    outcome = _benign().run(subject=subjects.by_name(subject))
    assert outcome.status is Status.OK, outcome.error
    assert all(m.higher_is_better is None for m in outcome.measurements)


def test_the_null_baseline_rewrites_every_benign_text():
    outcome = _benign().run(subject=subjects.by_name("null-baseline"))
    assert _measured(outcome, "rewritten:plain") == (2, 2)
    assert _measured(outcome, "rewritten:typed") == (3, 3)


def test_a_subject_with_no_detector_omits_the_detector_rows():
    outcome = _benign().run(subject=subjects.by_name("null-baseline"))
    keys = [m.key for m in outcome.measurements]
    assert not [key for key in keys if key.startswith(("fires:", "planted_detected:"))]


def test_the_benign_controls_run_on_every_run():
    outcome = _benign().run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "control_delete_everything_rewritten:plain") == (2, 2)
    assert _measured(outcome, "control_identity_rewritten:plain") == (0, 2)


def test_a_benign_set_never_reaches_a_report():
    secret = "UNIQUEBENIGNMARKER"
    report = run([_benign({"one": [secret]})], registered=1, subjects=[subjects.by_name(DISARM)])
    assert report.outcomes[0].status is Status.OK
    assert secret not in render_markdown(report)
    assert secret not in render_json(report)


def test_the_benign_controls_skip_with_a_reason_when_nothing_is_provisioned(monkeypatch):
    suite = BenignControls()
    monkeypatch.setattr(suite, "locate", lambda: None)
    outcome = suite.run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.SKIPPED
    assert outcome.skip_reason


def test_the_benign_sets_are_the_ones_the_issue_fixed_in_advance():
    names = {corpus.name for corpus in BenignControls.CORPORA}
    assert names == {
        "jailbreak_llms:regular_prompts_2023_12_25",
        "jailbreak_llms:regular_prompts_2023_05_07",
        "fuzzyai:benign_prompts",
        "palisade:benign",
        "spikee:seeds-investment-advice-fp",
    }
    for corpus in BenignControls.CORPORA:
        assert re.search(r"/[0-9a-f]{40}/", corpus.source.url), corpus.source.url
        assert re.fullmatch(r"[0-9a-f]{64}", corpus.source.sha256 or ""), corpus.name


def test_the_palisade_reader_keeps_only_its_benign_rows(tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_text(
        '{"text": "one", "label": "benign"}\n{"text": "two", "label": "attack"}\n',
        encoding="utf-8",
    )
    corpus = next(c for c in BenignControls.CORPORA if c.name == "palisade:benign")
    assert corpus.read(path) == ["one"]


def test_the_readme_says_gutenberg_is_not_the_only_false_positive_axis():
    readme = (REPO_ROOT / "benchmarks/meta/README.md").read_text(encoding="utf-8")
    assert "`benign-controls`" in readme
    flat = " ".join(readme.split())
    assert "`gutenberg-benign` is no longer the only false-positive axis" in flat


# --- ghostchars' labels and fixtures (#1161) ---------------------------------

INVISIBLE = "pay\u200bpal"
BLACK_FLAG_TAGS = "\U0001f3f4\U000e0061\U000e007f"
BLACK_FLAG = "\U0001f3f4"
EXCERPT_MARKER = "UNIQUEEXCERPTMARKER"


@pytest.fixture
def ghostchars_tree(tmp_path):
    root = tmp_path / "studies"
    (root / "prompt-census").mkdir(parents=True)
    rows = [
        {"label": "L", "excerpt": INVISIBLE},
        {"label": "L", "excerpt": "plain"},
        {"label": "O", "excerpt": INVISIBLE},
        {"label": "O", "excerpt": "plain"},
        {"label": "M", "excerpt": "plain"},
        {"label": "T", "excerpt": "plain"},
        {"label": "A", "excerpt": "plain"},
        {"label": "H", "excerpt": INVISIBLE},
        {"label": "D", "excerpt": INVISIBLE},
        {"label": "X", "excerpt": EXCERPT_MARKER},
        {"label": "B", "excerpt": INVISIBLE},
        {"label": "U", "excerpt": ""},
    ]
    (root / "prompt-census" / "classification.json").write_text(
        json.dumps({"categories": {"L": "language"}, "released": rows}), encoding="utf-8"
    )
    flags = root / "flag-tag-payloads"
    (flags / "fixtures").mkdir(parents=True)
    cases = [
        {"id": "wrapped", "text": BLACK_FLAG_TAGS, "findings": 1, "expected": BLACK_FLAG},
        {"id": "bare", "text": BLACK_FLAG, "findings": 0, "expected": BLACK_FLAG},
    ]
    (flags / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
    (flags / "fixtures" / "wrapped.txt").write_text(BLACK_FLAG_TAGS, encoding="utf-8")
    (flags / "fixtures" / "bare.txt").write_text(BLACK_FLAG, encoding="utf-8")
    code = root / "code-confusables" / "fixtures"
    code.mkdir(parents=True)
    (code / "one.txt").write_text(INVISIBLE, encoding="utf-8")
    (root / "no-fixtures-here").mkdir()
    return root


def _ghostchars(root: Path) -> GhostcharsLabels:
    suite = GhostcharsLabels()
    suite.locate = lambda: root
    suite.available = lambda: (True, "")
    return suite


def _direction(outcome: Outcome, key: str) -> bool | None:
    found = outcome.measurement(key)
    assert found is not None, key
    return found.higher_is_better


def test_a_label_that_should_stay_silent_reads_as_a_false_positive(ghostchars_tree):
    outcome = _ghostchars(ghostchars_tree).run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.OK, outcome.error
    assert _measured(outcome, "label_L_fired:has_anomalies") == (1, 2)
    assert _direction(outcome, "label_L_fired:has_anomalies") is False
    for label in "MTA":
        assert _direction(outcome, f"label_{label}_fired:has_anomalies") is False


def test_a_label_that_should_fire_reads_as_detection(ghostchars_tree):
    outcome = _ghostchars(ghostchars_tree).run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "label_O_fired:has_anomalies") == (1, 2)
    assert _direction(outcome, "label_O_fired:has_anomalies") is True


@pytest.mark.parametrize("label", ["H", "D", "X", "B", "U"])
def test_a_label_with_no_fixed_answer_is_a_census(ghostchars_tree, label):
    """H's excerpts lack the hidden text they were labelled for, so it is no detection rate."""
    outcome = _ghostchars(ghostchars_tree).run(subject=subjects.by_name(DISARM))
    assert _direction(outcome, f"label_{label}_fired:has_anomalies") is None


def test_every_label_is_reported_alone(ghostchars_tree):
    outcome = _ghostchars(ghostchars_tree).run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "labelled_rows")[0] == 12
    assert _measured(outcome, "label_L_rows")[0] == 2
    assert not outcome.measurement("label_fired:has_anomalies")


def test_a_flag_case_agrees_on_findings_in_both_directions(ghostchars_tree):
    outcome = _ghostchars(ghostchars_tree).run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "flag_findings_agree:has_anomalies") == (2, 2)
    assert _direction(outcome, "flag_findings_agree:has_anomalies") is True


def test_a_detector_that_always_fires_loses_a_flag_case(ghostchars_tree):
    suite = _ghostchars(ghostchars_tree)
    suite.detect = lambda: {"always": lambda _text: True}
    outcome = suite.run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "flag_findings_agree:always") == (1, 2)


def test_a_flag_case_compares_a_surface_with_the_repair_it_expects(ghostchars_tree):
    outcome = _ghostchars(ghostchars_tree).run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "flag_expected_matched:canonicalize") == (2, 2)
    assert _measured(outcome, "flag_expected_matched:strip_format") == (2, 2)
    assert _direction(outcome, "flag_expected_matched:canonicalize") is True


def test_deleting_everything_matches_no_expected_repair(ghostchars_tree):
    outcome = _ghostchars(ghostchars_tree).run(subject=subjects.by_name("null-baseline"))
    assert _measured(outcome, "control_delete_everything") == (0, 2)
    assert _measured(outcome, "flag_expected_matched:delete_all") == (0, 2)


def test_doing_nothing_earns_only_the_cases_with_nothing_to_repair(ghostchars_tree):
    outcome = _ghostchars(ghostchars_tree).run(subject=subjects.by_name("identity"))
    assert _measured(outcome, "control_identity") == (1, 2)


def test_each_study_with_fixtures_is_counted_alone(ghostchars_tree):
    outcome = _ghostchars(ghostchars_tree).run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "fixtures:code-confusables")[0] == 1
    assert _measured(outcome, "fixtures:flag-tag-payloads")[0] == 2
    assert _measured(outcome, "fixtures_fired:has_anomalies:code-confusables") == (1, 1)
    assert _direction(outcome, "fixtures_fired:has_anomalies:code-confusables") is None
    assert outcome.measurement("fixtures:no-fixtures-here") is None


def test_a_subject_with_no_detector_omits_the_detector_rows_here_too(ghostchars_tree):
    outcome = _ghostchars(ghostchars_tree).run(subject=subjects.by_name("identity"))
    assert outcome.status is Status.OK, outcome.error
    keys = [m.key for m in outcome.measurements]
    assert not [key for key in keys if "_fired:" in key or key.startswith("flag_findings")]


def test_no_excerpt_reaches_a_report(ghostchars_tree):
    report = run([_ghostchars(ghostchars_tree)], registered=1, subjects=[subjects.by_name(DISARM)])
    assert report.outcomes[0].status is Status.OK
    assert EXCERPT_MARKER not in render_markdown(report)
    assert EXCERPT_MARKER not in render_json(report)


def test_the_selection_bias_is_named_where_a_reader_finds_it():
    notes = GhostcharsLabels.provenance.notes
    assert "selected" in notes
    assert "prevalence" in notes


def test_a_tree_that_is_not_the_pinned_one_is_refused(tmp_path):
    suite = GhostcharsLabels()
    suite.locate = lambda: tmp_path
    ready, reason = suite.available()
    assert not ready
    assert "digest" in reason


def test_the_ghostchars_source_is_a_pinned_commit():
    source = GhostcharsLabels.SOURCES[0]
    assert re.search(r"/tar\.gz/[0-9a-f]{40}$", source.url), source.url
    assert re.fullmatch(r"[0-9a-f]{64}", GhostcharsLabels.TREE_SHA256)


def test_the_readme_lists_the_ghostchars_suite():
    readme = (REPO_ROOT / "benchmarks/meta/README.md").read_text(encoding="utf-8")
    assert "`ghostchars-labels`" in readme


# --- what PyRIT and garak ship (#1143) ---------------------------------------


def _smuggling(subject: str) -> Outcome:
    return TokenSmugglingConstructions().run(subject=subjects.by_name(subject))


def test_disarm_recovers_each_construction():
    outcome = _smuggling(DISARM)
    assert outcome.status is Status.OK, outcome.error
    assert _measured(outcome, "constructions_recovered") == (7, 7)
    assert _direction(outcome, "constructions_recovered") is True


@pytest.mark.parametrize("subject", CONTROLS)
def test_a_control_recovers_no_construction(subject):
    outcome = _smuggling(subject)
    assert outcome.status is Status.OK, outcome.error
    assert _measured(outcome, "constructions_recovered") == (0, 7)


def test_the_constructions_run_both_controls_on_every_run():
    outcome = _smuggling(DISARM)
    assert _measured(outcome, "control_delete_everything") == (0, 7)
    assert _measured(outcome, "control_identity") == (0, 7)


def test_the_unpadded_sneaky_bits_framing_is_scored_as_well():
    """PyRIT pads each byte to eight bits, and garak and Augustus do not."""
    outcome = _smuggling(DISARM)
    assert _measured(outcome, "sneaky_bits_unpadded_recovered") == (1, 1)


def test_the_two_sneaky_bits_framings_differ():
    framings = TokenSmugglingConstructions.sneaky_bits
    assert framings("hi", pad=True) != framings("hi", pad=False)
    assert len(framings("hi", pad=True)) == 16
    assert len(framings("hi", pad=False)) == 14


def test_an_unpadded_space_is_a_zero_width_space():
    bits = TokenSmugglingConstructions.sneaky_bits("a b", pad=False)
    assert "\u200b" in bits


def test_each_construction_is_reported_with_what_disarm_did():
    outcome = _smuggling(DISARM)
    per_construction = outcome.extra["recovered_by_construction"]
    assert per_construction["tag characters"] == 1
    assert len(per_construction) == 7


def test_what_decode_smuggled_reads_is_reported_for_disarm_alone():
    """Moves when #1136 lands, so it is a census and not a score."""
    outcome = _smuggling(DISARM)
    decoded = outcome.measurement("constructions_decoded")
    assert decoded is not None
    assert decoded.of == 8
    assert decoded.higher_is_better is None
    assert _smuggling("identity").measurement("constructions_decoded") is None


def test_the_constructions_need_no_network_and_no_cache():
    assert TokenSmugglingConstructions().available() == (True, "")
    assert not TokenSmugglingConstructions.SOURCES


def test_neither_package_is_imported():
    _smuggling(DISARM)
    assert "pyrit" not in sys.modules
    assert "garak" not in sys.modules


def test_each_construction_quotes_its_source():
    notes = TokenSmugglingConstructions.provenance.notes
    for name in (
        "SneakyBitsSmugglerConverter",
        "VariationSelectorSmugglerConverter",
        "InjectUnicodeVariantSelectors",
        "AsciiSmugglerConverter",
        "InjectUnicodeTagChars",
        "BidiConverter",
        "ZeroWidthConverter",
        "InjectSneakyBits",
    ):
        assert name in notes, name


def test_the_readme_records_where_pyrit_and_garak_went():
    readme = (REPO_ROOT / "benchmarks/meta/README.md").read_text(encoding="utf-8")
    assert "`token-smuggling-constructions`" in readme
    rows = [line for line in readme.splitlines() if line.startswith("| PyRIT")]
    assert rows and "not read" not in rows[0]


# --- ST3GG's static text examples (#1141) ------------------------------------

ST3GG_COVER = "the quick brown fox"


def _write_st3gg(root: Path) -> None:
    words = ST3GG_COVER
    files = {
        "example_zero_width.txt": "the\u200b quick\u200c brown\u200d fox",
        "example_invisible_ink.txt": f"{words}\U000e0061\U000e0062",
        "example_variation_selector.txt": "the\ufe01 quick brown fox",
        "example_combining_diacritics.txt": "the\u034f quick brown fox",
        "example_directional_override.txt": f"\u202e{words}\u202c",
        "example_hangul_filler.txt": "the\u3164quick brown fox",
        "example_confusable_whitespace.txt": "the\u2002quick\u2003brown\u2009fox",
        "example_whitespace.txt": f"{words}   \n{words}\t\n",
        "example_homoglyph.txt": "the qu\u0456ck brown fox",
        "example_math_alphanumeric.txt": "\U0001d42d\U0001d421\U0001d41e quick brown fox",
        "example_normalization.txt": "cafe\u0301 quick",
    }
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8", newline="")
    for name in St3ggTextExamples.BOUNDARY_FILES:
        (root / name).write_text("plain words", encoding="utf-8")
    (root / "README.md").write_text(f"hidden {SECRET}", encoding="utf-8")
    (root / "generate_examples.py").write_text(
        'HOMOGLYPH_MAP = {"i": "\\u0456"}\n', encoding="utf-8"
    )


@pytest.fixture
def st3gg_tree(tmp_path):
    _write_st3gg(tmp_path)
    return tmp_path


def _st3gg(root: Path) -> St3ggTextExamples:
    suite = St3ggTextExamples()
    suite.locate = lambda: root
    suite.available = lambda: (True, "")
    return suite


def test_disarm_recovers_each_st3gg_technique(st3gg_tree):
    outcome = _st3gg(st3gg_tree).run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.OK, outcome.error
    assert _measured(outcome, "techniques_recovered") == (11, 11)
    assert _direction(outcome, "techniques_recovered") is True


@pytest.mark.parametrize("subject", CONTROLS)
def test_a_control_recovers_no_st3gg_technique(st3gg_tree, subject):
    outcome = _st3gg(st3gg_tree).run(subject=subjects.by_name(subject))
    assert _measured(outcome, "techniques_recovered") == (0, 11)


def test_the_st3gg_suite_runs_both_controls(st3gg_tree):
    outcome = _st3gg(st3gg_tree).run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "control_delete_everything") == (0, 11)
    assert _measured(outcome, "control_identity") == (0, 11)


def test_the_detector_is_its_own_axis_and_a_census(st3gg_tree):
    outcome = _st3gg(st3gg_tree).run(subject=subjects.by_name(DISARM))
    detected = outcome.measurement("techniques_detected:has_anomalies")
    assert detected is not None
    assert detected.of == 11
    assert detected.higher_is_better is None


def test_a_subject_with_no_detector_omits_the_st3gg_detector_axis(st3gg_tree):
    outcome = _st3gg(st3gg_tree).run(subject=subjects.by_name("identity"))
    assert not [m.key for m in outcome.measurements if m.key.startswith("techniques_detected")]


def test_the_boundary_files_are_counted_and_never_scored(st3gg_tree):
    outcome = _st3gg(st3gg_tree).run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "boundary_files")[0] == len(St3ggTextExamples.BOUNDARY_FILES)
    assert _direction(outcome, "boundary_files") is None


def test_a_derived_cover_equal_to_its_example_is_an_error(st3gg_tree):
    """A derivation that removes nothing would score every subject as having recovered it."""
    (st3gg_tree / "example_zero_width.txt").write_text(ST3GG_COVER, encoding="utf-8")
    outcome = _st3gg(st3gg_tree).run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.ERROR
    assert "zero width" in outcome.error


def test_the_homoglyph_cover_comes_from_the_generator_constant(st3gg_tree):
    (st3gg_tree / "generate_examples.py").write_text('HOMOGLYPH_MAP = {"x": "y"}\n', "utf-8")
    outcome = _st3gg(st3gg_tree).run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.ERROR
    assert "homoglyph" in outcome.error


def test_the_st3gg_suite_runs_nothing_from_upstream(st3gg_tree, monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("a subprocess was started")

    (st3gg_tree / "generate_examples.py").write_text(
        'raise SystemExit("this file was executed")\nHOMOGLYPH_MAP = {"i": "\\u0456"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    outcome = _st3gg(st3gg_tree).run(subject=subjects.by_name("identity"))
    assert outcome.status is Status.OK, outcome.error


def test_the_st3gg_readme_is_never_read(st3gg_tree):
    (st3gg_tree / "README.md").write_bytes(b"\xff not utf-8, so a read of it would raise")
    outcome = _st3gg(st3gg_tree).run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.OK, outcome.error


def test_the_st3gg_suite_skips_when_the_tree_is_absent(monkeypatch):
    suite = St3ggTextExamples()
    monkeypatch.setattr(suite, "locate", lambda: None)
    outcome = suite.run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.SKIPPED
    assert outcome.skip_reason


def test_a_st3gg_tree_that_is_not_the_pinned_one_is_refused(tmp_path):
    suite = St3ggTextExamples()
    suite.locate = lambda: tmp_path
    ready, reason = suite.available()
    assert not ready
    assert "digest" in reason


def test_the_readme_records_that_st3gg_was_read():
    readme = (REPO_ROOT / "benchmarks/meta/README.md").read_text(encoding="utf-8")
    assert "`st3gg-text-examples`" in readme
    rows = [line for line in readme.splitlines() if line.startswith("| ST3GG")]
    assert rows and "not read" not in rows[0]
    assert "122 zero-width" in rows[0]


# --- Arcanum's named evasions (#1160) ----------------------------------------

ARCANUM_MARKER = "UNIQUEARCANUMMARKER"


def _arcanum(tmp_path: Path, items: list[dict] | None = None) -> ArcanumTaxonomy:
    path = tmp_path / "taxonomy.json"
    rows = (
        items
        if items is not None
        else [
            {"title": "Invisible Text", "examples": [INVISIBLE, ARCANUM_MARKER + "\u200b"]},
            {"title": "Fullwidth Characters", "examples": ["\uff41\uff42", "plain"]},
            {"title": "Braille", "examples": ["\u2801"]},
            {"title": "Base64", "examples": ["aGVsbG8="]},
        ]
    )
    path.write_text(json.dumps({"evasions": rows}), encoding="utf-8")
    suite = ArcanumTaxonomy()
    suite.locate = lambda: path
    suite.available = lambda: (True, "")
    return suite


def test_the_taxonomy_counts_titles_and_non_ascii_examples(tmp_path):
    outcome = _arcanum(tmp_path).run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.OK, outcome.error
    assert _measured(outcome, "titles")[0] == 4
    assert _measured(outcome, "titles_with_non_ascii")[0] == 3
    assert _measured(outcome, "non_ascii_examples")[0] == 4


def test_an_ascii_example_is_left_out_of_the_denominator(tmp_path):
    outcome = _arcanum(tmp_path).run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "examples:style")[0] == 1


def test_detection_and_change_are_reported_per_class(tmp_path):
    outcome = _arcanum(tmp_path).run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "fired:has_anomalies:disguise") == (2, 2)
    assert _measured(outcome, "fired:has_anomalies:boundary") == (0, 1)
    assert _measured(outcome, "changed:disguise") == (2, 2)
    assert _measured(outcome, "fired:has_anomalies") == (
        sum(
            disarm.has_anomalies(text)
            for text in (INVISIBLE, ARCANUM_MARKER + "\u200b", "\uff41\uff42", "\u2801")
        ),
        4,
    )


def test_a_subject_with_no_detector_reports_change_alone(tmp_path):
    outcome = _arcanum(tmp_path).run(subject=subjects.by_name("null-baseline"))
    assert outcome.status is Status.OK, outcome.error
    assert _measured(outcome, "changed:disguise") == (2, 2)
    assert not [m.key for m in outcome.measurements if m.key.startswith("fired:")]


def test_the_taxonomy_runs_the_delete_everything_control(tmp_path):
    """Deleting everything would otherwise read as full change on every class."""
    outcome = _arcanum(tmp_path).run(subject=subjects.by_name(DISARM))
    assert _measured(outcome, "control_delete_everything_changed:disguise") == (2, 2)
    assert _measured(outcome, "control_identity_changed:disguise") == (0, 2)


@pytest.mark.parametrize("subject", [DISARM, *CONTROLS])
def test_every_taxonomy_number_is_a_census(tmp_path, subject):
    outcome = _arcanum(tmp_path).run(subject=subjects.by_name(subject))
    assert outcome.status is Status.OK, outcome.error
    assert outcome.measurements
    assert all(m.higher_is_better is None for m in outcome.measurements)


def test_an_unclassed_title_is_an_error(tmp_path):
    items = [{"title": "A Title Nobody Classed", "examples": ["x\u200by"]}]
    outcome = _arcanum(tmp_path, items).run(subject=subjects.by_name(DISARM))
    assert outcome.status is Status.ERROR
    assert "A Title Nobody Classed" in outcome.error


def test_each_title_gets_exactly_one_class():
    seen = [title for titles in ArcanumTaxonomy.CLASSES.values() for title in titles]
    assert len(seen) == len(set(seen))
    assert set(ArcanumTaxonomy.CLASSES) == {"disguise", "style", "boundary"}


def test_the_classes_say_who_chose_them_and_when():
    notes = ArcanumTaxonomy.provenance.notes
    assert "2026-10-31" in notes
    assert "Claude" in notes


def test_the_attribution_is_kept():
    provenance = ArcanumTaxonomy.provenance
    assert provenance.licence == "CC-BY-4.0"
    assert "Arcanum" in provenance.notes


def test_no_taxonomy_example_reaches_a_report(tmp_path):
    report = run([_arcanum(tmp_path)], registered=1, subjects=[subjects.by_name(DISARM)])
    assert report.outcomes[0].status is Status.OK
    assert ARCANUM_MARKER not in render_markdown(report)
    assert ARCANUM_MARKER not in render_json(report)


def test_the_title_breakdown_holds_counts_only(tmp_path):
    outcome = _arcanum(tmp_path).run(subject=subjects.by_name(DISARM))
    row = outcome.extra["by_title"]["Invisible Text"]
    assert row["class"] == "disguise"
    assert row["examples"] == 2


def test_the_taxonomy_reads_the_same_pinned_file_as_the_invariants():
    invariants = {c.source.url for c in LabelFreeInvariants.CORPORA}
    assert ArcanumTaxonomy.SOURCES[0].url in invariants


def test_the_readme_lists_the_taxonomy_suite():
    readme = (REPO_ROOT / "benchmarks/meta/README.md").read_text(encoding="utf-8")
    assert "`arcanum-taxonomy`" in readme


# --- the sandbox on CI (#1144) ----------------------------------------------


def _ci() -> dict:
    return yaml.safe_load((REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))


def _sandbox_job() -> dict:
    return _ci()["jobs"][SANDBOX_JOB]


def _sandbox_pytest_step() -> dict:
    job = _sandbox_job()
    found = [s for s in job["steps"] if str(s.get("run", "")).startswith("pytest ")]
    assert len(found) == 1, f"{SANDBOX_JOB} has {len(found)} pytest steps, not one"
    return found[0]


def _with_node(monkeypatch, major: int | None) -> None:
    found = None if major is None else "/usr/bin/node"
    monkeypatch.setattr(shutil, "which", lambda _name: found)
    monkeypatch.setattr(P4rs3lt0ngv3Transforms, "_node_major", staticmethod(lambda _n: major))


@pytest.mark.parametrize("major", [None, P4rs3lt0ngv3Transforms.MIN_NODE_MAJOR - 1])
def test_a_contributor_without_a_new_node_skips(monkeypatch, major):
    monkeypatch.delenv(REQUIRE_NODE, raising=False)
    _with_node(monkeypatch, major)
    with pytest.raises((pytest.skip.Exception, pytest.fail.Exception)) as outcome:
        _node_or_skip()
    assert outcome.type is pytest.skip.Exception


@pytest.mark.parametrize("major", [None, P4rs3lt0ngv3Transforms.MIN_NODE_MAJOR - 1])
def test_the_sandbox_job_fails_without_a_new_node(monkeypatch, major):
    """A skip is how these six tests went unnoticed on every CI run."""
    monkeypatch.setenv(REQUIRE_NODE, "1")
    _with_node(monkeypatch, major)
    with pytest.raises((pytest.skip.Exception, pytest.fail.Exception)) as outcome:
        _node_or_skip()
    assert outcome.type is pytest.fail.Exception


def test_a_new_enough_node_neither_skips_nor_fails(monkeypatch):
    monkeypatch.setenv(REQUIRE_NODE, "1")
    _with_node(monkeypatch, P4rs3lt0ngv3Transforms.MIN_NODE_MAJOR)
    _node_or_skip()


def test_ci_gives_the_sandbox_job_a_node_with_the_permission_model():
    versions = [
        step["with"]["node-version"]
        for step in _sandbox_job()["steps"]
        if "actions/setup-node" in step.get("uses", "")
    ]
    assert len(versions) == 1, versions
    assert int(versions[0]) >= P4rs3lt0ngv3Transforms.MIN_NODE_MAJOR


def test_ci_makes_an_old_node_a_failure_in_the_sandbox_job():
    assert _sandbox_pytest_step()["env"][REQUIRE_NODE]


def test_ci_runs_this_module_in_the_sandbox_job():
    assert "tests/test_meta_benchmark_practitioner.py" in _sandbox_pytest_step()["run"].split()


def test_ci_leaves_the_requirement_out_of_the_test_job():
    """Its Node stays what it is, so these tests skip there on purpose."""
    assert REQUIRE_NODE not in yaml.safe_dump(_ci()["jobs"]["test"])


def test_the_rollup_requires_the_sandbox_job():
    rollup = _ci()["jobs"]["all-ok"]
    assert SANDBOX_JOB in rollup["needs"]
    script = "\n".join(str(step.get("run", "")) for step in rollup["steps"])
    assert f"needs['{SANDBOX_JOB}'].result" in script
    assert "needs.changes.outputs.sandbox" in script


@pytest.mark.parametrize(
    "path",
    [
        "benchmarks/meta/suites/practitioner_driver.js",
        "benchmarks/meta/suites/practitioner.py",
        "tests/test_meta_benchmark_practitioner.py",
        ".github/workflows/ci.yml",
    ],
)
def test_a_change_to_the_sandbox_alone_starts_its_job(path):
    """`code` has no `*.js`, so a driver-only change would start nothing that runs it."""
    assert (REPO_ROOT / path).is_file(), path
    jobs = _ci()["jobs"]
    assert "needs.changes.outputs.sandbox" in jobs[SANDBOX_JOB]["if"]
    assert jobs["changes"]["outputs"]["sandbox"] == "${{ steps.filter.outputs.sandbox }}"
    step = next(s for s in jobs["changes"]["steps"] if s.get("id") == "filter")
    patterns = yaml.safe_load(step["with"]["filters"])["sandbox"]
    assert any(fnmatch.fnmatch(path, pattern) for pattern in patterns), patterns


def test_the_pinned_tree_still_matches_when_it_is_cached():
    suite = P4rs3lt0ngv3Transforms()
    root = suite.locate()
    if root is None:
        pytest.skip("P4RS3LT0NGV3 is not cached")
    assert tree_digest(root) == suite.TREE_SHA256


def test_every_real_transform_is_classified_when_it_is_cached():
    suite = P4rs3lt0ngv3Transforms()
    root = suite.locate()
    if root is None:
        pytest.skip("P4RS3LT0NGV3 is not cached")
    kinds = {classify_transform(relative) for relative in suite.discover(root)}
    assert kinds == {"style", "carrier", "boundary", "excluded"}


# --- provisioning -----------------------------------------------------------


def _serving(monkeypatch, body: bytes) -> None:
    monkeypatch.setattr(fetch, "urlopen", lambda *_a, **_k: nullcontext(io.BytesIO(body)))


def test_a_digest_mismatch_leaves_nothing_in_the_cache(tmp_path, monkeypatch):
    """It used to leave the bad bytes in place, and the next run read them as cached."""
    _serving(monkeypatch, b"unexpected")
    source = fetch.Source(
        url="https://example.com/a", filename="a.txt", licence="MIT", sha256="0" * 64
    )
    with pytest.raises(ValueError, match="expected sha256"):
        fetch.ensure(source, cache=tmp_path)
    assert list(tmp_path.iterdir()) == []
    assert fetch.ensure(source, cache=tmp_path, offline=True) is None


def test_an_archive_digest_is_checked_before_it_is_expanded(tmp_path, monkeypatch):
    _serving(monkeypatch, b"not a real archive")
    source = fetch.Source(
        url="https://example.com/a",
        filename="a",
        licence="MIT",
        kind="tar.gz",
        sha256="0" * 64,
    )
    with pytest.raises(ValueError, match="expected sha256"):
        fetch.ensure(source, cache=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_a_matching_digest_is_accepted(tmp_path, monkeypatch):
    import hashlib

    body = b"expected"
    _serving(monkeypatch, body)
    source = fetch.Source(
        url="https://example.com/a",
        filename="a.txt",
        licence="MIT",
        sha256=hashlib.sha256(body).hexdigest(),
    )
    got = fetch.ensure(source, cache=tmp_path)
    assert got is not None
    assert got.path.read_bytes() == body
