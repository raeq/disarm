"""Every version field agrees, and the four glue pins track the minor.

`RELEASING.md` lists eight items, covering nine files and ten `version` fields —
its item 3 names two files, and one of those carries two fields. It records what
happens when one is missed: "the `0.11.1` PR initially left items 5–6 stale —
caught in review before publish". Caught by a person reading a diff. Nothing
else was looking.

A missed site is not a build failure. It is inconsistent metadata on a published
artifact: a wheel that says one version and a gem that says another, or — the case
`RELEASING.md` singles out — a JVM artifact published under a stale Maven version,
because the publish workflow names the upload bundle from the git tag while the
artifact version comes from the Gradle hardcode.

These are file reads, with no import of `disarm`, so this runs in milliseconds and
during a release PR rather than after it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: The files whose version is one field a single regex can find. The remaining
#: three — `package.json`, `package-lock.json` (two fields) and `uv.lock` — need
#: their own parsing, and have dedicated tests below.
SITES: dict[str, str] = {
    "Cargo.toml": r'^version = "([^"]+)"',
    "pyproject.toml": r'^version = "([^"]+)"',
    "bindings/ruby/lib/disarm/version.rb": r'VERSION = "([^"]+)"',
    "CITATION.cff": r'^version: "([^"]+)"',
    "bindings/java/disarm-java/build.gradle.kts": r'^version = "([^"]+)"',
    "bindings/java/disarm-kotlin/build.gradle.kts": r'^version = "([^"]+)"',
}

#: `disarm_core = { package = "disarm", version = "0.<minor>" }` in each binding's
#: glue crate. A **minor-only** requirement, so a patch never touches them and a
#: minor moves all four.
GLUE_CRATES = (
    "bindings/node/Cargo.toml",
    "bindings/ruby/ext/disarm/Cargo.toml",
    "bindings/java/rust/Cargo.toml",
    "bindings/cabi/Cargo.toml",
)
GLUE_PIN = re.compile(r'disarm_core = \{ package = "disarm", version = "([^"]+)"')


def canonical_version() -> str:
    """`Cargo.toml` is the reference the others are compared against."""
    text = (ROOT / "Cargo.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', text, re.MULTILINE)
    assert match, "Cargo.toml has no top-level version"
    return match.group(1)


def test_the_canonical_version_looks_like_one() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", canonical_version()), canonical_version()


@pytest.mark.parametrize(("relative", "pattern"), sorted(SITES.items()))
def test_site_matches_cargo_toml(relative: str, pattern: str) -> None:
    path = ROOT / relative
    assert path.is_file(), f"{relative} is missing; RELEASING.md still lists it"
    match = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    assert match, f"no version found in {relative} — has its syntax changed?"
    assert match.group(1) == canonical_version(), (
        f"{relative} says {match.group(1)}, Cargo.toml says {canonical_version()}. "
        "See RELEASING.md → 'Where the version lives'."
    )


def test_node_package_json_matches() -> None:
    data = json.loads((ROOT / "bindings/node/package.json").read_text(encoding="utf-8"))
    assert data["version"] == canonical_version()


def test_node_package_lock_matches_in_both_places() -> None:
    """Two fields, and missing the second is the documented trap."""
    data = json.loads((ROOT / "bindings/node/package-lock.json").read_text(encoding="utf-8"))
    assert data["version"] == canonical_version(), "package-lock.json top-level version"
    assert data["packages"][""]["version"] == canonical_version(), (
        'package-lock.json packages[""] version — the second field RELEASING.md warns '
        "about. `npm install --package-lock-only` updates both."
    )


def test_uv_lock_matches() -> None:
    """Only the `disarm` entry. The file names many versions."""
    text = (ROOT / "uv.lock").read_text(encoding="utf-8")
    index = text.index('name = "disarm"')
    match = re.search(r'^version = "([^"]+)"', text[index:], re.MULTILINE)
    assert match, "uv.lock has no version under the disarm entry"
    assert match.group(1) == canonical_version(), (
        f"uv.lock says {match.group(1)}; regenerate with `uv lock`"
    )


@pytest.mark.parametrize("relative", GLUE_CRATES)
def test_glue_pin_tracks_the_minor(relative: str) -> None:
    """The four binding glue crates take a minor-only requirement.

    A patch must not touch them — `0.14` already matches `0.14.1`. A minor must
    move all four, and this is what says so out loud rather than leaving it to
    the checklist.
    """
    text = (ROOT / relative).read_text(encoding="utf-8")
    match = GLUE_PIN.search(text)
    assert match, f"{relative} has no disarm_core pin"
    major, minor, _ = canonical_version().split(".")
    assert match.group(1) == f"{major}.{minor}", (
        f"{relative} pins disarm_core at {match.group(1)}, but the core is "
        f"{canonical_version()}. The pin is minor-only: a patch leaves it alone, a "
        "minor moves all four in lockstep. See RELEASING.md."
    )


def test_the_changelog_has_an_entry_for_this_version() -> None:
    """A released version with no changelog section is a release nobody can read.

    Only checked once the version is stamped: on a development commit between
    releases the top section is `[Unreleased]`, and that is correct.
    """
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    version = canonical_version()
    assert f"## [{version}]" in text, (
        f"CHANGELOG.md has no `## [{version}]` section. Stamp it before tagging: "
        "the release PR renames `[Unreleased]`."
    )
