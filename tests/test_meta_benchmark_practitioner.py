"""Tests for the practitioner tier of the meta-benchmark.

The tier's rules are the point of it, so they are asserted here: a known answer
scores, an unlabelled corpus stays a census, the delete-everything control runs on
every run, and a copyleft source is cached from a pinned commit and never vendored.

Nothing here reaches the network or needs the real corpora. Upstream's transforms
are replaced by stubs, and the fixture corpus is synthetic. The driver tests need
Node with its permission model and skip without it, and a test that reads a cached
upstream skips when it is absent.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
from contextlib import nullcontext
from pathlib import Path

import pytest

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
    GarakAnsiEscapes,
    L1b3rt4sFixtures,
    P4rs3lt0ngv3Transforms,
    _FixtureSuite,
    _KnownAnswerSuite,
    classify_transform,
    literal_constants,
    tree_digest,
)

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

DISARM = "disarm"
CONTROLS = ("null-baseline", "identity")
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
    assert names == {"p4rs3lt0ngv3-transforms", "garak-ansi-escapes", "l1b3rt4s-fixtures"}
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
