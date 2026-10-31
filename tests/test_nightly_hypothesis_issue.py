"""The nightly's failure issue must say what actually failed.

`if: failure()` is true when any step failed, and only the test step can produce a
counterexample. #1120 was a rustup download that timed out: no test ran, the log was
"(log unavailable)", and the issue still said "a failure here is a real counterexample,
not flake". This runs the step's own script under node with `github` stubbed, so it reads
what the workflow would file rather than what its source looks like.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
NIGHTLY = ROOT / ".github" / "workflows" / "nightly-hypothesis.yml"

COUNTEREXAMPLE = "Nightly Hypothesis run failed"
NO_VERDICT = "Nightly Hypothesis run did not reach a verdict"

_HARNESS = """
const script = require('fs').readFileSync(process.argv[2], 'utf8');
const AsyncFunction = (async () => {}).constructor;
const calls = [];
const github = {rest: {issues: {
  listForRepo: async () => ({data: JSON.parse(process.env.OPEN_ISSUES)}),
  createComment: async (args) => calls.push({kind: 'comment', ...args}),
  create: async (args) => calls.push({kind: 'create', ...args}),
}}};
const context = {
  serverUrl: 'https://github.com',
  runId: 1,
  sha: 'abcdef0123456',
  repo: {owner: 'o', repo: 'r'},
};
new AsyncFunction('github', 'context', 'require', script)(github, context, require)
  .then(() => console.log(JSON.stringify(calls)));
"""


def _step() -> dict:
    workflow = yaml.safe_load(NIGHTLY.read_text(encoding="utf-8"))
    (step,) = [
        s
        for s in workflow["jobs"]["hypothesis"]["steps"]
        if s.get("name") == "Open an issue on failure"
    ]
    return step


def _file(tmp_path: Path, outcome: str, open_issues: list[dict] | None = None) -> list[dict]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    script = tmp_path / "script.js"
    script.write_text(_step()["with"]["script"], encoding="utf-8")
    harness = tmp_path / "harness.js"
    harness.write_text(_HARNESS, encoding="utf-8")
    result = subprocess.run(  # noqa: S603 — fixed argv, no shell
        [node, str(harness), str(script)],
        cwd=tmp_path,
        env={
            **os.environ,
            "HYPOTHESIS_OUTCOME": outcome,
            "SEED": "42",
            "OPEN_ISSUES": json.dumps(open_issues or []),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_the_step_is_given_the_outcome_of_the_test_step() -> None:
    assert _step()["env"]["HYPOTHESIS_OUTCOME"] == "${{ steps.hypothesis.outcome }}"


def test_a_failed_test_step_files_a_counterexample(tmp_path: Path) -> None:
    (call,) = _file(tmp_path, "failure")
    assert call["kind"] == "create"
    assert call["title"] == COUNTEREXAMPLE
    assert call["labels"] == ["bug", "nightly-hypothesis"]
    assert "real counterexample" in call["body"]
    assert "--hypothesis-seed=42" in call["body"]


@pytest.mark.parametrize("outcome", ["skipped", "success", "cancelled"])
def test_a_failure_elsewhere_does_not_claim_a_counterexample(tmp_path: Path, outcome: str) -> None:
    """#1120's shape: `skipped`, because setup failed before the tests were reached."""
    (call,) = _file(tmp_path, outcome)
    assert call["kind"] == "create"
    assert call["title"] == NO_VERDICT
    assert call["labels"] == ["ci", "nightly-hypothesis"]
    assert "counterexample" not in call["body"]
    assert "falsifying example, so there is nothing to reproduce" in call["body"]
    assert f"`{outcome}`" in call["body"]


def test_each_kind_of_failure_keeps_its_own_rolling_issue(tmp_path: Path) -> None:
    both = [{"number": 1, "title": NO_VERDICT}, {"number": 2, "title": COUNTEREXAMPLE}]

    (call,) = _file(tmp_path, "failure", both)
    assert (call["kind"], call["issue_number"]) == ("comment", 2)

    (call,) = _file(tmp_path, "skipped", both)
    assert (call["kind"], call["issue_number"]) == ("comment", 1)


def test_a_counterexample_is_not_filed_under_a_setup_failure(tmp_path: Path) -> None:
    (call,) = _file(tmp_path, "failure", [{"number": 1, "title": NO_VERDICT}])
    assert call["kind"] == "create"
    assert call["title"] == COUNTEREXAMPLE
