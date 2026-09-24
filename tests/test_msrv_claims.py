"""No comment may state an MSRV that `Cargo.toml` does not (#941).

A comment in `src/anomalies.rs` gave the crate's MSRV as 1.81 and justified an explicit
match on the grounds that `is_none_or` (Rust 1.82) was unavailable. The MSRV moved to
1.88 and the comment did not. It then read as a standing convention, and was cited in
review against code that was correct — so the cost of the drift was a reviewer's time and
nearly a needless rewrite.

A version in prose is a claim like any other. This is the cheapest gate that keeps it
true: the number a comment states must be the number the manifest states.

The same holds for the documentation, which is where a user reads the floor. The second
half of this file applies the rule to the README, `docs/`, the binding READMEs,
CONTRIBUTING and the crate's rustdoc, and to the `rust-version` each binding crate
declares.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
#: Prose forms that name the crate's minimum Rust version.
CLAIM = re.compile(r"MSRV\s+(?:is\s+)?(?:=\s*)?(\d+\.\d+)", re.IGNORECASE)


def _declared_msrv() -> str:
    manifest = (ROOT / "Cargo.toml").read_text(encoding="utf-8")
    match = re.search(r'^rust-version\s*=\s*"(\d+\.\d+)"', manifest, re.MULTILINE)
    assert match, "Cargo.toml no longer declares rust-version — update this gate"
    return match.group(1)


def test_no_source_comment_states_a_stale_msrv() -> None:
    declared = _declared_msrv()
    stale: list[str] = []
    for path in sorted((ROOT / "src").rglob("*.rs")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "//" not in line:
                continue
            for claimed in CLAIM.findall(line.split("//", 1)[1]):
                if claimed != declared:
                    rel = path.relative_to(ROOT)
                    stale.append(f"{rel}:{lineno} claims MSRV {claimed}, manifest says {declared}")
    assert not stale, "comments state an MSRV the manifest does not:\n  " + "\n  ".join(stale)


def test_the_gate_can_actually_fail() -> None:
    """A gate anchored to nothing passes forever — #806's lesson, applied here."""
    declared = _declared_msrv()
    assert CLAIM.findall(f"// the crate's MSRV is {declared}") == [declared]
    bogus = "1.0" if declared != "1.0" else "1.1"
    assert CLAIM.findall(f"// MSRV {bogus}") == [bogus] != [declared]


# ---------------------------------------------------------------------------
# The prose a user reads states the same floor (#718 follow-up)
# ---------------------------------------------------------------------------
#
# The gate above reads source comments. The README said "Rust 1.81+" in two places long
# after #718 moved the manifest to 1.88, and `docs/rust/getting-started.md` said
# the same, because nothing read the documentation. `tests/msrv_declared.rs` guards the
# manifest against the resolved graph; these guard the prose against the manifest.

#: Forms that state the crate's Rust floor in prose. Each one is anchored to a word that
#: makes it a *Rust* floor, and to a two-digit minor, so "Python 3.10+", "cargo +1.81"
#: (a measurement, not a claim) and "criterion needs 1.86" do not match.
DOC_CLAIMS = (
    re.compile(r"\bRust\s+(1\.\d{2})(?:\.\d+)?\+"),  # Rust 1.88+
    re.compile(  # toolchain (>= 1.88   /   rustc at least 1.88
        r"\b(?:Rust|rustc|toolchain|MSRV)\b[^\n.]{0,24}?(?:>=|\u2265|at least)\s*(1\.\d{2})\b",
        re.IGNORECASE,
    ),
    re.compile(r"\brustc\s+(1\.\d{2})\b"),  # rustc 1.88
    re.compile(r"\bMSRV\)?\s*(?:is\s+|of\s+|:\s*|=\s*)?(1\.\d{2})\b"),  # MSRV 1.88, (MSRV) is 1.88
    re.compile(
        r"\bminimum supported Rust version\b(?:\s*\(MSRV\))?\s+(?:is\s+)?(1\.\d{2})\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:msrv|rust)-v?(1\.\d{2})\b", re.IGNORECASE),  # shields.io badge
    re.compile(r"\brust-version\s*=\s*\"(1\.\d{2})"),  # a manifest snippet in a doc
)

#: "1.88 or later" only counts on a line that is about Rust; on its own it is too loose.
OR_LATER = re.compile(r"\b(1\.\d{2})(?:\.\d+)?\s+or\s+(?:later|newer|above)\b")
RUST_LINE = re.compile(r"\b(?:Rust|rustc|MSRV|cargo|toolchain)\b", re.IGNORECASE)

#: Binding crates depend on the core, so none of them can build below its floor.
BINDING_MANIFESTS = (
    "bindings/node/Cargo.toml",
    "bindings/ruby/ext/disarm/Cargo.toml",
    "bindings/cabi/Cargo.toml",
    "bindings/java/rust/Cargo.toml",
)


def _doc_claims(line: str) -> list[str]:
    found = [claim for pattern in DOC_CLAIMS for claim in pattern.findall(line)]
    if RUST_LINE.search(line):
        found += OR_LATER.findall(line)
    return found


def _user_facing_docs() -> list[Path]:
    """Every Markdown page a user or contributor reads, plus the crate's rustdoc.

    `CHANGELOG.md`, its archive under `docs/changelog/` and `changelog.d/` are history: an
    entry saying the floor *was* 1.81 is true. Symlinks are skipped so
    `docs/CONTRIBUTING.md` is not read twice.
    """
    archive = ROOT / "docs" / "changelog"
    pages = [p for p in ROOT.glob("*.md") if p.name != "CHANGELOG.md"]
    pages += [p for p in (ROOT / "docs").rglob("*.md") if archive not in p.parents]
    pages += [p for p in (ROOT / "bindings").rglob("*.md") if "node_modules" not in p.parts]
    return sorted(p for p in set(pages) if not p.is_symlink())


def _rustdoc_lines(path: Path) -> list[tuple[int, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [(n, ln) for n, ln in enumerate(lines, 1) if ln.lstrip().startswith(("//!", "///"))]


def test_no_user_facing_doc_states_a_different_rust_floor() -> None:
    declared = _declared_msrv()
    stale: list[str] = []
    for path in _user_facing_docs():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for claimed in _doc_claims(line):
                if claimed != declared:
                    rel = path.relative_to(ROOT)
                    stale.append(f"{rel}:{lineno} states Rust {claimed}: {line.strip()[:90]}")
    for path in sorted((ROOT / "src").rglob("*.rs")):
        for lineno, line in _rustdoc_lines(path):
            for claimed in _doc_claims(line):
                if claimed != declared:
                    rel = path.relative_to(ROOT)
                    stale.append(f"{rel}:{lineno} (rustdoc) states Rust {claimed}")
    assert not stale, (
        f"Cargo.toml declares rust-version = {declared!r}, but these say otherwise:\n  "
        + "\n  ".join(stale)
    )


def test_the_docs_scan_reads_the_pages_that_drifted() -> None:
    """Anchored to the pages that were wrong, so a narrowed glob cannot pass vacuously."""
    scanned = {p.relative_to(ROOT).as_posix() for p in _user_facing_docs()}
    for page in ("README.md", "CONTRIBUTING.md", "docs/index.md", "docs/rust/getting-started.md"):
        assert page in scanned, f"{page} is no longer scanned for a Rust floor"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert _doc_claims(readme), "README.md states no Rust floor the patterns recognise"


def test_the_doc_patterns_can_fail_and_stay_tight() -> None:
    """Every stale form the review named is caught; unrelated versions are not."""
    for stale in (
        "cargo add disarm        # Rust 1.81+     (pure Rust)",
        "The minimum supported Rust version (MSRV) is 1.81.",
        "- Rust stable toolchain (>= 1.70): `rustup update stable`",
        "Requires rustc 1.81.",
        "MSRV 1.81",
        "Rust 1.81 or later is required.",
        "![MSRV](https://img.shields.io/badge/msrv-1.81-blue)",
    ):
        assert _doc_claims(stale), f"not recognised as a Rust floor: {stale!r}"
    for unrelated in (
        "pip install disarm      # Python 3.10+",
        "`cargo +1.81`, `+1.85` and `+1.87` all fail to build a consumer",
        "criterion 0.8 requires 1.86 for its benches",
        "Java 1.8 or later",
        "Ruby 3.1 or later",
    ):
        assert not _doc_claims(unrelated), f"matched an unrelated version: {unrelated!r}"


@pytest.mark.parametrize("manifest", BINDING_MANIFESTS)
def test_every_binding_crate_declares_the_core_floor(manifest: str) -> None:
    """A binding that declares less than the core promises a build no toolchain can do."""
    text = (ROOT / manifest).read_text(encoding="utf-8")
    match = re.search(r'^rust-version\s*=\s*"(\d+\.\d+)"', text, re.MULTILINE)
    assert match, f"{manifest} declares no rust-version"
    assert match.group(1) == _declared_msrv(), (
        f"{manifest} declares rust-version {match.group(1)}; the core it wraps needs "
        f"{_declared_msrv()}, so the binding cannot build below that either"
    )
