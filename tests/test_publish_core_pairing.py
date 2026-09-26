"""#830 — a publish lane must verify the core it resolves, not that a version exists.

`wait-for-core` exists because of a release race (#500): on `release: published` the
binding publishers fire in parallel with `publish.yml`, so a build can start before the
core it needs is on crates.io. The job polls the sparse index until a non-yanked
`0.MINOR.*` appears.

That is the right gate for the race and the wrong gate for the lane. It proves a version
**exists**; it does not prove the glue at this ref can build against it — and between
releases it usually cannot. A core API and the binding glue that uses it land in one
commit, so from that commit until the next release the glue needs a core that is not
published yet, while the pin still reads the old minor. `0.14.1` had existed since the
release, so the poll went green in one request and handed the build a core the glue could
not compile against.

Measured on `main` at `cadd616`, with no `[patch.crates-io]` redirect, against the
published `disarm 0.14.1`:

    bindings/node        3 errors   UNICODE_VERSION, KEY_SCHEMA_VERSION, compat_fold
    bindings/ruby        4 errors
    bindings/java/rust   4 errors

#830 measured one missing field. It is four core items now, which is the point: the gap
widens with every core API that lands mid-cycle, and nothing was watching it.

The fix is that `wait-for-core` compiles the glue against the published core after the
poll and refuses with a reason. This file asserts the shape, because the poll on its own
looks like a complete gate and reads like one.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"

#: The sparse-index host the poll must reach, compared as a whole netloc.
REGISTRY_INDEX_HOST = "index.crates.io"

#: The three workflows that resolve the core from crates.io and build glue against it.
PUBLISHERS = ("publish-node.yml", "publish-ruby.yml", "publish-java.yml")


def _text(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def _wait_for_core(name: str) -> str:
    """The `wait-for-core` job as text, with comments stripped.

    Parsed rather than sliced between job names — an earlier draft cut to `\n  build:`
    and raised `ValueError` on the workflow whose next job is called something else.
    Comments go because both a YAML comment and a shell comment inside a `run:` block can
    contain the very strings these assertions look for: the redirect check was failing on
    a comment that says there is deliberately *no* redirect.
    """
    job = yaml.safe_load(_text(name))["jobs"]["wait-for-core"]
    parts: list[str] = []
    for step in job.get("steps", []):
        for key, value in step.items():
            if not isinstance(value, str):
                parts.append(f"{key}: {value}")
                continue
            # `yaml.dump` folds a `run: |` block into one escaped line, so stripping
            # comments from the dumped text cannot reach the shell comments inside it.
            # Strip them here, where the block is still real lines.
            parts.append(
                "\n".join(line for line in value.split("\n") if not line.strip().startswith("#"))
            )
    return "\n".join(parts)


def test_the_publishers_exist() -> None:
    """A gate over a missing file passes for the wrong reason."""
    for name in PUBLISHERS:
        assert (WORKFLOWS / name).exists(), name


@pytest.mark.parametrize("name", PUBLISHERS)
def test_the_gate_polls_for_the_core(name: str) -> None:
    """The #500 half, still needed: a release publishes the core in parallel.

    Scoped to the `wait-for-core` job with comments stripped, not to the raw file: a
    poll that had been deleted would still be "found" in a YAML or shell comment mentioning
    it, and this file already strips comments everywhere else for that reason.

    The host is compared as a parsed netloc rather than as a substring. CodeQL flagged the
    substring form (`py/incomplete-url-substring-sanitization`) and the rule is right on
    the general point — `"index.crates.io" in text` also matches
    `index.crates.io.example.com` — so this checks the thing the rule asks for, which is
    also the stronger assertion.
    """
    urls = re.findall(r"https?://[^\s\"']+", _wait_for_core(name))
    hosts = {urlparse(url).netloc for url in urls}
    # Equality per host, not `literal in hosts`. Both are correct here — `hosts` holds
    # parsed netlocs, so membership is exact — but CodeQL's
    # `py/incomplete-url-substring-sanitization` matches the shape rather than the
    # semantics, and an equality comparison is the pattern the rule documents. Writing
    # it the way the analyser can verify costs nothing and keeps the check green.
    assert any(host == REGISTRY_INDEX_HOST for host in hosts), (
        f"{name} lost its crates.io sparse-index poll; hosts found: {sorted(hosts)}"
    )


@pytest.mark.parametrize("name", PUBLISHERS)
def test_the_gate_also_compiles_against_it(name: str) -> None:
    """The #830 half: existence is not compatibility.

    Asserted as *a compile step inside `wait-for-core`* rather than by name, so renaming
    the step is fine and deleting the check is not.
    """
    job = _wait_for_core(name)
    assert "cargo check" in job, (
        f"{name}'s wait-for-core polls for a published core but never builds against it. "
        "The poll proves a version exists; between releases the glue routinely needs one "
        "that is not published yet, and a dispatch then dies in a per-platform matrix "
        "with a bare E0425/E0609 instead of here."
    )


@pytest.mark.parametrize("name", PUBLISHERS)
def test_the_check_runs_without_a_redirect(name: str) -> None:
    """It must resolve what the publish build resolves.

    A `[patch.crates-io]` redirect inside this job would make the check pass always and
    mean nothing — it would be testing the local core, which CI already covers.
    """
    job = _wait_for_core(name)
    assert "patch.crates-io" not in job, (
        f"{name}'s wait-for-core applies a path redirect; then it is not checking the "
        "published core and the gate is vacuous"
    )


@pytest.mark.parametrize("name", PUBLISHERS)
def test_the_failure_names_the_way_out(name: str) -> None:
    """A gate that fails without a remedy sends the reader to the matrix logs.

    The two remedies are release-tag dispatch or releasing the core first, and both are
    in RELEASING.md rule 2 — so the message points there rather than restating it.
    """
    job = _wait_for_core(name)
    assert "RELEASING.md" in job, f"{name}'s failure path does not name the documented lane"


def test_releasing_md_says_the_lane_is_conditional() -> None:
    """The doc claimed the per-registry patch lane is always available. It is not."""
    text = (ROOT / "RELEASING.md").read_text(encoding="utf-8")
    assert "#830" in text, "RELEASING.md does not record the constraint on the patch lane"


@pytest.mark.parametrize(
    "manifest",
    ["bindings/cabi/Cargo.toml", "bindings/java/rust/Cargo.toml"],
)
def test_the_manifests_do_not_assert_the_disproved_property(manifest: str) -> None:
    """Both said the shipped manifest builds against the published core, unqualified.

    True at a release boundary, false for most of a cycle, and #830 is the measurement.
    """
    text = (ROOT / manifest).read_text(encoding="utf-8")
    if "PUBLISHED" not in text:
        return
    assert "#830" in text or "RELEASE BOUNDARY" in text, (
        f"{manifest} claims it builds against the PUBLISHED core without the qualification "
        "#830 established"
    )


# ---------------------------------------------------------------------------
# The exact core, not any 0.MINOR.* (0.17.1)
# ---------------------------------------------------------------------------
#
# The poll above waited for any non-yanked `0.MINOR.*`. On a minor release none exists
# until publish.yml pushes it, so the wait was real. On a patch release the previous
# patch already satisfies it: 0.17.1's wait-for-core passed in one request at 12:55,
# the Node and JVM builds compiled `disarm v0.17.0`, npm and Maven published them at
# 12:59-13:00, and core 0.17.1 reached crates.io at 13:03. The fix the release existed
# for was in neither artifact. The gem did not publish only because its specs happened
# to exercise that fix.

#: Commands that compile the glue against whichever core the lockfile resolves.
_COMPILES = ("cargo check", "cargo build", "napi build", "rake compile")
_CROSS_GEM = "oxidize-rb/actions/cross-gem@"


def _jobs(name: str) -> dict:
    return yaml.safe_load(_text(name))["jobs"]


def _root_version() -> str:
    import tomllib

    return tomllib.loads((ROOT / "Cargo.toml").read_text(encoding="utf-8"))["package"]["version"]


def _compiles(step: dict) -> bool:
    run = step.get("run") or ""
    return any(command in run for command in _COMPILES) or str(step.get("uses", "")).startswith(
        _CROSS_GEM
    )


def _pins(step: dict) -> bool:
    return "pin_published_core.sh" in (step.get("run") or "")


@pytest.mark.parametrize("name", PUBLISHERS)
def test_the_poll_waits_for_the_version_this_ref_releases(name: str) -> None:
    """The version expression, run for real, must yield the root crate's version.

    Executed rather than pattern-matched: the old poll also read "a version" out of a
    manifest, and read the wrong one.
    """
    import subprocess

    job = _wait_for_core(name)
    lines = [line.strip() for line in job.splitlines() if line.strip().startswith('want="$(')]
    assert len(lines) == 1, f"{name}'s poll does not compute the version it waits for"
    result = subprocess.run(
        ["bash", "-c", lines[0] + '\nprintf %s "$want"'],
        capture_output=True,
        text=True,
        check=True,
        env={"GITHUB_WORKSPACE": str(ROOT), "PATH": "/usr/bin:/bin"},
    )
    assert result.stdout == _root_version(), (
        f"{name}'s poll waits for {result.stdout!r}, but this ref releases {_root_version()!r}"
    )
    assert 'grep -qxF "$want"' in job, (
        f"{name}'s poll does not match the version exactly; a prefix or pattern match "
        "lets the previous patch through"
    )


@pytest.mark.parametrize("name", PUBLISHERS)
def test_every_compile_on_the_publish_path_is_pinned_first(name: str) -> None:
    """An exact wait is not an exact build: the build resolves the lockfile itself.

    Every step that compiles the glue must come after a step that pins the lockfile to
    the release's core, in the same job.
    """
    compiling = 0
    for job_name, job in _jobs(name).items():
        pinned = False
        for step in job.get("steps", []):
            if _pins(step):
                pinned = True
            elif _compiles(step):
                compiling += 1
                assert pinned, (
                    f"{name}: job `{job_name}` compiles "
                    f"({step.get('name') or step.get('run') or step.get('uses')}) with no "
                    "pin_published_core.sh step before it, so it builds against whatever "
                    "0.MINOR.* is newest when it runs"
                )
    assert compiling, f"{name}: no compiling step found; the check above checked nothing"


def test_the_pin_script_is_executable() -> None:
    script = ROOT / "scripts" / "pin_published_core.sh"
    assert script.exists()
    assert script.stat().st_mode & 0o111, "scripts/pin_published_core.sh is not executable"


def test_the_npm_publish_job_compiles_nothing() -> None:
    """It ran `napi build` for the loader, which also compiles the addon.

    A debug build for the runner's platform, written over the release prebuild: every
    npm release through 0.17.1 shipped a debug linux-x64 addon of about 40 MB, built
    against whichever core resolved when the publish job ran.
    """
    steps = _jobs("publish-node.yml")["publish"]["steps"]
    for step in steps:
        assert not _compiles(step), f"the npm publish job compiles: {step}"
    runs = "\n".join(step.get("run") or "" for step in steps)
    assert "sha256sum -c" in runs, (
        "the npm publish job no longer verifies that the prebuilds it publishes are the "
        "ones the build matrix made"
    )
