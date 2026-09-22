"""The tree-walking gates must not walk a virtual environment — and must walk the rest.

Two modules build a corpus by walking the repository and skipping build output by
NAME, and the name they knew was `.venv`. Anyone whose environment is `venv/`, `env/`,
`.tox/` or `.venv312/` swept the whole of site-packages into it. Two costs, one visible
and one not:

* **Slow.** 1,516 of 2,123 files in one corpus and 1,390 of 1,796 in another were
  third-party. Those two modules were the second and third most expensive in the suite
  entirely on that account.
* **Wrong.** `test_no_literal_bidi_controls_anywhere` and its siblings fail on a literal
  bidi control found anywhere in the corpus. A dependency shipping one in a test fixture
  would fail this repository's gate, on a machine the author cannot see, with a path
  nobody recognises.

`conftest.venv_dirs` finds them by `pyvenv.cfg` — what actually makes a directory a
virtual environment — and `conftest.in_skipped_dir` excludes a file only when one of
those directories *contains* it. The first version of this returned bare directory
names and matched them against every component of every path, so a `.tox/docs`
environment excluded the real `docs/` tree; and it matched skip names against the
*absolute* path, so a checkout under `~/build/` had an empty corpus (#997 review).

Every test here runs each module's own collector over a synthetic tree. The first version
asked about this checkout instead, and skipped whenever the checkout held no virtualenv —
which is every CI run, so it never once checked what it was for.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import conftest
import pytest

#: Each module that walks the tree, by its collector. Both take the root to walk.
COLLECTORS = ["test_code_context_profile", "test_tree_invisible_characters"]


def _collector(module_name: str) -> Callable[[Path], list[Path]]:
    return __import__(module_name)._sources


def _touch(root: Path, *rels: str) -> None:
    for rel in rels:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("home = /usr\n" if path.name == "pyvenv.cfg" else "x = 1\n", "utf-8")


def _corpus(module_name: str, root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in _collector(module_name)(root)}


@pytest.mark.parametrize("module_name", COLLECTORS)
def test_an_arbitrarily_named_virtualenv_is_skipped(tmp_path: Path, module_name: str) -> None:
    """The point of the marker: the name is arbitrary, `pyvenv.cfg` is not."""
    _touch(tmp_path, "src/ours.py", "whatever/pyvenv.cfg", "whatever/lib/site-packages/dep.py")
    assert _corpus(module_name, tmp_path) == {"src/ours.py"}


@pytest.mark.parametrize("module_name", COLLECTORS)
def test_a_virtualenv_does_not_hide_a_directory_with_its_name(
    tmp_path: Path, module_name: str
) -> None:
    """`.tox/docs` is an environment; `docs/` is this repository's documentation."""
    _touch(tmp_path, "docs/ours.py", ".tox/docs/pyvenv.cfg", ".tox/docs/lib/dep.py")
    assert _corpus(module_name, tmp_path) == {"docs/ours.py"}


@pytest.mark.parametrize("module_name", COLLECTORS)
@pytest.mark.parametrize("parent", ["build", "target", "tmp", "pkg", "node_modules"])
def test_a_checkout_under_a_skipped_name_is_still_walked(
    tmp_path: Path, module_name: str, parent: str
) -> None:
    """Skip names apply inside the tree, not to wherever the tree happens to live."""
    root = tmp_path / parent / "disarm"
    _touch(root, "src/ours.py")
    assert _corpus(module_name, root) == {"src/ours.py"}


@pytest.mark.parametrize("module_name", COLLECTORS)
def test_dot_venv_is_skipped_by_name_even_without_the_marker(
    tmp_path: Path, module_name: str
) -> None:
    """A conda environment at `.venv` has no `pyvenv.cfg`, and nor does one nested deeper
    than the marker search goes. The name that was always skipped still is."""
    _touch(tmp_path, "src/ours.py", ".venv/lib/conda_dep.py", "a/b/c/.venv/lib/deep_dep.py")
    assert _corpus(module_name, tmp_path) == {"src/ours.py"}


@pytest.mark.parametrize("module_name", COLLECTORS)
def test_build_output_is_still_skipped(tmp_path: Path, module_name: str) -> None:
    """And moving the match to relative paths did not stop it matching at all."""
    _touch(tmp_path, "src/ours.py", "target/debug/build/gen.rs", "a/node_modules/x/y.py")
    assert _corpus(module_name, tmp_path) == {"src/ours.py"}


# ── the detector ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", [".venv", "venv", "env", ".tox", ".venv312", "whatever"])
def test_a_virtualenv_is_found_by_its_marker_not_its_name(tmp_path: Path, name: str) -> None:
    _touch(tmp_path, f"{name}/pyvenv.cfg")
    assert conftest.venv_dirs(tmp_path) == frozenset({Path(name)})


def test_a_directory_without_the_marker_is_not_a_virtualenv(tmp_path: Path) -> None:
    """The other direction: the name alone must not be enough for the detector."""
    for name in (".venv", "venv", "site-packages"):
        (tmp_path / name).mkdir()
    assert conftest.venv_dirs(tmp_path) == frozenset()


def test_a_virtualenv_is_reported_by_its_path_not_its_name(tmp_path: Path) -> None:
    """Two levels are searched, and what comes back says where, not just what."""
    _touch(tmp_path, ".tox/docs/pyvenv.cfg")
    assert conftest.venv_dirs(tmp_path) == frozenset({Path(".tox/docs")})

    _touch(tmp_path, "a/b/c/pyvenv.cfg")
    assert Path("a/b/c") not in conftest.venv_dirs.__wrapped__(tmp_path), (
        "the two-level limit is not what it says"
    )


def test_every_virtualenv_this_repo_reports_carries_the_marker() -> None:
    """And the real tree agrees with the rule."""
    for rel in conftest.venv_dirs():
        assert (conftest.ROOT / rel / "pyvenv.cfg").exists(), rel
