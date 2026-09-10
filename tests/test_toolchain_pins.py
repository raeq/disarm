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
"""

from __future__ import annotations

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
