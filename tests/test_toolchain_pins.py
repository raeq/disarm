"""The ruff version is written in two files, and nothing checked they agree.

`pyproject.toml`'s `dev` extra and `.github/workflows/ci.yml` each pin ruff, and the
`.pre-commit-config.yaml` hooks run `language: system` — whatever `ruff` is on PATH. So a
developer's ruff can be older than CI's while every local gate passes, and the divergence
only shows up as a red *Lint & format* job on a pull request.

That happened: a branch passed `ruff format --check .` locally on 0.15.17 and failed CI on
0.16.4, because 0.16 formats Python inside Markdown fenced code blocks and 0.15 does not.
Nothing about the failure pointed at a version difference.

Two assertions, in the order they help:

* the two pins agree — a pure file comparison, so it runs anywhere;
* the ruff you are actually running matches them — skipped when ruff is absent, since a
  test runner without the `dev` extra is a legitimate configuration.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
CI = ROOT / ".github" / "workflows" / "ci.yml"

#: `ruff==X.Y.Z`, in either file. An exact pin is deliberate — see the `dev` extra.
PIN = re.compile(r"ruff==(\d+\.\d+\.\d+)")


def pinned_in(path: Path) -> list[str]:
    return PIN.findall(path.read_text(encoding="utf-8"))


def test_the_two_ruff_pins_agree() -> None:
    """One version, written twice. They have to say the same thing."""
    in_pyproject = pinned_in(PYPROJECT)
    in_ci = pinned_in(CI)
    assert in_pyproject, "pyproject.toml no longer pins ruff exactly"
    assert in_ci, ".github/workflows/ci.yml no longer pins ruff exactly"
    assert len(set(in_pyproject + in_ci)) == 1, (
        f"ruff is pinned to different versions: pyproject.toml {in_pyproject}, "
        f"ci.yml {in_ci}. A local gate then passes on one version and CI fails on the "
        "other, and nothing about the failure says so."
    )


def test_ruff_is_pinned_at_least_to_the_version_that_formats_markdown() -> None:
    """0.16 formats Python inside Markdown fences; 0.15 does not.

    This repository's docs carry executable Python in fenced blocks, and several gates
    read those blocks. Going back below 0.16 would stop formatting them without failing
    anything, which is the silent direction.
    """
    major, minor, _ = (int(part) for part in pinned_in(PYPROJECT)[0].split("."))
    assert (major, minor) >= (0, 16), (
        "ruff is pinned below 0.16, which does not format Python inside Markdown fences"
    )


@pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff is not installed")
def test_the_installed_ruff_matches_the_pin() -> None:
    """The one that catches a stale local environment before a pull request does."""
    pinned = pinned_in(PYPROJECT)[0]
    reported = subprocess.run(
        ["ruff", "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    installed = reported.split()[-1]
    assert installed == pinned, (
        f"ruff on PATH is {installed}, the repository pins {pinned}. The pre-commit hooks "
        f"run `language: system`, so they are using {installed} too. Install the pin: "
        "`uv pip install ruff==" + pinned + "` (or `pip install -e '.[dev]'`)."
    )
