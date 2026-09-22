"""The nightly Hypothesis run must explore different input each night.

That is the stated reason `nightly-hypothesis.yml` exists, and it did not happen, twice
over:

* `--hypothesis-seed=random` is not a request for a random seed. The plugin tries
  `int(seed)`, fails, and uses the *string* `"random"` as the seed — the same one every
  night.
* And on GitHub Actions it would not have mattered what seed it passed. Hypothesis sees
  `CI` and loads its built-in `ci` profile, which sets `derandomize=True`, and a
  derandomized test seeds itself from its own source and ignores `--hypothesis-seed`.

Measured on the review of #997: under `CI=true`, `--hypothesis-seed=1`, `=2` and
`=random` drew identical examples. So the workflow now generates a seed, logs it, and
runs under a `nightly` profile — `ci`'s settings minus `derandomize` — registered in
`tests/conftest.py`.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import yaml
from hypothesis import settings

ROOT = Path(__file__).resolve().parent.parent
NIGHTLY = ROOT / ".github" / "workflows" / "nightly-hypothesis.yml"


def _pytest_argv() -> list[str]:
    workflow = yaml.safe_load(NIGHTLY.read_text(encoding="utf-8"))
    (step,) = [s for s in workflow["jobs"]["hypothesis"]["steps"] if s.get("id") == "hypothesis"]
    lines = [ln for ln in step["run"].splitlines() if ln.strip().startswith("pytest ")]
    assert len(lines) == 1, lines
    return shlex.split(lines[0].split("|")[0], comments=True)


def test_the_workflow_passes_a_generated_seed_not_a_literal() -> None:
    seeds = [a.split("=", 1)[1] for a in _pytest_argv() if a.startswith("--hypothesis-seed=")]
    assert len(seeds) == 1, _pytest_argv()
    assert re.fullmatch(r"\$\{?\w+\}?", seeds[0]), (
        f"--hypothesis-seed={seeds[0]} is a fixed seed; a non-integer is used as a string"
    )


def test_the_workflow_runs_under_a_profile_that_honours_the_seed() -> None:
    assert "--hypothesis-profile=nightly" in _pytest_argv(), _pytest_argv()


def test_the_nightly_profile_is_not_derandomized() -> None:
    profile = settings.get_profile("nightly")
    assert profile.derandomize is False
    assert profile.print_blob is True, "a failure's reproduction blob belongs in the log"


_PROBE = """
import os
from hypothesis import given, settings, strategies as st

@settings(max_examples=5, database=None)
@given(st.integers())
def test_draw(x):
    with open(os.environ["PROBE_OUT"], "a") as fh:
        fh.write(f"{x}\\n")
"""


def _draws(tmp_path: Path, seed: str) -> list[str]:
    """Run a five-example property as the nightly does, under CI, and return its draws."""
    out = tmp_path / f"draws-{seed}-{len(list(tmp_path.iterdir()))}.txt"
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env |= {
        "CI": "true",
        "GITHUB_ACTIONS": "true",
        "PROBE_OUT": str(out),
        "PYTHONPATH": str(ROOT / "tests"),
    }
    result = subprocess.run(  # noqa: S603 — fixed argv, no shell
        [
            sys.executable,
            "-m",
            "pytest",
            str(tmp_path / "test_probe.py"),
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "conftest",  # tests/conftest.py, where the profile is registered
            "--rootdir",
            str(tmp_path),
            "--hypothesis-profile=nightly",
            f"--hypothesis-seed={seed}",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return out.read_text(encoding="utf-8").split()


def test_under_ci_different_seeds_draw_different_examples(tmp_path: Path) -> None:
    """The behaviour, not the configuration: what the ci profile alone gets wrong."""
    (tmp_path / "test_probe.py").write_text(_PROBE, encoding="utf-8")
    first, second = _draws(tmp_path, "1"), _draws(tmp_path, "2")
    assert first != second, "the seed is being ignored — derandomized?"
    assert _draws(tmp_path, "1") == first, "a logged seed must reproduce its run"
