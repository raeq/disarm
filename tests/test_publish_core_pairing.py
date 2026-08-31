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
