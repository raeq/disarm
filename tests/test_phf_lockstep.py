"""phf and phf_codegen move as one pair, on the release the MSRV allows.

`build.rs` writes every lookup table with `phf_codegen`, and the library reads it back
with `phf`. The codegen emits the table in the layout the runtime expects, so the two
must resolve to one release: a split still compiles, and `get` misses
(`src/phf_integrity.rs` pins the tables themselves).

The pair was held on 0.13 by a Dependabot `ignore` because 0.14 moved to edition 2024
and Rust 1.85 while this crate's MSRV was 1.81 (the closed attempt, #509). Since #718 the
MSRV is 1.88, so the hold's reason is gone, and an `ignore` left behind would hide every
later release too.

The manifests are read with regular expressions rather than `tomllib`, which needs
Python 3.11; the package still supports 3.10.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

#: The phf crates this repository builds with. `phf_generator` and `phf_shared` come in
#: through the first two and must land on the same release.
PHF_FAMILY = ("phf", "phf_codegen", "phf_generator", "phf_shared")

#: phf 0.14 requires Rust 1.85 (`rust-version` on crates.io).
PHF_014_RUST_VERSION = (1, 85)


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def _declared(name: str) -> str:
    manifest = (ROOT / "Cargo.toml").read_text(encoding="utf-8")
    match = re.search(rf'^{name}\s*=\s*"([^"]+)"', manifest, re.MULTILINE)
    assert match, f"Cargo.toml declares no {name} requirement"
    return match.group(1)


def _locked() -> dict[str, list[str]]:
    lock = (ROOT / "Cargo.lock").read_text(encoding="utf-8")
    found: dict[str, list[str]] = {}
    for name, version in re.findall(r'^name = "([^"]+)"\nversion = "([^"]+)"', lock, re.MULTILINE):
        if name in PHF_FAMILY:
            found.setdefault(name, []).append(version)
    return found


def _rust_version() -> tuple[int, ...]:
    manifest = (ROOT / "Cargo.toml").read_text(encoding="utf-8")
    match = re.search(r'^rust-version\s*=\s*"([^"]+)"', manifest, re.MULTILINE)
    assert match, "Cargo.toml declares no rust-version"
    return _version(match.group(1))


def test_phf_and_phf_codegen_declare_the_same_requirement() -> None:
    assert _declared("phf") == _declared("phf_codegen")


def test_the_phf_family_resolves_to_one_release() -> None:
    locked = _locked()
    assert set(locked) == set(PHF_FAMILY), f"Cargo.lock is missing part of {PHF_FAMILY}"
    versions = {v for vs in locked.values() for v in vs}
    assert len(versions) == 1, f"the phf family resolves to several releases: {locked}"


def test_the_phf_pair_is_on_the_release_the_msrv_allows() -> None:
    assert _rust_version() >= PHF_014_RUST_VERSION
    (version,) = set(_locked()["phf"])
    assert _version(version)[:2] >= (0, 14), (
        f"phf resolves to {version}; the MSRV ({'.'.join(map(str, _rust_version()))}) "
        "allows 0.14, which needs Rust 1.85"
    )


def test_dependabot_does_not_hold_the_phf_pair_back() -> None:
    config = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text())
    held = [
        (update.get("directory") or update.get("directories"), rule["dependency-name"])
        for update in config["updates"]
        if update["package-ecosystem"] == "cargo"
        for rule in update.get("ignore", [])
        if rule.get("dependency-name") in PHF_FAMILY
    ]
    assert held == [], (
        f"Dependabot still ignores {held}: the hold was for an MSRV of 1.81, and the MSRV "
        "is now 1.88"
    )
