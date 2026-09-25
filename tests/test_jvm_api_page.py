"""`docs/java/api.md` against the JVM surface it describes (#981).

The page's "does not have" table listed `canonicalizeStrict` and `stripFormat` long after
both shipped, and its coverage figure was measured by hand once and never again. Nothing
compared the page to the class, which is how a phantom name also reached a javadoc link
and failed the v0.16.0 Java publish.

The surfaces are read the way `scripts/parity.py` reads them (`java_surface`,
`kotlin_surface`), and the figures from the `generated/parity.yaml` it writes.

Run as a script, this file rewrites `tests/fixtures/introspection_lists.tsv`, the lists the
JVM tests compare `listLangs`, `listProfiles` and `reverseLangs` against.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "java" / "api.md"
JAVA = ROOT / "bindings/java/disarm-java/src/main/java/dev/disarm/Disarm.java"
KOTLIN = ROOT / "bindings/java/disarm-kotlin/src/main/kotlin/dev/disarm/kotlin/Disarm.kt"
PARITY = ROOT / "generated" / "parity.yaml"
FIXTURE = ROOT / "tests" / "fixtures" / "introspection_lists.tsv"

ABSENT_HEADING = "## What the JVM surface does not have"


def _java_surface() -> set[str]:
    """`scripts/parity.py`'s `java_surface`: `public static` methods on the facade."""
    return set(
        re.findall(r"public\s+static\s+[\w<>\[\], ]+?\s+([a-zA-Z0-9_]+)\s*\(", JAVA.read_text())
    )


def _kotlin_surface() -> set[str]:
    """`scripts/parity.py`'s `kotlin_surface`: top-level functions, receivers skipped."""
    return set(re.findall(r"^fun\s+(?:[\w<>, ]+\.)?([a-zA-Z0-9_]+)\s*\(", KOTLIN.read_text(), re.M))


def _absent_table() -> list[str]:
    """The backticked names in the first column of the "does not have" table."""
    text = PAGE.read_text(encoding="utf-8")
    section = text.split(ABSENT_HEADING, 1)[1].split("\n## ", 1)[0]
    names: list[str] = []
    for line in section.splitlines():
        if not line.startswith("| `"):
            continue
        first_cell = line.split("|")[1]
        names += re.findall(r"`([A-Za-z0-9_]+)`", first_cell)
    return names


def _lists() -> dict[str, list[str]]:
    """The three lists as a fresh interpreter sees them.

    Not this process's: other tests call `register_lang`, and a registration lives for
    the life of the process, so `list_langs()` here depends on which tests shared the
    worker. The JVM has no registration, so the built-in list is the one to compare.
    """
    code = (
        "import json, disarm; print(json.dumps({"
        "'list_langs': disarm.list_langs(), "
        "'list_profiles': disarm.list_profiles(), "
        "'reverse_langs': disarm.reverse_langs()}))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def _fixture() -> dict[str, list[str]]:
    rows = {}
    for line in FIXTURE.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            key, values = line.split("\t")
            rows[key] = values.split(",")
    return rows


def test_the_absent_table_is_read() -> None:
    names = _absent_table()
    assert "setEmojiProvider" in names, names
    assert len(names) >= 5, names


def test_the_absent_table_names_nothing_the_jvm_declares() -> None:
    declared = _java_surface() | _kotlin_surface()
    shipped = [n for n in _absent_table() if n in declared]
    assert shipped == [], (
        f"docs/java/api.md lists {shipped} as absent from the JVM, and the facade declares "
        "them: take them out of the table"
    )


def test_every_disarm_call_on_the_page_is_declared() -> None:
    called = set(re.findall(r"\bDisarm\.([a-z][A-Za-z0-9]*)\(", PAGE.read_text(encoding="utf-8")))
    missing = sorted(called - _java_surface())
    assert missing == [], f"docs/java/api.md calls Disarm.{missing}, which Disarm.java lacks"


def test_the_coverage_figures_are_the_parity_manifest_s() -> None:
    operations = yaml.safe_load(PARITY.read_text())["operations"]
    covered = sum(1 for op in operations if op["names"].get("java") is not None)
    prose = " ".join(PAGE.read_text(encoding="utf-8").split())
    match = re.search(
        r"Measured against the (\d+) canonical operations in `generated/parity\.yaml`, "
        r"the JVM covers (\d+)\.",
        prose,
    )
    assert match, "docs/java/api.md no longer states its coverage figure"
    assert (int(match[1]), int(match[2])) == (len(operations), covered), (
        f"the page says {match[1]} operations, {match[2]} covered; "
        f"generated/parity.yaml says {len(operations)}, {covered}"
    )


def test_the_introspection_fixture_is_what_python_returns() -> None:
    assert _fixture() == _lists(), (
        "tests/fixtures/introspection_lists.tsv is stale: python tests/test_jvm_api_page.py"
    )


def _write_fixture() -> None:
    lines = [
        "# The core's introspection lists, as every binding must return them (#981).",
        "# Written by tests/test_jvm_api_page.py from the Python binding; read by the JVM tests.",
        "# Regenerate: python tests/test_jvm_api_page.py",
    ]
    lines += [f"{key}\t{','.join(values)}" for key, values in _lists().items()]
    FIXTURE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {FIXTURE.relative_to(ROOT)}", file=sys.stderr)


if __name__ == "__main__":
    _write_fixture()
