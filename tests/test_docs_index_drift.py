"""#656: ``docs/index.md`` stays in sync with the README it is generated from.

``docs/index.md`` carries a banner saying it is generated from ``README.md`` +
``docs/_index_nav.md`` and must not be edited directly. Nothing regenerated it and
nothing checked it, so the banner was the only thing holding the line — and it did
not hold. Measured before this test existed, the file had drifted **in both
directions at once**:

* two *Features* bullets existed only in the generated file, and the next run of
  the generator would have deleted them;
* a Node.js *Getting Started* entry, a whole-script-spoof example and a
  coverage-residue note existed only in the sources and had never reached the
  published site.

The second kind is the one that reads as working. A contributor edits
``README.md``, the change appears on GitHub, and the docs site quietly does not
move.

There is a second reason this matters, which is why the check lives here rather
than only in CI. Every Python block in ``README.md`` lands in ``docs/index.md``,
which is first on ``EXECUTED_RECIPES`` in ``docs/conftest.py`` and runs under
Sybil on every CI run. **In sync, the README's examples are executed; out of sync,
they are not.** So this is not only a tidiness check — it is what makes the
most-read file in the project covered at all.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

#: Every test here shells out to the generator, which is a bash script. Skipping
#: only the ones that obviously need a shell would leave the rest erroring on
#: Windows before any skip applied, so the mark is module-wide.
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the generator is a bash script")

ROOT = Path(__file__).resolve().parent.parent
GENERATOR = ROOT / "scripts" / "generate_docs_index.sh"
README = ROOT / "README.md"
NAV = ROOT / "docs" / "_index_nav.md"
INDEX = ROOT / "docs" / "index.md"

#: ```python … ``` — the blocks Sybil executes.
PY_BLOCK = re.compile(r"^```python\n(.*?)^```", re.DOTALL | re.MULTILINE)


def _run_check() -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — fixed argv, no shell, our own script
        ["bash", str(GENERATOR), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_the_generator_exists_and_is_runnable() -> None:
    assert GENERATOR.is_file(), GENERATOR
    for source in (README, NAV, INDEX):
        assert source.is_file(), source


def test_docs_index_matches_its_sources() -> None:
    """The whole point. Regenerate, compare, and print the diff on failure."""
    result = _run_check()
    assert result.returncode == 0, (
        "docs/index.md is out of date with README.md + docs/_index_nav.md.\n"
        "Run `bash scripts/generate_docs_index.sh` and commit the result.\n\n"
        f"{result.stdout}\n{result.stderr}"
    )


def test_the_check_can_actually_fail() -> None:
    """A gate that only ever passes is not a gate.

    Perturbs the README in a place the generator carries through — appending to
    the end would land inside the ``## License`` section, which the generator
    strips, so the check would pass and prove nothing.
    """
    original = README.read_text(encoding="utf-8")
    assert "## disarm capabilities" in original, "the probe's anchor moved"
    try:
        README.write_text(
            original.replace(
                "## disarm capabilities", "## disarm capabilities\n\n- drift probe", 1
            ),
            encoding="utf-8",
        )
        result = _run_check()
        assert result.returncode == 1, (
            "the drift check passed on a perturbed README, so it is not checking "
            f"anything. stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert "out of date" in result.stderr
    finally:
        README.write_text(original, encoding="utf-8")

    assert _run_check().returncode == 0, "the README was not restored"


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(["--not-a-flag"], id="unknown-flag"),
        pytest.param(["--chekc"], id="typo-of-check"),
        pytest.param(["--check", "--extra"], id="check-plus-junk"),
        pytest.param(["--check", "--check"], id="check-twice"),
    ],
)
def test_the_generator_refuses_bad_arguments(args: list[str]) -> None:
    """A typo must not fall through to the write path.

    This script overwrites ``docs/index.md``. ``--chekc`` silently regenerating
    the file it was asked to *verify* is the one failure that would defeat the
    point of having a ``--check``, and ``--check --extra`` ignoring the extra
    argument is the same hazard one keystroke further away.
    """
    result = subprocess.run(  # noqa: S603 — fixed argv, no shell
        ["bash", str(GENERATOR), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 2, result
    assert "usage:" in result.stderr


class TestReadmeExamplesAreExecutedTransitively:
    """The README is covered *because* it is in sync, not on its own."""

    def test_every_readme_python_block_reaches_the_executed_page(self) -> None:
        readme_blocks = PY_BLOCK.findall(README.read_text(encoding="utf-8"))
        index_blocks = PY_BLOCK.findall(INDEX.read_text(encoding="utf-8"))
        assert readme_blocks, "no Python blocks found in README.md"

        # The generator rewrites `(docs/…)` links, which never appear inside a
        # code block, so the blocks must survive byte-identical.
        missing = [b for b in readme_blocks if b not in index_blocks]
        assert not missing, [b.strip().splitlines()[0] for b in missing]

    def test_the_target_page_is_on_the_sybil_allowlist(self) -> None:
        """If `index.md` ever leaves EXECUTED_RECIPES, the README stops being
        executed and this file's premise quietly stops holding."""
        conftest = (ROOT / "docs" / "conftest.py").read_text(encoding="utf-8")
        assert '"index.md"' in conftest, (
            "docs/index.md is no longer on EXECUTED_RECIPES, so README.md's "
            "examples are executed by nothing again"
        )


def test_running_the_generator_is_idempotent() -> None:
    """Two runs in a row must not produce two different files.

    Guards the failure where a timestamp or a `mktemp` name leaks into the
    output: the check would then fail on every commit and get switched off.
    """
    before = INDEX.read_text(encoding="utf-8")
    try:
        for _ in range(2):
            subprocess.run(  # noqa: S603 — fixed argv, no shell
                ["bash", str(GENERATOR)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            )
        assert INDEX.read_text(encoding="utf-8") == before
    finally:
        INDEX.write_text(before, encoding="utf-8")
