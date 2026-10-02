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
import tomllib
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


def _toml(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_the_crate_ships_notice() -> None:
    assert "/NOTICE" in _toml(ROOT / "Cargo.toml")["package"]["include"]


def test_the_wheel_and_sdist_ship_notice() -> None:
    assert "NOTICE" in _toml(ROOT / "pyproject.toml")["project"]["license-files"]


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


# ---------------------------------------------------------------------------
# Unicode data: the UCD, UTS #39 and CLDR, under the Unicode License v3
# ---------------------------------------------------------------------------
#
# Every table under src/tables/ is generated from Unicode data, and the Unicode License v3
# grants its rights on the condition that its copyright and permission notice travel with
# every copy. NOTICE carries the text; these tests keep it complete and current.

#: The clauses of the Unicode License v3 that carry its conditions, whitespace-normalised.
UNICODE_LICENCE_CLAUSES = (
    "UNICODE LICENSE V3",
    "COPYRIGHT AND PERMISSION NOTICE",
    "provided that either (a) this copyright and permission notice appear with all copies "
    "of the Data Files or Software, or (b) this copyright and permission notice appear in "
    "associated Documentation.",
    'THE DATA FILES AND SOFTWARE ARE PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND',
    "IN NO EVENT SHALL THE COPYRIGHT HOLDER OR HOLDERS INCLUDED IN THIS NOTICE BE LIABLE",
    "the name of a copyright holder shall not be used in advertising",
)

_UNICODE_HOLDER = re.compile(
    r"(?:©|\(c\)|Copyright)[^\n]*?(?:(\d{4})-)?(\d{4}) Unicode(?:®)?, Inc\."
)


def _normalised(text: str) -> str:
    return " ".join(text.split())


def _vendored_unicode_files() -> dict[Path, int]:
    """Files under data/ whose header names Unicode, Inc. as copyright holder, with the year."""
    found: dict[Path, int] = {}
    for path in sorted((ROOT / "data").rglob("*")):
        if not path.is_file() or path.suffix not in (".txt", ".xml"):
            continue
        with path.open(encoding="utf-8", errors="replace") as f:
            head = f.read(4096)
        match = _UNICODE_HOLDER.search(head)
        if match:
            found[path] = int(match.group(2))
    return found


def test_notice_carries_the_unicode_licence() -> None:
    text = _normalised(NOTICE.read_text(encoding="utf-8"))
    for clause in UNICODE_LICENCE_CLAUSES:
        assert _normalised(clause) in text, f"NOTICE lacks the Unicode licence clause {clause!r}"


def test_the_unicode_scan_finds_the_vendored_files() -> None:
    """Guards the scan below: it must find the files it is meant to check."""
    found = {path.relative_to(ROOT).as_posix() for path in _vendored_unicode_files()}
    for expected in ("data/Scripts.txt", "data/confusables.txt", "data/cldr/en.xml"):
        assert expected in found, f"{expected} was not recognised as Unicode data: {sorted(found)}"


def test_notice_names_every_vendored_unicode_file() -> None:
    text = NOTICE.read_text(encoding="utf-8")
    for path in _vendored_unicode_files():
        name = path.relative_to(ROOT).as_posix()
        assert name in text, f"NOTICE does not name {name}, which is Unicode data"


def test_the_unicode_copyright_covers_the_newest_vendored_file() -> None:
    """Vendoring a newer Unicode release moves its copyright year; NOTICE must follow."""
    match = re.search(
        r"Copyright © (\d{4})-(\d{4}) Unicode, Inc\.", NOTICE.read_text(encoding="utf-8")
    )
    assert match is not None, "NOTICE has no `Copyright © YYYY-YYYY Unicode, Inc.` line"
    newest = max(_vendored_unicode_files().values())
    assert int(match.group(2)) >= newest, (
        f"NOTICE's Unicode copyright ends in {match.group(2)}, but data/ carries Unicode data "
        f"from {newest}"
    )
