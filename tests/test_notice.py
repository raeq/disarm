"""#738 — the confusable-vision credit travels with the data into every package.

disarm folds pairs measured by confusable-vision (© Paul Wood FRSA, data CC-BY-4.0) into
its confusable tables. The two source files under `data/` credited it from the start, but
they are not what ships: the crate, the wheels, the gem, the npm package and the jar carry
the generated tables and nothing from `data/`. CC-BY-4.0 asks for the credit, a link to the
licence and a note of changes wherever the adapted data is redistributed, so the generated
tables carry it in their header and every package carries `NOTICE`.

These tests pin that. Each one is derived from the files it describes, so a new source
file, a new target or a new package manifest fails here rather than shipping uncredited.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NOTICE = ROOT / "NOTICE"
TABLES = ROOT / "src" / "tables" / "data"

#: The source files whose rows are adapted from confusable-vision.
ADAPTED_SOURCES = (
    ROOT / "data" / "confusables_supplement.tsv",
    ROOT / "data" / "confusables_vision.tsv",
)

#: Copies of NOTICE that a package build reads from its own directory.
NOTICE_COPIES = (ROOT / "bindings" / "node" / "NOTICE", ROOT / "bindings" / "ruby" / "NOTICE")

LICENCE_URL = "https://creativecommons.org/licenses/by/4.0/"
SOURCE_URL = "https://github.com/paultendo/confusable-vision"


def _targets_fed_by(source: Path) -> set[str]:
    """The fold targets a source file overrides: its `latin`/`cyrillic` cells not `-`."""
    targets: set[str] = set()
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cells = line.split("\t")
        assert len(cells) >= 3, f"{source.name}: expected source, latin, cyrillic columns: {line!r}"
        for name, cell in (("latin", cells[1]), ("cyrillic", cells[2])):
            if cell.strip() not in ("", "-"):
                targets.add(name)
    return targets


def _header(table: Path) -> str:
    lines = table.read_text(encoding="utf-8").splitlines()
    header = "\n".join(line for line in lines[:20] if line.lstrip().startswith("#"))
    assert header, f"{table.name} has no comment header"
    return header


def test_notice_credits_the_source_and_the_licence() -> None:
    text = NOTICE.read_text(encoding="utf-8")
    for required in ("Paul Wood FRSA", SOURCE_URL, "CC-BY-4.0", LICENCE_URL, "Changed:"):
        assert required in text, f"NOTICE lacks {required!r}"


@pytest.mark.parametrize("source", ADAPTED_SOURCES, ids=lambda p: p.name)
def test_notice_names_every_adapted_source_file(source: Path) -> None:
    """The note of changes points at the file that states the admission rule."""
    assert source.exists(), source
    assert f"data/{source.name}" in NOTICE.read_text(encoding="utf-8"), (
        f"NOTICE does not name data/{source.name}, which carries adapted rows"
    )


@pytest.mark.parametrize("copy", NOTICE_COPIES, ids=lambda p: str(p.relative_to(ROOT)))
def test_package_copies_match_the_root_notice(copy: Path) -> None:
    """npm and RubyGems package only their own directory, so they carry a copy."""
    assert copy.read_bytes() == NOTICE.read_bytes(), (
        f"{copy.relative_to(ROOT)} has drifted from NOTICE; copy it again"
    )


def test_every_table_fed_by_an_adapted_source_carries_the_credit() -> None:
    fed: dict[str, list[str]] = {}
    for source in ADAPTED_SOURCES:
        for target in _targets_fed_by(source):
            fed.setdefault(target, []).append(f"data/{source.name}")
    assert fed, "no adapted source feeds any target; the check below checks nothing"
    for target, sources in fed.items():
        header = _header(TABLES / f"confusables_to_{target}.tsv")
        for required in ("confusable-vision", "Paul Wood FRSA", "CC-BY-4.0", LICENCE_URL, "NOTICE"):
            assert required in header, f"confusables_to_{target}.tsv header lacks {required!r}"
        for source in sources:
            assert source in header, f"confusables_to_{target}.tsv header does not name {source}"


def _toml_array(path: Path, key: str) -> list[str]:
    """The string items of a top-level TOML array, read without a TOML parser.

    `tomllib` is not in Python 3.10, which disarm supports, and `tomli` is not a
    dependency, so the two arrays are read directly.
    """
    match = re.search(
        rf"^{re.escape(key)}\s*=\s*\[(.*?)\]", path.read_text(encoding="utf-8"), re.M | re.S
    )
    assert match is not None, f"{path.name} has no `{key} = [...]`"
    return re.findall(r'"([^"]*)"', match.group(1))


def test_the_crate_ships_notice() -> None:
    assert "/NOTICE" in _toml_array(ROOT / "Cargo.toml", "include")


def test_the_wheel_and_sdist_ship_notice() -> None:
    assert "NOTICE" in _toml_array(ROOT / "pyproject.toml", "license-files")


def test_the_npm_package_ships_notice() -> None:
    """npm adds LICENSE and README on its own; NOTICE only when `files` lists it."""
    package = json.loads((ROOT / "bindings" / "node" / "package.json").read_text(encoding="utf-8"))
    assert "NOTICE" in package["files"]


def test_the_gem_ships_notice() -> None:
    gemspec = (ROOT / "bindings" / "ruby" / "disarm.gemspec").read_text(encoding="utf-8")
    files = re.search(r"spec\.files\s*=\s*Dir\[(.*?)\]", gemspec, re.S)
    assert files is not None, "disarm.gemspec has no spec.files = Dir[...]"
    assert '"NOTICE"' in files.group(1)


def test_the_jar_ships_notice() -> None:
    """The native library inside disarm-java's jar is what carries the tables."""
    gradle = (ROOT / "bindings" / "java" / "disarm-java" / "build.gradle.kts").read_text(
        encoding="utf-8"
    )
    jar = re.search(r'tasks\.named<Jar>\("jar"\)\s*\{(.*?)\n\}', gradle, re.S)
    assert jar is not None, "disarm-java/build.gradle.kts has no jar task block"
    assert '"../../../NOTICE"' in jar.group(1) and 'into("META-INF")' in jar.group(1)
