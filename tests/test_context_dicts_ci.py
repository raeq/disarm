"""The context-dictionary tests must run somewhere (#1151).

`tests/test_context_{arabic,hebrew,persian}.py` and one test in
`tests/test_register_replacements.py` skip when their dictionary is absent. The
dictionaries are gitignored and `scripts/bootstrap_dicts.sh` builds them, and no workflow
ran it, so all 29 skipped on every CI run, and Hebrew's ran nowhere. The test step's log
counted them without naming them.

CI now builds what it can build honestly. Persian needs no corpus, and Hebrew's corpus is a
pinned public commit, so both come from the real builders and are held to their pins. Arabic
needs Kaggle credentials, which never reach a pull request from a fork, so its dictionary
comes from a small fixture in this repository, built by the real builder. These tests hold
those pieces together, since losing any one of them puts the tests back to skipping without
a single failure.
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import conftest
import pytest
import yaml
from conftest import REQUIRE_CONTEXT_DICTS, has_context_dict

ROOT = Path(__file__).resolve().parent.parent
BOOTSTRAP = ROOT / "scripts" / "bootstrap_dicts.sh"
ARABIC_FIXTURE = ROOT / "tests" / "fixtures" / "context_dicts" / "arabic.txt"
JOB = "context-dictionaries"
#: The modules whose tests skip without a dictionary, and how many each one holds.
GUARDED = {
    "tests/test_context_arabic.py": 8,
    "tests/test_context_hebrew.py": 6,
    "tests/test_context_persian.py": 14,
}


def _pin(name: str) -> str:
    pattern = rf'^{name}_DICT_SHA256="([0-9a-f]{{64}})"$'
    found = re.search(pattern, BOOTSTRAP.read_text(encoding="utf-8"), re.MULTILINE)
    assert found, f"{BOOTSTRAP.name} has no 64-digit pin for {name}"
    return found.group(1)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_module(module: str, dict_dir: Path) -> subprocess.CompletedProcess[str]:
    """Run one guarded module against one directory of dictionaries, as CI's step does."""
    env = {**os.environ, "DISARM_DICT_DIR": str(dict_dir), REQUIRE_CONTEXT_DICTS: "1"}
    return subprocess.run(  # noqa: S603 - fixed argv; the module is this repository's own
        [sys.executable, "-m", "pytest", module, "-n", "0", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def _ci() -> dict:
    return yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))


def _job() -> dict:
    return _ci()["jobs"][JOB]


def _step_running(fragment: str) -> dict:
    found = [s for s in _job()["steps"] if fragment in str(s.get("run", ""))]
    assert len(found) == 1, f"{len(found)} steps of {JOB} run {fragment!r}, not one"
    return found[0]


# --- the guard ---------------------------------------------------------------


def _with_answer(monkeypatch: pytest.MonkeyPatch, error: Exception | None) -> None:
    def transliterate(_word: str, **_kwargs: object) -> str:
        if error is not None:
            raise error
        return "kataba"

    monkeypatch.setattr(conftest, "transliterate", transliterate)


MISSING = ValueError("context dictionary for Arabic not found; run bootstrap_dicts.sh")


def test_a_dictionary_that_answers_is_available(monkeypatch):
    monkeypatch.setenv(REQUIRE_CONTEXT_DICTS, "1")
    _with_answer(monkeypatch, None)
    assert has_context_dict("x", lang="ar") is True


def test_a_missing_dictionary_skips_on_a_contributors_machine(monkeypatch):
    monkeypatch.delenv(REQUIRE_CONTEXT_DICTS, raising=False)
    _with_answer(monkeypatch, MISSING)
    assert has_context_dict("x", lang="ar") is False


def test_a_missing_dictionary_is_an_error_where_it_is_required(monkeypatch):
    """Raised at import, so the module fails to collect and the step goes red."""
    monkeypatch.setenv(REQUIRE_CONTEXT_DICTS, "1")
    _with_answer(monkeypatch, MISSING)
    with pytest.raises(ValueError, match="not found"):
        has_context_dict("x", lang="ar")


def test_a_real_error_is_never_read_as_a_missing_dictionary(monkeypatch):
    monkeypatch.delenv(REQUIRE_CONTEXT_DICTS, raising=False)
    _with_answer(monkeypatch, ValueError("corrupt dictionary"))
    with pytest.raises(ValueError, match="corrupt"):
        has_context_dict("x", lang="ar")


# --- what CI can build -------------------------------------------------------


def test_the_persian_pin_is_what_the_builder_produces(tmp_path):
    """The pin dated from v0.5.0, so `bootstrap_dicts.sh persian` stopped on a mismatch."""
    out = tmp_path / "persian_dict.bin"
    subprocess.run(  # noqa: S603 - fixed argv; the builder is this repository's own
        [sys.executable, "scripts/build_persian_dict.py", "-o", str(out)],
        cwd=ROOT,
        capture_output=True,
        check=True,
        timeout=60,
    )
    assert _sha256(out) == _pin("PERSIAN")


def test_the_persian_dictionary_answers_the_persian_tests(tmp_path):
    subprocess.run(  # noqa: S603 - fixed argv; the builder is this repository's own
        [sys.executable, "scripts/build_persian_dict.py", "-o", str(tmp_path / "persian_dict.bin")],
        cwd=ROOT,
        capture_output=True,
        check=True,
        timeout=60,
    )
    run = _run_module("tests/test_context_persian.py", tmp_path)
    assert f"{GUARDED['tests/test_context_persian.py']} passed" in run.stdout, run.stdout


def test_the_arabic_fixture_answers_the_arabic_tests(tmp_path):
    """Real builder, small input: no Kaggle credentials, and nothing vendored from Tashkeela."""
    subprocess.run(  # noqa: S603 - fixed argv; the builder is this repository's own
        [
            sys.executable,
            "scripts/build_arabic_dict.py",
            str(ARABIC_FIXTURE),
            "-o",
            str(tmp_path / "arabic_dict.bin"),
            "--min-freq",
            "1",
        ],
        cwd=ROOT,
        capture_output=True,
        check=True,
        timeout=60,
    )
    run = _run_module("tests/test_context_arabic.py", tmp_path)
    assert f"{GUARDED['tests/test_context_arabic.py']} passed" in run.stdout, run.stdout


# --- the workflow ------------------------------------------------------------


def test_ci_builds_each_dictionary_with_the_real_builder():
    run = _step_running("bootstrap_dicts.sh persian")["run"]
    assert "bootstrap_dicts.sh hebrew" in run
    assert "scripts/build_arabic_dict.py tests/fixtures/context_dicts/arabic.txt" in run


def test_ci_needs_no_credentials_to_build_them():
    """A secret never reaches a pull request from a fork, so the step would skip there."""
    step = _step_running("bootstrap_dicts.sh persian")
    assert "kaggle" not in str(step).lower()
    assert "secrets." not in str(step)


def test_ci_runs_every_guarded_module_where_a_missing_dictionary_fails():
    step = _step_running("tests/test_context_hebrew.py")
    assert step["env"][REQUIRE_CONTEXT_DICTS]
    assert step["env"]["DISARM_DICT_DIR"]
    argv = shlex.split(step["run"])
    for module in (*GUARDED, "tests/test_register_replacements.py"):
        assert module in argv, argv


def test_ci_builds_them_before_it_runs_them():
    steps = _job()["steps"]
    build = steps.index(_step_running("bootstrap_dicts.sh persian"))
    run = steps.index(_step_running("tests/test_context_hebrew.py"))
    assert build < run


def test_the_hebrew_cache_key_covers_what_decides_the_bytes():
    """The corpus is 3.1 GB and the build takes six minutes, so the output is what is cached."""
    caches = [s for s in _job()["steps"] if "actions/cache@" in s.get("uses", "")]
    assert len(caches) == 1, caches
    assert caches[0]["with"]["path"] == "data/hebrew_dict.bin"
    key = caches[0]["with"]["key"]
    assert "scripts/bootstrap_dicts.sh" in key
    assert "scripts/build_hebrew_dict.py" in key
    assert "scripts/context_words.py" in key


def test_a_cached_hebrew_dictionary_is_still_held_to_its_pin():
    run = _step_running("bootstrap_dicts.sh persian")["run"]
    assert "HEBREW_DICT_SHA256" in run


def test_the_rollup_requires_the_job():
    rollup = _ci()["jobs"]["all-ok"]
    assert JOB in rollup["needs"]
    script = "\n".join(str(step.get("run", "")) for step in rollup["steps"])
    assert f"needs['{JOB}'].result" in script
    assert "needs.changes.outputs.context" in script


@pytest.mark.parametrize(
    "path",
    [
        "src/context.rs",
        "src/transliterate.rs",
        "scripts/build_arabic_dict.py",
        "scripts/build_hebrew_dict.py",
        "scripts/build_persian_dict.py",
        "scripts/context_words.py",
        "scripts/bootstrap_dicts.sh",
        "tests/test_context_hebrew.py",
        ".github/workflows/ci.yml",
    ],
)
def test_a_change_to_what_the_dictionaries_depend_on_starts_the_job(path):
    """`code` has no `*.sh`, so a change to the pin alone would start nothing that checks it."""
    assert (ROOT / path).is_file(), path
    jobs = _ci()["jobs"]
    assert "needs.changes.outputs.context" in jobs[JOB]["if"]
    assert jobs["changes"]["outputs"]["context"] == "${{ steps.filter.outputs.context }}"
    step = next(s for s in jobs["changes"]["steps"] if s.get("id") == "filter")
    patterns = yaml.safe_load(step["with"]["filters"])["context"]
    assert any(fnmatch.fnmatch(path, pattern) for pattern in patterns), patterns


def test_the_fixture_is_in_the_filter():
    jobs = _ci()["jobs"]
    step = next(s for s in jobs["changes"]["steps"] if s.get("id") == "filter")
    patterns = yaml.safe_load(step["with"]["filters"])["context"]
    relative = ARABIC_FIXTURE.relative_to(ROOT).as_posix()
    assert any(fnmatch.fnmatch(relative, pattern) for pattern in patterns), patterns


def test_the_weekly_run_saves_the_cache_where_a_pull_request_can_read_it():
    """A pull request reads the default branch's cache and never another pull request's."""
    assert "github.event_name == 'schedule'" in _job()["if"]


def test_the_guarded_counts_are_the_modules_own():
    """A count that drifts would make the assertions above pass on a smaller module."""
    for module, count in GUARDED.items():
        text = (ROOT / module).read_text(encoding="utf-8")
        assert len(re.findall(r"^\s*def test_", text, re.MULTILINE)) == count, module
