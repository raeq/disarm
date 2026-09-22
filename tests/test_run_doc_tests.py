"""`scripts/run_doc_tests.py` runs one pytest process per page, and each must be serial.

The runner already parallelises across pages — up to eight page processes at once. Each
of those inherited `-n auto` from `addopts` once #997 made it the default, so every page
also started a full set of xdist workers to run a handful of examples: 42 pages x (1 + 4)
interpreters, on a four-core box. Measured on the review of #997: 34.8s against 5.8s
with `-n 0`.
"""

from __future__ import annotations

import importlib.util
import itertools
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "run_doc_tests", ROOT / "scripts" / "run_doc_tests.py"
)
assert _spec and _spec.loader
run_doc_tests = importlib.util.module_from_spec(_spec)
sys.modules["run_doc_tests"] = run_doc_tests
_spec.loader.exec_module(run_doc_tests)


def _argv_for(monkeypatch: pytest.MonkeyPatch, user_argv: list[str]) -> list[str]:
    seen: list[list[str]] = []

    def fake_run(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(run_doc_tests.subprocess, "run", fake_run)
    rel = run_doc_tests._load_allowlist()[0]
    _page, code, _output = run_doc_tests._run_one(rel, user_argv)
    assert code == 0
    assert len(seen) == 1
    return seen[0]


def test_each_page_runs_without_xdist_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    argv = _argv_for(monkeypatch, [])
    pairs = list(itertools.pairwise(argv))
    assert ("-n", "0") in pairs, argv


def test_it_is_turned_off_with_n_0_not_by_unloading_the_plugin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`-p no:xdist` would leave `addopts`' `-n auto` as an unrecognised option."""
    argv = _argv_for(monkeypatch, [])
    assert "no:xdist" not in argv, argv


def test_a_callers_own_n_still_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """Forwarded arguments come after ours, and pytest honours the last `-n`."""
    argv = _argv_for(monkeypatch, ["-n", "2", "-k", "slug"])
    assert argv[-4:] == ["-n", "2", "-k", "slug"], argv
    assert argv.index("0") < len(argv) - 4, argv


def test_the_default_job_count_is_the_usable_cores(monkeypatch: pytest.MonkeyPatch) -> None:
    """The affinity mask, not the host: a pinned or containerised run gets what it has."""
    monkeypatch.delenv("DISARM_DOC_TEST_JOBS", raising=False)
    monkeypatch.setattr(os, "cpu_count", lambda: 64)
    monkeypatch.setattr(os, "sched_getaffinity", lambda _pid: {0, 1}, raising=False)
    assert run_doc_tests._jobs(40) == 2
