"""#667/#669: the artifact smoke script runs in a virtualenv holding only disarm.

``scripts/smoke_installed.py`` exists to answer one question — does the thing a
user installs import and work — and it can only answer it from an environment
that contains the artifact and nothing else. Every other environment in this
repository holds pytest, hypothesis, mypy and sybil, which is exactly why a
missing runtime dependency has never been detectable here.

One stray ``import pytest`` at the top of that script and it stops being able to
run where it matters, while still passing everywhere it does not. These tests
hold the property that makes it useful.

They deliberately do **not** run the script. Doing that needs a built artifact and
a clean virtualenv, which is minutes of compiling and belongs in
``.github/workflows/smoke.yml`` rather than in the unit suite.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "smoke_installed.py"
WORKFLOW = ROOT / ".github" / "workflows" / "smoke.yml"

#: Anything the script may import: the package under test, plus the standard
#: library, which is all a bare virtualenv has.
ALLOWED = {"disarm"} | set(sys.stdlib_module_names)


def _imports(path: Path) -> set[str]:
    """Top-level package name of every import in a module, at any nesting."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_the_script_exists() -> None:
    assert SCRIPT.is_file(), SCRIPT


def test_it_imports_nothing_a_bare_virtualenv_lacks() -> None:
    """The whole point: it has to run where nothing else is installed."""
    outside = sorted(_imports(SCRIPT) - ALLOWED)
    assert not outside, (
        f"scripts/smoke_installed.py imports {outside}, which a virtualenv holding "
        "only the built artifact does not have. That is the environment it exists "
        "to test, so it would fail there and pass everywhere else."
    )


def test_it_imports_disarm_lazily() -> None:
    """A module-level ``import disarm`` turns a missing install into a traceback.

    The script's first check *is* the import, and it reports the failure with the
    exception type and message. That only works if the import happens inside a
    function, where it can be caught.
    """
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    module_level: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            module_level |= {alias.name.split(".")[0] for alias in node.names}
        # `from disarm import canonicalize` binds at module level too, and
        # scanning only ast.Import would miss it — the same failure one keyword
        # away.
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            module_level.add(node.module.split(".")[0])
    assert "disarm" not in module_level, (
        "importing disarm at module level — with `import` or `from … import` — "
        "makes a missing install a bare traceback instead of the script's own "
        "reported failure"
    )


def test_it_is_syntactically_valid_and_has_an_entry_point() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert "main" in functions
    assert 'if __name__ == "__main__":' in source


def _yaml_block(text: str, key: str, indent: int) -> list[str]:
    """The lines nested under ``key`` at ``indent``, by indentation alone.

    A hand-rolled reader rather than PyYAML, because PyYAML is not in the
    ``[test]`` extra and adding a dependency to a test *about* a script that must
    run without dependencies would be a poor joke. Only two blocks are read and
    both are ours, so this needs to understand indentation and nothing else.
    """
    lines = text.split("\n")
    prefix = " " * indent
    start = next(
        (i for i, line in enumerate(lines) if line == f"{prefix}{key}:"),
        None,
    )
    if start is None:
        return []
    body: list[str] = []
    for line in lines[start + 1 :]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if len(line) - len(line.lstrip()) <= indent:
            break
        body.append(line)
    return body


class TestTheWorkflowUsesIt:
    """A script nothing runs is not a gate."""

    def test_the_workflow_exists_and_calls_the_script(self) -> None:
        assert WORKFLOW.is_file(), WORKFLOW
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "scripts/smoke_installed.py" in text

    def test_the_branch_job_has_no_path_filter(self) -> None:
        """#669's requirement, and the easiest thing to undo by accident.

        The point of the branch job is that it runs on *every* commit that lands.
        A ``paths:`` filter under ``push:`` would silently reinstate the gap: a
        merge matching no pattern would trigger nothing at all, which is the state
        that left ``main`` unbuilt in the first place.
        """
        text = WORKFLOW.read_text(encoding="utf-8")
        push = _yaml_block(text, "push", indent=2)
        assert push, "the workflow no longer runs on push"
        assert any("branches: [main]" in line for line in push), push
        offending = [line for line in push if line.strip().startswith("paths")]
        assert not offending, (
            "the push trigger gained a paths filter, so a commit matching no "
            f"pattern lands on main unbuilt — the gap #669 was filed for: {offending}"
        )

    def test_the_pull_request_trigger_does_still_filter(self) -> None:
        """The other direction: running the artifact build on every PR is waste.

        Only the branch job needs to be unconditional.
        """
        pull_request = _yaml_block(WORKFLOW.read_text(encoding="utf-8"), "pull_request", 2)
        assert any(line.strip().startswith("paths") for line in pull_request), pull_request

    def test_both_artifacts_are_covered(self) -> None:
        """The sdist is the one with no coverage anywhere else."""
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "artifact: [wheel, sdist]" in text, (
            "the artifact matrix changed; the sdist is the half with no other "
            "coverage in the repository and must stay in it"
        )
