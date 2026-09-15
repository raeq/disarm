"""The tree-walking gates must not walk a virtual environment.

Two modules build a corpus by walking the repository and skipping build output by
NAME, and the name they knew was `.venv`. Anyone whose environment is `venv/`, `env/`,
`.tox/` or — as here — `.venv312/` swept the whole of site-packages into it. Two costs,
one visible and one not:

* **Slow.** 1,516 of 2,123 files in one corpus and 1,390 of 1,796 in another were
  third-party. Those two modules were the second and third most expensive in the suite
  entirely on that account.
* **Wrong.** `test_no_literal_bidi_controls_anywhere` and its siblings fail on a literal
  bidi control found anywhere in the corpus. A dependency shipping one in a test fixture
  would fail this repository's gate, on a machine the author cannot see, with a path
  nobody recognises.

`conftest.venv_dir_names` finds them by `pyvenv.cfg` — what actually makes a directory a
virtual environment — rather than by a list of names to be wrong about later.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import ROOT, excluded_dirs, venv_dir_names

CORPORA = {
    "test_code_context_profile": "SOURCES",
    "test_tree_invisible_characters": "SOURCES",
}


def _corpus(module_name: str, attr: str) -> list[Path]:
    module = __import__(module_name)
    return list(getattr(module, attr))


@pytest.mark.parametrize(("module_name", "attr"), sorted(CORPORA.items()))
def test_no_corpus_contains_a_virtualenv_file(module_name: str, attr: str) -> None:
    names = venv_dir_names()
    if not names:
        pytest.skip("no virtual environment in the tree to be caught by")
    strays = [
        str(p.relative_to(ROOT))
        for p in _corpus(module_name, attr)
        if any(part in names for part in p.parts)
    ]
    assert not strays, (
        f"{module_name}.{attr} walked into a virtual environment ({sorted(names)}). "
        f"Its skip set must come from `conftest.excluded_dirs`:\n  " + "\n  ".join(strays[:5])
    )


@pytest.mark.parametrize("name", [".venv", "venv", "env", ".tox", ".venv312", "whatever"])
def test_a_virtualenv_is_found_by_its_marker_not_its_name(tmp_path: Path, name: str) -> None:
    """The point of using `pyvenv.cfg`: the name is arbitrary, the marker is not.

    Against a synthetic tree, because a test that can only ask about this checkout can
    only agree with whatever this checkout happens to contain. The first version of this
    test did exactly that and was a tautology — `excluded_dirs(set())` *is*
    `venv_dir_names()`, so `x not in A or x in A` cannot fail. Caught in review on #997.
    """
    (tmp_path / name).mkdir()
    (tmp_path / name / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
    assert venv_dir_names(tmp_path) == frozenset({name})


def test_a_directory_without_the_marker_is_not_a_virtualenv(tmp_path: Path) -> None:
    """The other direction: the name alone must not be enough."""
    for name in (".venv", "venv", "site-packages"):
        (tmp_path / name).mkdir()
    assert venv_dir_names(tmp_path) == frozenset()


def test_a_virtualenv_one_level_down_is_found(tmp_path: Path) -> None:
    """Two levels are searched; the depth is a documented limit, so assert it."""
    (tmp_path / "sub" / "venv").mkdir(parents=True)
    (tmp_path / "sub" / "venv" / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
    assert venv_dir_names(tmp_path) == frozenset({"venv"})

    deeper = tmp_path / "a" / "b" / "c"
    deeper.mkdir(parents=True)
    (deeper / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
    assert "c" not in venv_dir_names(tmp_path), "the two-level limit is not what it says"


def test_every_name_this_repo_reports_carries_the_marker() -> None:
    """And the real tree agrees with the rule."""
    for name in venv_dir_names():
        assert (ROOT / name / "pyvenv.cfg").exists() or any(
            (d / "pyvenv.cfg").exists() for d in ROOT.glob(f"*/{name}")
        ), f"{name} was reported as a virtualenv but carries no pyvenv.cfg"


def test_the_helper_keeps_what_it_is_given() -> None:
    """`excluded_dirs` adds to a caller's skip set; it does not replace it."""
    given = {"target", "node_modules"}
    assert given <= excluded_dirs(given)
