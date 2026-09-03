"""No comment may state an MSRV that `Cargo.toml` does not (#941).

A comment in `src/anomalies.rs` gave the crate's MSRV as 1.81 and justified an explicit
match on the grounds that `is_none_or` (Rust 1.82) was unavailable. The MSRV moved to
1.88 and the comment did not. It then read as a standing convention, and was cited in
review against code that was correct — so the cost of the drift was a reviewer's time and
nearly a needless rewrite.

A version in prose is a claim like any other. This is the cheapest gate that keeps it
true: the number a comment states must be the number the manifest states.
"""

from __future__ import annotations

import re
from pathlib import Path

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
