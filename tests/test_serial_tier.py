"""The `serial` tier must actually run somewhere (#997 review).

A few tests measure wall-clock parallelism — #70's GIL-release guard proves the GIL is
released by finishing two batches on two threads faster than one thread can. Under
`-n auto` every core already has a worker on it, so there is no idle core for the second
thread and the measurement is of the box being full. #997 made `-n auto` the default and
the guard answered by skipping itself, which is correct locally and meant CI never ran it
at all: `2 skipped`, on every run, in a log nobody reads for skips.

So those tests carry `@pytest.mark.serial`, the parallel run deselects them, and CI runs
them in a step of their own with `-n 0`. These tests hold the three pieces together, since
losing any one of them puts the guard back to running nowhere without a single failure.
"""

from __future__ import annotations

import shlex
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CI = ROOT / ".github" / "workflows" / "ci.yml"


def _test_job_pytest_commands() -> list[list[str]]:
    """Every `pytest` invocation in the CI job that `All checks passed` requires, split."""
    workflow = yaml.safe_load(CI.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    assert "test" in jobs["all-ok"]["needs"], "the rollup no longer requires the test job"
    commands = []
    for step in jobs["test"]["steps"]:
        for line in str(step.get("run", "")).splitlines():
            # Filter before splitting: other steps' shell lines (a trailing `\`
            # continuation, for one) are not valid on their own.
            if line.strip().startswith("pytest "):
                commands.append(shlex.split(line, comments=True))
    return commands


def _option(argv: list[str], flag: str) -> str | None:
    """The value of the last `flag` in `argv` — the one pytest honours."""
    value = None
    for i, arg in enumerate(argv):
        if arg == flag and i + 1 < len(argv):
            value = argv[i + 1]
        elif arg.startswith(f"{flag}="):
            value = arg[len(flag) + 1 :]
    return value


def test_the_marker_is_registered(pytestconfig: pytest.Config) -> None:
    """Read from pytest's parsed config, not the TOML: `tomllib` is 3.11+, the floor 3.10."""
    markers = pytestconfig.getini("markers")
    assert any(m.split(":", 1)[0].strip() == "serial" for m in markers), markers


def test_the_default_run_deselects_it(pytestconfig: pytest.Config) -> None:
    """Bare `pytest` is `-n auto`, which is exactly where these cannot be measured."""
    addopts = pytestconfig.getini("addopts")
    assert "not serial" in (_option(addopts, "-m") or ""), addopts


def test_ci_parallel_run_deselects_it() -> None:
    """CI's `-m` replaces the one in `addopts`, so it has to say `not serial` itself."""
    main = [argv for argv in _test_job_pytest_commands() if "--cov=disarm" in argv]
    assert len(main) == 1, main
    assert "not serial" in (_option(main[0], "-m") or ""), main[0]


def test_ci_runs_it_serially() -> None:
    serial = [argv for argv in _test_job_pytest_commands() if _option(argv, "-m") == "serial"]
    assert len(serial) == 1, _test_job_pytest_commands()
    assert _option(serial[0], "-n") == "0", serial[0]
