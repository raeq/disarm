"""#832 — a workflow that runs on `push` must not read `github.base_ref` unguarded.

`github.base_ref` is the *target branch of a pull request*. On a push it is empty, so
`git merge-base origin/${{ github.base_ref }} HEAD` expands to `git merge-base origin/ HEAD`
and fails with `fatal: Not a valid object name origin/`.

`perf-gate.yml` runs on both events and two of its three jobs did exactly that, so they
died before benchmarking anything. Measured over the last 60 runs at the time of the fix:
44 `pull_request` runs, all successful; **13 push runs, all failures**. The gate had never
run on `main` — while a comment in the same file said "Pushes to main always run it, so
nothing reaches a release unmeasured".

The third job had the correct branch all along, under a comment naming this exact case.
That is what makes this worth a gate rather than a fix: the right answer was twelve lines
away from both wrong ones, and copying the wrong one was easier.

The rule is narrow on purpose. Reading `base_ref` is correct in a workflow that only runs
on `pull_request`, and correct inside an `if` that has already established the event. What
is never correct is reading it unguarded in a workflow that also runs on `push`.

`schedule` is the same case and the gate did not cover it. `ci.yml` runs weekly for the
RustSec scan, and the changelog job #994 added ran `towncrier check --compare-with
"origin/${{ github.base_ref }}"` on that run too — `origin/`, again (#994 review). A guard
on the whole job, in its `if:`, counts: it establishes the event for every line inside.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"

#: `github.base_ref`, in either expression syntax.
BASE_REF = re.compile(r"github\.base_ref")

#: An event guard — the line establishes it is a pull request before using `base_ref`.
GUARD = re.compile(
    r"github\.event_name\s*==\s*'pull_request'"
    r"|\[\s*\"\$\{\{\s*github\.event_name\s*\}\}\"\s*=\s*\"pull_request\"\s*\]"
    r"|github\.event_name\s*!=\s*'push'"
)


def _workflows() -> list[Path]:
    return sorted(p for p in WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))


def test_there_are_workflows_to_check() -> None:
    """A gate over an empty directory passes for the wrong reason."""
    assert len(_workflows()) > 3, _workflows()


def _runs_on_push(text: str) -> bool:
    """True when the workflow's `on:` includes a `push` trigger, in any of its forms.

    Parsed rather than pattern-matched. An earlier draft required `on:` on its own line
    followed by exactly two spaces before `push:`, which silently exempted the inline
    forms — `on: push` and `on: [push, pull_request]` — and this repository already uses
    the inline style elsewhere. A gate that reports "not a push workflow" for a push
    workflow passes for the wrong reason, which is the failure this file exists to catch.

    Note the YAML 1.1 trap: `on` is a boolean keyword, so PyYAML parses the key as
    `True`, not `"on"`. All three forms below land under that key.

        on: push                      -> {True: "push"}
        on: [push, pull_request]      -> {True: ["push", "pull_request"]}
        on:\n  push:\n    branches: … -> {True: {"push": …}}
    """
    document = yaml.safe_load(text) or {}
    triggers = document.get("on", document.get(True))
    if isinstance(triggers, str):
        return triggers == "push"
    if isinstance(triggers, list):
        return "push" in triggers
    if isinstance(triggers, dict):
        return "push" in triggers
    return False


#: A job's header line under `jobs:` — two spaces, the id, a colon, nothing else.
JOB_HEADER = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")


def _job_if(document: dict, lines: list[str], number: int) -> str:
    """The `if:` of the job that line `number` (1-based) sits in, or `""`."""
    for line in reversed(lines[: number - 1]):
        if match := JOB_HEADER.match(line):
            job = (document.get("jobs") or {}).get(match.group(1))
            return str(job.get("if", "")) if isinstance(job, dict) else ""
    return ""


def _unguarded_base_refs(text: str, name: str) -> list[str]:
    """Lines reading `github.base_ref` in a workflow that also runs without one."""
    if not (_runs_on_push(text) or _runs_on_schedule(text)):
        return []  # `base_ref` is always populated when only pull_request triggers.

    document = yaml.safe_load(text) or {}
    offenders = []
    lines = text.split("\n")
    for number, line in enumerate(lines, 1):
        if not BASE_REF.search(line):
            continue
        # A comment describing the bug is not the bug. Both fixed jobs carry one that
        # quotes the broken expression, and an earlier draft of this gate flagged them.
        if line.lstrip().startswith("#"):
            continue
        # Guarded if this line, or any of the five above it, establishes the event.
        window = "\n".join(lines[max(0, number - 6) : number])
        if GUARD.search(window) or GUARD.search(line):
            continue
        # Or if the whole job only runs once the event is established.
        if GUARD.search(_job_if(document, lines, number)):
            continue
        offenders.append(f"{name}:{number}: {line.strip()}")
    return offenders


@pytest.mark.parametrize("path", _workflows(), ids=lambda p: p.name)
def test_no_unguarded_base_ref_in_a_push_workflow(path: Path) -> None:
    offenders = _unguarded_base_refs(path.read_text(encoding="utf-8"), path.name)
    assert not offenders, (
        f"{path.name} runs on `push` or `schedule`, where `github.base_ref` is empty. "
        "These lines read it without first establishing the event, which is how two of "
        "perf-gate.yml's three jobs came to run `git merge-base origin/ HEAD` on every "
        "push to main:\n  " + "\n  ".join(offenders)
    )


def test_a_scheduled_workflow_is_checked_and_a_job_guard_counts() -> None:
    """`schedule` has no `base_ref` either; a job-level `if:` establishes the event."""
    head = 'on:\n  pull_request:\n  schedule:\n    - cron: "0 5 * * 1"\njobs:\n  x:\n'
    step = (
        '    steps:\n      - run: towncrier check --compare-with "origin/${{ github.base_ref }}"\n'
    )
    assert len(_unguarded_base_refs(head + step, "ci.yml")) == 1
    guarded = head + "    if: github.event_name == 'pull_request'\n" + step
    assert _unguarded_base_refs(guarded, "ci.yml") == []


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("on: push\n", True),
        ("on: [push, pull_request]\n", True),
        ("on:\n  push:\n    branches: [main]\n  pull_request:\n", True),
        ("on: pull_request\n", False),
        ("on: [pull_request]\n", False),
        ("on:\n  pull_request:\n", False),
        ("on:\n  workflow_dispatch:\n", False),
    ],
    ids=["inline-str", "inline-list", "block", "pr-str", "pr-list", "pr-block", "dispatch"],
)
def test_every_trigger_form_is_recognised(source: str, expected: bool) -> None:
    """The inline forms are the ones an earlier draft of this gate exempted."""
    assert _runs_on_push(source) is expected


def test_the_check_can_actually_fail() -> None:
    """A gate that only ever passes is not a gate."""
    broken = "on:\n  push:\n    branches: [main]\n  pull_request:\njobs:\n  x:\n    steps:\n"
    broken += '      - run: git merge-base "origin/${{ github.base_ref }}" HEAD\n'
    assert _runs_on_push(broken)
    hits = [
        line
        for line in broken.split("\n")
        if BASE_REF.search(line) and not GUARD.search(line) and not line.lstrip().startswith("#")
    ]
    assert len(hits) == 1, hits


def test_the_guard_recognises_the_correct_shape() -> None:
    """The shape `perf-gate.yml`'s `changes` job had right all along."""
    guarded = 'if [ "${{ github.event_name }}" = "pull_request" ]; then\n'
    guarded += '  base="$(git merge-base "origin/${{ github.base_ref }}" HEAD)"\n'
    window = guarded
    assert GUARD.search(window), "the correct pattern must not be reported"


def test_perf_gate_takes_its_baseline_from_one_place() -> None:
    """The specific regression: three jobs, one computation.

    Both broken jobs recomputed the baseline rather than consuming it. Exporting it from
    the job that gets it right means a fourth job cannot reintroduce this by copying.
    """
    text = (WORKFLOWS / "perf-gate.yml").read_text(encoding="utf-8")
    assert "base: ${{ steps.f.outputs.base }}" in text, "the changes job must export it"
    assert text.count("needs.changes.outputs.base") >= 2, "both benchmarking jobs consume it"
    executable = "\n".join(line for line in text.split("\n") if not line.lstrip().startswith("#"))
    assert "merge-base origin/${{ github.base_ref }}" not in executable, (
        "an unguarded use remains outside a comment"
    )


# ---------------------------------------------------------------------------
# #782 — an action that reports by opening an issue needs `issues: write`
# ---------------------------------------------------------------------------

#: Actions whose non-PR reporting path is `POST /repos/:owner/:repo/issues`.
#:
#: `rustsec/audit-check` annotates a pull request with a check run, and on any other
#: event it has no pull request to annotate — so it opens an issue instead. Under
#: `contents: read` that call returns *"Resource not accessible by integration"* and the
#: job fails, **after** a clean audit.
#:
#: That direction is what makes it worth a gate. The job passed every week it had nothing
#: to report and failed every week it did: twelve consecutive red Mondays, each one a
#: security report nobody received, and none of it visible on the pull-request path that
#: gates a merge.
ISSUE_OPENING_ACTIONS = ("rustsec/audit-check",)


def _runs_on_schedule(text: str) -> bool:
    """As `_runs_on_push`, for the `schedule` trigger. Same YAML 1.1 `on`/`True` trap."""
    document = yaml.safe_load(text) or {}
    triggers = document.get("on", document.get(True))
    if isinstance(triggers, str):
        return triggers == "schedule"
    if isinstance(triggers, list):
        return "schedule" in triggers
    return isinstance(triggers, dict) and "schedule" in triggers


def _jobs_using(document: dict, actions: tuple[str, ...]) -> list[tuple[str, dict]]:
    found = []
    for name, job in (document.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            uses = step.get("uses", "") if isinstance(step, dict) else ""
            if any(uses.startswith(a) for a in actions):
                found.append((name, job))
                break
    return found


@pytest.mark.parametrize("path", _workflows(), ids=lambda p: p.name)
def test_an_issue_opening_action_on_a_schedule_can_open_an_issue(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if not _runs_on_schedule(text):
        return
    document = yaml.safe_load(text) or {}
    for name, job in _jobs_using(document, ISSUE_OPENING_ACTIONS):
        # Job permissions REPLACE the workflow's rather than adding to them, so the
        # workflow-level block is not a fallback and is deliberately not consulted here.
        permissions = job.get("permissions")
        assert permissions is not None, (
            f"{path.name}: job '{name}' runs an issue-opening action on a schedule with "
            f"no job-level permissions; it inherits the workflow's and cannot report"
        )
        # `permissions:` is legally a scalar as well as a mapping — `write-all` and
        # `read-all` are both valid. Indexing a string raises `AttributeError`, which
        # reports as an error rather than as a failure and says nothing about the
        # workflow (#878 review). Handle the scalar form as the answer it is.
        if isinstance(permissions, str):
            assert permissions == "write-all", (
                f"{path.name}: job '{name}' sets `permissions: {permissions}`, which "
                f"grants no issue write; it cannot report on a non-PR event"
            )
            continue
        assert isinstance(permissions, dict), (
            f"{path.name}: job '{name}' has an unrecognised `permissions:` shape "
            f"({type(permissions).__name__}); this gate cannot read it"
        )
        assert permissions.get("issues") == "write", (
            f"{path.name}: job '{name}' needs `issues: write` to report on a non-PR "
            f"event; it has {permissions}"
        )


def test_the_gate_has_something_to_check() -> None:
    """Anchored to the registry, not to the symptom (#806).

    If the audit job is renamed, retriggered or moved to its own workflow, this must
    keep finding it rather than passing over an empty set.
    """
    matches = [
        (path.name, name)
        for path in _workflows()
        if _runs_on_schedule(path.read_text(encoding="utf-8"))
        for name, _ in _jobs_using(
            yaml.safe_load(path.read_text(encoding="utf-8")) or {}, ISSUE_OPENING_ACTIONS
        )
    ]
    assert matches, "no scheduled issue-opening job found — has the audit job moved?"


# ---------------------------------------------------------------------------
# Tier 3 gates the CORE only — one verdict, not one per publisher
# ---------------------------------------------------------------------------


def test_tier3_is_called_by_exactly_one_publish_workflow() -> None:
    """`uses:` instantiates a fresh job per caller, so N callers are N runs.

    `tier3.yml` contains proptests, which draw random inputs. Four publish workflows
    calling it meant four independent draws on one artifact: a seed that fails in one
    and passes in three ships a subset of the bindings, and the three green ones look
    verified. Cutting v0.15.0 hit the benign version of that — all four failed on the
    same input, so nothing published and nothing diverged.

    The bindings inherit the gate transitively: each waits for the core on crates.io,
    and the core cannot get there unless `publish.yml`'s Tier 3 passed. Re-running it
    per publisher bought nothing and risked disagreement.
    """
    callers = []
    for path in _workflows():
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for name, job in (document.get("jobs") or {}).items():
            if isinstance(job, dict) and "tier3.yml" in str(job.get("uses", "")):
                callers.append((path.name, name))
    assert callers, "nothing calls tier3.yml — has the release gate been dropped entirely?"
    assert [c[0] for c in callers] == ["publish.yml"], (
        f"tier3.yml must be called by publish.yml alone; found {callers}. Each extra "
        "caller is another independent proptest draw on the same artifact."
    )


def test_every_binding_publisher_waits_for_the_core() -> None:
    """The transitive gate the removal relies on.

    If a binding could publish without the core being on crates.io, dropping its own
    Tier 3 would leave it ungated rather than gated upstream.
    """
    for name in ("publish-node.yml", "publish-ruby.yml", "publish-java.yml"):
        document = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8")) or {}
        jobs = document.get("jobs") or {}
        # The exact key, not a substring: `wait-for-core-disabled` would satisfy a
        # containment test, and `wait_for_core` would not be found by one (#898 review).
        assert "wait-for-core" in jobs, (
            f"{name} has no job keyed exactly `wait-for-core`, so it does not inherit "
            f"the core's Tier 3 gate; its jobs are {sorted(jobs)}"
        )


# ---------------------------------------------------------------------------
# Every action is pinned to a SHA, and every pin names the one ref it is
# ---------------------------------------------------------------------------
#
# #1027 pinned every `uses:` to a 40-hex commit. The comments that say which release a
# SHA is were written by hand and drifted at once: the same SHA read `# v7` in one file
# and `# v7.0.0` in another, the space before `#` was one or two by accident, and
# `# v1`, `# v2` and `# release/v1` named refs that move, so the comment stopped being
# true the day upstream tagged again. `Swatinem/rust-cache`'s `# v2` was already false:
# `v2` is `v2.9.2`, and the pinned commit is an untagged one on `master`.
#
# A pin whose comment is wrong is worse than no comment. The comment is what a reviewer
# reads, and what Dependabot rewrites on a bump, so a wrong one hides which code runs.
# The policy, uniform everywhere including the snippets in the docs:
#
# * `uses: owner/repo[/path]@<40-hex>  # <exact ref>`, exactly two spaces, then `# `;
# * the ref is the most specific tag pointing at that SHA (`vX.Y.Z`), resolved with
#   `git ls-remote --tags` and dereferenced through `^{}`;
# * a SHA no tag points at keeps the branch it was taken from, and is listed below;
# * one SHA, one comment, across the whole tree.

GITHUB_DIR = WORKFLOWS.parent

#: A `uses:` line, as a step (`- uses:`) or as a reusable-workflow job (`uses:`).
USES_LINE = re.compile(r"^\s*(?:-\s+)?uses:\s*(?P<ref>\S+)(?P<rest>.*)$")
#: `owner/repo[/path]@<40 hex>`.
SHA_PIN = re.compile(
    r"^(?P<action>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[^@\s]+)?)@(?P<sha>[0-9a-f]{40})$"
)
#: Exactly two spaces, `#`, one space, the ref, nothing after it.
PIN_COMMENT = re.compile(r"^  # (?P<ref>\S+)$")
#: The most specific form a release tag takes here.
EXACT_TAG = re.compile(r"^v\d+\.\d+\.\d+$")

#: Pins that no tag points at, so the comment names the branch they were taken from.
#: Checked 2026-09-23 with `git ls-remote --tags --heads`:
#:
#: * `dtolnay/rust-toolchain` publishes no tags at all; each toolchain is a branch that is
#:   regenerated when `master` moves. The pinned commit was the tip of `stable` and is no
#:   longer reachable from any branch, so it runs the toolchain it was pinned with.
#: * `Swatinem/rust-cache`'s pinned commit is the tip of `master`, newer than `v2.9.2`.
BRANCH_PINS = {
    "dtolnay/rust-toolchain": "stable",
    "Swatinem/rust-cache": "master",
}


def _pin_sources() -> list[Path]:
    """Workflows, composite actions, and the docs that show a workflow snippet."""
    sources = sorted(WORKFLOWS.glob("*.y*ml"))
    sources += sorted((GITHUB_DIR / "actions").rglob("*.y*ml"))
    docs = [p for p in ROOT.glob("*.md") if p.name != "CHANGELOG.md"]
    docs += list((ROOT / "docs").rglob("*.md"))
    docs += [p for p in (ROOT / "bindings").rglob("*.md") if "node_modules" not in p.parts]
    sources += sorted(p for p in set(docs) if not p.is_symlink())
    return sources


def _uses_lines(text: str) -> list[tuple[int, str, str]]:
    """`(line, ref, rest)` for every `uses:` that is code rather than a comment."""
    found = []
    for number, line in enumerate(text.split("\n"), 1):
        if line.lstrip().startswith("#"):
            continue
        if match := USES_LINE.match(line):
            found.append((number, match.group("ref"), match.group("rest")))
    return found


def _pin_problems(name: str, text: str) -> tuple[list[str], dict[str, set[str]]]:
    """Every rule a file breaks, and the comment each SHA carries in it."""
    problems: list[str] = []
    comments: dict[str, set[str]] = {}
    for number, ref, rest in _uses_lines(text):
        where = f"{name}:{number}"
        if ref.startswith(("./", "docker://")):
            continue
        pin = SHA_PIN.match(ref)
        if not pin:
            problems.append(f"{where}: `{ref}` is not pinned to a 40-hex commit SHA")
            continue
        comment = PIN_COMMENT.match(rest)
        if not comment:
            problems.append(f"{where}: `{rest.strip()}` is not exactly two spaces then `# <ref>`")
            continue
        repo = "/".join(pin.group("action").split("/")[:2])
        tag = comment.group("ref")
        if not EXACT_TAG.match(tag) and BRANCH_PINS.get(repo) != tag:
            problems.append(
                f"{where}: `# {tag}` names a moving ref; write the exact tag (vX.Y.Z) that "
                "points at this SHA, or list a tagless branch pin in BRANCH_PINS"
            )
        comments.setdefault(pin.group("sha"), set()).add(tag)
    return problems, comments


def test_there_are_pins_to_check() -> None:
    """Anchored to the tree as it is, so a broken glob cannot pass over nothing."""
    sources = [p.relative_to(ROOT).as_posix() for p in _pin_sources()]
    assert ".github/workflows/ci.yml" in sources
    assert "docs/cli.md" in sources, "the SARIF upload snippet is a pin a user copies"
    total = sum(len(_uses_lines(p.read_text(encoding="utf-8"))) for p in _pin_sources())
    assert total > 100, f"only {total} `uses:` lines found; the scan has lost its files"


def _check_tree(files: list[tuple[str, str]]) -> list[str]:
    """Every rule broken across `(name, text)` files, including one SHA, two comments."""
    problems: list[str] = []
    seen: dict[str, dict[str, list[str]]] = {}
    for name, text in files:
        found, comments = _pin_problems(name, text)
        problems += found
        for sha, tags in comments.items():
            for tag in tags:
                seen.setdefault(sha, {}).setdefault(tag, []).append(name)
    for sha, tags in sorted(seen.items()):
        if len(tags) > 1:
            problems.append(f"{sha[:12]} is commented differently in different places: {tags}")
    return problems


def test_every_uses_line_is_a_sha_pin_with_its_exact_ref() -> None:
    files = [
        (p.relative_to(ROOT).as_posix(), p.read_text(encoding="utf-8")) for p in _pin_sources()
    ]
    problems = _check_tree(files)
    assert not problems, "action pins break the pinning policy:\n  " + "\n  ".join(problems)


@pytest.mark.parametrize("path", _workflows(), ids=lambda p: p.name)
def test_the_line_scan_sees_every_uses_yaml_sees(path: Path) -> None:
    """A quoted or otherwise unusual `uses:` the line scan missed would be unchecked."""
    text = path.read_text(encoding="utf-8")
    document = yaml.safe_load(text) or {}
    parsed = []
    for job in (document.get("jobs") or {}).values():
        if not isinstance(job, dict):
            continue
        if "uses" in job:
            parsed.append(str(job["uses"]))
        parsed += [
            str(step["uses"])
            for step in job.get("steps") or []
            if isinstance(step, dict) and "uses" in step
        ]
    assert sorted(parsed) == sorted(ref for _, ref, _ in _uses_lines(text))


@pytest.mark.parametrize(
    ("line", "complaint"),
    [
        ("      - uses: actions/checkout@v4", "not pinned"),
        ("      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", "two spaces"),
        (
            "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
            "two spaces",
        ),  # noqa: E501
        (
            "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7",
            "moving ref",
        ),  # noqa: E501
        (
            "      - uses: pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33  # release/v1",
            "moving ref",
        ),  # noqa: E501
        (
            "      - uses: Swatinem/rust-cache@f0d9c3887740aee45f6153b24b3a6b815192ec16  # v2",
            "moving ref",
        ),  # noqa: E501
    ],
)
def test_the_pin_gate_can_fail(line: str, complaint: str) -> None:
    problems, _ = _pin_problems("x.yml", line)
    assert len(problems) == 1 and complaint in problems[0], problems


def test_the_pin_gate_passes_the_right_shapes() -> None:
    good = "\n".join(
        [
            "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1",
            "      - uses: dtolnay/rust-toolchain@29eef336d9b2848a0b548edc03f92a220660cdb8  # stable",
            "    uses: ./.github/workflows/tier3.yml",
            "      - uses: docker://alpine:3",
            "  # `uses:` instantiates a fresh job per caller",
        ]
    )
    problems, comments = _pin_problems("x.yml", good)
    assert problems == [] and len(comments) == 2, problems


def test_one_sha_carrying_two_comments_is_reported() -> None:
    sha = "5fda3b95a4ea91299a34e894583c3862153e4b97"
    problems = _check_tree(
        [
            ("a.yml", f"  - uses: actions/setup-python@{sha}  # v7.0.0"),
            ("b.yml", f"  - uses: actions/setup-python@{sha}  # v7.0.1"),
        ]
    )
    assert len(problems) == 1 and "commented differently" in problems[0], problems
