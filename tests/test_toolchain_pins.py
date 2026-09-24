"""The ruff version is written once, in `pyproject.toml`, and CI reads it from there.

`pyproject.toml`'s `dev` extra pins ruff. The *Lint & format* job used to pin it a second
time in `.github/workflows/ci.yml`, and the two copies went wrong in both directions:

* A developer's ruff drifted from CI's. The `.pre-commit-config.yaml` hooks run
  `language: system` — whatever `ruff` is on PATH — so a branch passed
  `ruff format --check .` locally on 0.15.17 and failed CI on 0.16.4, because 0.16 formats
  Python inside Markdown fenced code blocks and 0.15 does not. Nothing about the failure
  pointed at a version difference.
* Dependabot bumped one copy. It updates `pyproject.toml` and cannot see a version inside
  a workflow's `run:` line, so its ruff bump (#985) failed the check that compared the two,
  and would have stayed red until someone copied the number across by hand.

So the lint job reads the pin out of the `dev` extra. Five assertions:

* `ci.yml` writes no ruff version of its own;
* the lint job's install step installs exactly the pinned ruff — its own script, run
  against a stand-in `pip`, so a broken read fails here rather than on a pull request;
* that step stops when there is no pin, rather than installing whatever ruff is newest;
* the pin is at least 0.16 — below that the Markdown blocks stop being formatted and
  nothing fails, which is the silent direction;
* the ruff you are actually running matches it — skipped when ruff is absent, since a
  test runner without the `dev` extra is a legitimate configuration.

The second half applies the same rule to the runtime floors. Each binding's floor is
written in its manifest, in the CI jobs that install the runtime, and in the docs; the
tests at the end of this file fail when those disagree, per binding.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
CI = ROOT / ".github" / "workflows" / "ci.yml"

#: The ci.yml step that installs ruff for the *Lint & format* job.
LINT_STEP = "Install Python lint tools"

#: `ruff==X.Y.Z`. An exact pin is deliberate — see the `dev` extra.
PIN = re.compile(r"ruff==(\d+\.\d+\.\d+)")

runs_the_lint_step = pytest.mark.skipif(
    sys.platform == "win32" or sys.version_info < (3, 11),
    reason="the step is a bash script that reads pyproject.toml with tomllib (3.11+); "
    "CI runs it on ubuntu with Python 3.12",
)


def pinned_in(path: Path) -> list[str]:
    return PIN.findall(path.read_text(encoding="utf-8"))


def sole_pin(path: Path) -> str:
    """The one version `path` pins, or a failure that says what is wrong.

    Indexing `pinned_in(...)[0]` raises `IndexError` when the pin is removed or the regex
    stops matching, and pytest does not guarantee which test runs first — so the clear
    message is not reliably the one a reader sees. This makes every test in the file fail
    the same legible way.
    """
    found = pinned_in(path)
    assert found, (
        f"{path.name} no longer pins ruff exactly. An exact pin is deliberate: a floating "
        "one lets a local gate and CI disagree, which is what this file exists to stop."
    )
    assert len(set(found)) == 1, f"{path.name} pins ruff more than once: {found}"
    return found[0]


def lint_install_script() -> str:
    workflow = yaml.safe_load(CI.read_text(encoding="utf-8"))
    found = [
        step["run"]
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if step.get("name") == LINT_STEP
    ]
    assert len(found) == 1, f"ci.yml has {len(found)} steps named {LINT_STEP!r}, not one"
    return found[0]


def run_lint_step(cwd: Path, stubs: Path) -> subprocess.CompletedProcess[str]:
    """Run the step as Actions does, with a `pip` that prints its arguments instead."""
    for name, body in (
        ("pip", 'printf "%s\\n" "$@"'),
        ("python", f'exec "{sys.executable}" "$@"'),
    ):
        stub = stubs / name
        stub.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
        stub.chmod(0o755)
    return subprocess.run(  # noqa: S603 — fixed argv; the script is ci.yml's own
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", lint_install_script()],
        cwd=cwd,
        env={**os.environ, "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_ci_writes_no_ruff_version_of_its_own() -> None:
    """A second copy is the one Dependabot cannot see."""
    assert not pinned_in(CI), (
        f"ci.yml pins ruff itself ({pinned_in(CI)}). Dependabot bumps pyproject.toml and "
        "cannot see a version inside a workflow, so every ruff bump then goes red until "
        "someone copies the number across. Read it from the `dev` extra instead."
    )


@runs_the_lint_step
def test_the_lint_step_installs_the_pinned_ruff(tmp_path: Path) -> None:
    result = run_lint_step(ROOT, tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["install", f"ruff=={sole_pin(PYPROJECT)}", "mypy"]


@runs_the_lint_step
def test_the_lint_step_stops_when_there_is_no_pin(tmp_path: Path) -> None:
    """Without the pin, `pip install "" mypy` or a bare `ruff` would be the quiet outcome."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[project]\nname = "x"\n\n[project.optional-dependencies]\ndev = ["maturin"]\n',
        encoding="utf-8",
    )
    result = run_lint_step(project, tmp_path)
    assert result.returncode != 0, result.stdout
    assert result.stdout == "", "pip ran although the dev extra pins no ruff"


def test_ruff_is_pinned_at_least_to_the_version_that_formats_markdown() -> None:
    """0.16 formats Python inside Markdown fences; 0.15 does not.

    This repository's docs carry executable Python in fenced blocks, and several gates
    read those blocks. Going back below 0.16 would stop formatting them without failing
    anything, which is the silent direction.
    """
    major, minor, _ = (int(part) for part in sole_pin(PYPROJECT).split("."))
    assert (major, minor) >= (0, 16), (
        "ruff is pinned below 0.16, which does not format Python inside Markdown fences"
    )


@pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff is not installed")
def test_the_installed_ruff_matches_the_pin() -> None:
    """The one that catches a stale local environment before a pull request does."""
    pinned = sole_pin(PYPROJECT)
    reported = subprocess.run(
        ["ruff", "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    installed = reported.split()[-1]
    assert installed == pinned, (
        f"ruff on PATH is {installed}, the repository pins {pinned}. The pre-commit hooks "
        f"run `language: system`, so they are using {installed} too. Install the pin: "
        "`uv pip install ruff==" + pinned + "` (or `pip install -e '.[dev]'`)."
    )


# ---------------------------------------------------------------------------
# Platform floors: the manifest, the CI matrix and the docs state one number
# ---------------------------------------------------------------------------
#
# The README and package.json claimed Node.js >= 14 more than three years after Node 14
# reached end of life, while CI tested 20 and 22. The Ruby gem claimed 3.1, eighteen
# months past its end of life. Nothing compared the places a floor is written, so each
# drifted on its own.
#
# The policy: the declared floor is the oldest version upstream still supports *and* CI
# tests, and CI's lowest entry is that floor. Whether a version is still supported is a
# fact about the calendar, which a deterministic test cannot check; the dated notes next
# to each matrix say when it was last verified and against what. What is checked here is
# that the manifest, every CI job that installs the runtime, and every page that states a
# floor agree, so raising one without the others fails.

WORKFLOWS = ROOT / ".github" / "workflows"

#: `${{ matrix.node }}` and friends.
MATRIX_REF = re.compile(r"^\$\{\{\s*matrix\.([A-Za-z0-9_-]+)\s*\}\}$")
#: The JSON arrays inside a `fromJSON('[...]')` matrix expression.
JSON_ARRAY = re.compile(r"fromJSON\('(\[[^']*\])'\)")


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _matrix_values(job: dict, axis: str) -> list[str]:
    """Every value a job's matrix axis can take, including both arms of a `fromJSON`."""
    raw = ((job.get("strategy") or {}).get("matrix") or {}).get(axis)
    if isinstance(raw, list):
        return [str(v) for v in raw]
    if isinstance(raw, str):
        return [str(v) for arm in JSON_ARRAY.findall(raw) for v in json.loads(arm)]
    return []


def _setup_versions(action: str, key: str) -> list[tuple[str, str, str]]:
    """`(workflow, job, version)` for every step that runs `action` with `key` set."""
    found = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for name, job in (document.get("jobs") or {}).items():
            if not isinstance(job, dict):
                continue
            for step in job.get("steps") or []:
                if not isinstance(step, dict) or not str(step.get("uses", "")).startswith(action):
                    continue
                value = str((step.get("with") or {}).get(key, "")).strip()
                if not value:
                    continue
                ref = MATRIX_REF.match(value)
                versions = _matrix_values(job, ref.group(1)) if ref else [value]
                assert versions, f"{path.name}:{name} reads {value} from an empty matrix"
                found += [(path.name, name, v) for v in versions]
    return found


def _job(workflow: str, job: str) -> dict:
    document = yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8")) or {}
    return document["jobs"][job]


def _floor_from(path: str, pattern: str) -> str:
    match = re.search(pattern, (ROOT / path).read_text(encoding="utf-8"), re.MULTILINE)
    assert match, f"{path} no longer declares a floor this gate can read ({pattern})"
    return match.group(1)


def _docs() -> list[Path]:
    """Every Markdown page a user reads. Symlinks are skipped so none is read twice.

    The changelog and its archive under `docs/changelog/` are history: an old release's
    entry naming the floor it had then is true, so they are not read.
    """
    archive = ROOT / "docs" / "changelog"
    pages = [p for p in ROOT.glob("*.md") if p.name != "CHANGELOG.md"]
    pages += [p for p in (ROOT / "docs").rglob("*.md") if archive not in p.parents]
    pages += [p for p in (ROOT / "bindings").rglob("*.md") if "node_modules" not in p.parts]
    return sorted(p for p in set(pages) if not p.is_symlink())


#: Per binding: how prose states its floor, and the pages that must state it.
DOC_FLOORS: dict[str, tuple[tuple[re.Pattern[str], ...], tuple[str, ...]]] = {
    "python": (
        (re.compile(r"\bPython (\d+\.\d+)\+"),),
        ("README.md", "docs/index.md", "docs/python/getting-started.md", "CONTRIBUTING.md"),
    ),
    "node": (
        (re.compile(r"\bNode(?:\.js)? (\d+)\+"),),
        (
            "README.md",
            "docs/index.md",
            "docs/node/getting-started.md",
            "bindings/node/README.md",
        ),
    ),
    "ruby": (
        (
            re.compile(r"\bRuby (\d+\.\d+)\+"),
            re.compile(r"\bRuby >= ?(\d+\.\d+)"),
            re.compile(r"\bRuby (\d+\.\d+) through\b"),
            re.compile(r"\bBelow (\d+\.\d+) the gem\b"),
        ),
        (
            "README.md",
            "docs/index.md",
            "docs/ruby/getting-started.md",
            "bindings/ruby/README.md",
        ),
    ),
    "java": (
        (re.compile(r"\bJava (\d+)\+"), re.compile(r"\bJDK (\d+) or newer\b")),
        (
            "README.md",
            "docs/index.md",
            "docs/java/getting-started.md",
            "bindings/java/README.md",
        ),
    ),
}


def _python_floor() -> str:
    return _floor_from("pyproject.toml", r'^requires-python\s*=\s*">=\s*(\d+\.\d+)"')


def _node_floor() -> str:
    engines = json.loads((ROOT / "bindings/node/package.json").read_text(encoding="utf-8"))
    match = re.fullmatch(r">=\s*(\d+)", engines["engines"]["node"])
    assert match, f"package.json engines.node is {engines['engines']['node']!r}, not '>= N'"
    return match.group(1)


def _ruby_floor() -> str:
    return _floor_from(
        "bindings/ruby/disarm.gemspec", r'required_ruby_version\s*=\s*">=\s*(\d+\.\d+)(?:\.0)?"'
    )


def _java_floor() -> str:
    return _floor_from(
        "bindings/java/disarm-java/build.gradle.kts", r"JavaLanguageVersion\.of\((\d+)\)"
    )


FLOORS = {"python": _python_floor, "node": _node_floor, "ruby": _ruby_floor, "java": _java_floor}


def _doc_claims(binding: str, text: str) -> list[str]:
    patterns, _ = DOC_FLOORS[binding]
    return [claim for pattern in patterns for claim in pattern.findall(text)]


@pytest.mark.parametrize("binding", sorted(DOC_FLOORS))
def test_every_doc_states_the_declared_floor(binding: str) -> None:
    floor = FLOORS[binding]()
    _, required = DOC_FLOORS[binding]
    wrong, silent = [], []
    for path in _docs():
        rel = path.relative_to(ROOT).as_posix()
        claims = _doc_claims(binding, path.read_text(encoding="utf-8"))
        wrong += [f"{rel} says {c}" for c in claims if c != floor]
        if rel in required and not claims:
            silent.append(rel)
    assert not wrong, f"the {binding} floor is {floor}, but:\n  " + "\n  ".join(wrong)
    assert not silent, f"these pages no longer state the {binding} floor: {silent}"


@pytest.mark.parametrize(
    ("binding", "stale", "claims"),
    [
        ("node", "npm install disarm      # Node.js 14+", ["14"]),
        ("node", "Requires Node 14+.", ["14"]),
        ("ruby", "Requires Ruby >= 3.1. Platform gems ship for Ruby 3.1 through 4.0", ["3.1"] * 2),
        ("ruby", "Rust toolchain. Below 3.1 the gem does not install at all.", ["3.1"]),
        ("python", "pip install disarm      # Python 3.9+", ["3.9"]),
        ("java", "| Java 17+ / Kotlin |", ["17"]),
        ("python", "CPython 3.12 ships Unicode 15.0.0", []),
    ],
)
def test_the_doc_patterns_can_fail(binding: str, stale: str, claims: list[str]) -> None:
    """The stale forms this gate was written against are recognised; others are not."""
    assert _doc_claims(binding, stale) == claims


def test_python_ci_floor_is_the_declared_floor() -> None:
    floor = _python_floor()
    used = _setup_versions("actions/setup-python", "python-version")
    below = [u for u in used if _version_key(u[2]) < _version_key(floor)]
    assert not below, f"CI installs a Python below requires-python >= {floor}: {below}"
    assert _matrix_values(_job("smoke.yml", "artifacts"), "python")[0] == floor, (
        "smoke.yml's `artifacts` job is where CI exercises the shipped wheel and sdist on "
        f"the floor; its first python entry must be requires-python's {floor}"
    )
    pyproject = PYPROJECT.read_text(encoding="utf-8")
    classifiers = re.findall(r"Programming Language :: Python :: (3\.\d+)", pyproject)
    assert min(classifiers, key=_version_key) == floor, f"lowest classifier is not {floor}"
    assert f'target-version = "py{floor.replace(".", "")}"' in pyproject, "ruff target"
    assert f'pythonVersion = "{floor}"' in pyproject, "type-checker target"
    publish = (WORKFLOWS / "publish.yml").read_text(encoding="utf-8")
    assert f"--interpreter {floor}" in publish, "publish.yml builds abi3 against the floor"


def test_node_ci_floor_is_the_declared_floor() -> None:
    floor = _node_floor()
    lock = json.loads((ROOT / "bindings/node/package-lock.json").read_text(encoding="utf-8"))
    assert lock["packages"][""]["engines"]["node"] == f">= {floor}", "package-lock engines"
    matrix = _matrix_values(_job("ci.yml", "node"), "node")
    assert matrix and min(matrix, key=_version_key) == floor, (
        f"ci.yml's node matrix {matrix} must start at the engines floor {floor}"
    )
    used = _setup_versions("actions/setup-node", "node-version")
    assert {u[0] for u in used} >= {"ci.yml", "publish-node.yml", "dependency-audit.yml"}, used
    below = [u for u in used if _version_key(u[2]) < _version_key(floor)]
    assert not below, f"CI runs a Node below the engines floor {floor}: {below}"


def test_ruby_ci_floor_is_the_declared_floor() -> None:
    floor = _ruby_floor()
    rubocop = (ROOT / "bindings/ruby/.rubocop.yml").read_text(encoding="utf-8")
    assert re.search(rf"^\s*TargetRubyVersion:\s*{re.escape(floor)}\s*$", rubocop, re.M), (
        f"RuboCop's TargetRubyVersion must be the gemspec floor {floor}"
    )
    raw = str(_job("ci.yml", "ruby")["strategy"]["matrix"]["ruby"])
    pr_arm, full_arm = (json.loads(arm) for arm in JSON_ARRAY.findall(raw))
    assert pr_arm == [floor], f"a pull request runs the floor alone; ci.yml runs {pr_arm}"
    assert full_arm[0] == floor, f"ci.yml's full Ruby range {full_arm} must start at {floor}"
    publish = _job("publish-ruby.yml", "test")["strategy"]["matrix"]["ruby"]
    assert publish == full_arm, f"publish-ruby.yml tests {publish}, ci.yml tests {full_arm}"
    cross = [
        str(step["with"]["ruby-versions"]).split(",")
        for step in _job("publish-ruby.yml", "cross-gems")["steps"]
        if str(step.get("uses", "")).startswith("oxidize-rb/actions/cross-gem")
    ]
    assert cross == [full_arm], f"cross-gem ABIs {cross} must be the tested range {full_arm}"
    used = _setup_versions("oxidize-rb/actions/setup-ruby-and-rust", "ruby-version")
    used += _setup_versions("ruby/setup-ruby", "ruby-version")
    below = [u for u in used if _version_key(u[2]) < _version_key(floor)]
    assert not below, f"CI runs a Ruby below the gemspec floor {floor}: {below}"


def test_java_ci_floor_is_the_declared_floor() -> None:
    floor = _java_floor()
    kotlin = (ROOT / "bindings/java/disarm-kotlin/build.gradle.kts").read_text(encoding="utf-8")
    assert f"jvmToolchain({floor})" in kotlin, f"the Kotlin module must target JDK {floor} too"
    matrix = _matrix_values(_job("ci.yml", "java"), "java")
    assert matrix and min(matrix, key=_version_key) == floor, (
        f"ci.yml's java matrix {matrix} must start at the Gradle toolchain floor {floor}"
    )
    used = _setup_versions("actions/setup-java", "java-version")
    below = [u for u in used if _version_key(u[2]) < _version_key(floor)]
    assert not below, f"CI builds on a JDK below the toolchain floor {floor}: {below}"


#: Versions upstream has already retired, with the date and the source it was read from.
#: Deterministic on purpose: the test never consults the clock, so it cannot turn red on a
#: pull request that changed nothing. It stops a floor from going *back* to a line known
#: to be dead; moving forward when the next line retires is a change someone makes, and
#: that change adds the line here too.
#:
#: Verified 2026-09-23 against nodejs/Release `schedule.json`, ruby-lang.org
#: `_data/branches.yml`, python/peps `release_management/python-releases.toml` and
#: Oracle's Java SE Support Roadmap. Python 3.10 is next: end of life 2026-10-01.
KNOWN_EOL: dict[str, dict[str, str]] = {
    "node": {"14": "2023-04-30", "16": "2023-09-11", "18": "2025-04-30", "20": "2026-04-30"},
    "ruby": {"3.0": "2024-04-23", "3.1": "2025-03-26", "3.2": "2026-04-01"},
    "python": {"3.8": "2024-10-07", "3.9": "2025-10-31"},
    # Oracle Premier Support; 11 and 17 remain only under paid Extended Support.
    "java": {"11": "2023-09", "17": "2026-09"},
}


@pytest.mark.parametrize("binding", sorted(KNOWN_EOL))
def test_no_floor_is_a_version_upstream_has_retired(binding: str) -> None:
    floor = FLOORS[binding]()
    retired = KNOWN_EOL[binding]
    newest_dead = max(retired, key=_version_key)
    assert _version_key(floor) > _version_key(newest_dead), (
        f"the {binding} floor is {floor}, but {newest_dead} reached end of life on "
        f"{retired[newest_dead]}; raise the floor to the oldest supported line in the "
        "manifest, the CI matrix and the docs together"
    )
