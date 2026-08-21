"""Drift gate: the committed C header must match what the C ABI actually exports (#580).

`bindings/cabi/disarm.h` IS the C ABI contract. Until this gate existed the header was
gitignored and regenerated inside the CI step that then compiled `smoke.c` against it —
so a signature change plus a matching call-site change was internally consistent and
passed. That is exactly how a 2-arg `disarm_normalize_confusables` became 3-arg on #574
with every check green; a human reading the diff caught it, no test did.

The C smoke test answers "do the header, the library and this caller agree right now?".
It cannot answer "would a caller linked against the previous release still work?",
because no previously-shipped caller is in the loop. This test answers the second
question by keeping a committed baseline to diff against.

Same shape as `test_metadata_parity.py`: regenerate, byte-compare, fail with the command
that fixes it. A HARD gate, not advisory — an ABI break that reaches a release is not
recoverable by a patch, because callers are already linked.

Note this gate deliberately does NOT judge whether a change is breaking. It makes every
change *visible*. Deciding that a diff is additive (a new `_opts` entry point) rather
than breaking (a widened signature) is the reviewer's job — the job that actually caught
#574.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
CABI = ROOT / "bindings" / "cabi"
HEADER = CABI / "disarm.h"

#: Appending this to the cabi manifest points its registry `disarm` dependency at the
#: in-repo core, the same redirect ci.yml injects (#374). Without it the header is
#: generated against the last *published* core and an unreleased API is missing.
PATCH = '\n[patch.crates-io]\ndisarm = { path = "../.." }\n'


def _regenerate(dest: pathlib.Path) -> str:
    """Run the generator in a scratch copy of the manifest, return the header text."""
    manifest = CABI / "Cargo.toml"
    original = manifest.read_text(encoding="utf-8")
    saved = HEADER.read_text(encoding="utf-8") if HEADER.exists() else None
    try:
        manifest.write_text(original + PATCH, encoding="utf-8")
        proc = subprocess.run(
            ["cargo", "test", "--features", "headers", "--", "generate_headers"],
            cwd=CABI,
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"header generation failed:\n{proc.stderr}"
        produced = HEADER.read_text(encoding="utf-8")
        # Inside the `try` so `produced` is provably bound at every use, and so a
        # reader does not have to reason about whether the `finally` can fall through
        # to a use of it. The restore below runs either way.
        dest.write_text(produced, encoding="utf-8")
        return produced
    finally:
        # Best-effort restore. Guard it so a failure here cannot replace the real
        # exception — a generation failure must surface as itself, not as whatever
        # went wrong putting the manifest back.
        try:
            manifest.write_text(original, encoding="utf-8")
            if saved is not None:
                HEADER.write_text(saved, encoding="utf-8")
        except OSError:  # pragma: no cover - the original error is the useful one
            pass


@pytest.mark.slow
def test_committed_header_matches_the_exported_abi(tmp_path: pathlib.Path) -> None:
    """The local pre-push gate. In CI the `cabi` job owns this.

    That job already builds the crate with the [patch.crates-io] redirect applied, so it
    diffs the regenerated header with one `git diff --exit-code` and pays nothing extra.
    Running here as well would mean a second full cabi build inside the Python job for
    the same answer, so this skips under CI rather than duplicating it. The arity pin
    below is pure text and always runs, in CI included.
    """
    if os.environ.get("CI"):  # pragma: no cover - the cabi job covers this
        pytest.skip("the cabi CI job runs the header diff; see ci.yml 'C header drift gate'")
    if not HEADER.exists():  # pragma: no cover - source checkout only
        pytest.skip("bindings/cabi/disarm.h not present")
    if shutil.which("cargo") is None:  # pragma: no cover
        pytest.skip("cargo not available; cannot regenerate the header")

    produced = _regenerate(tmp_path / "disarm.h")
    committed = HEADER.read_text(encoding="utf-8")

    if produced != committed:
        import difflib

        diff = "\n".join(
            difflib.unified_diff(
                committed.splitlines(),
                produced.splitlines(),
                fromfile="committed disarm.h",
                tofile="regenerated",
                lineterm="",
                n=2,
            )
        )
        pytest.fail(
            "bindings/cabi/disarm.h is out of date with the C ABI.\n\n"
            "If the change is intentional, regenerate and commit it:\n"
            "  cd bindings/cabi\n"
            "  printf '\\n[patch.crates-io]\\ndisarm = { path = \"../..\" }\\n' >> Cargo.toml\n"
            "  cargo test --features headers -- generate_headers\n"
            "  git checkout Cargo.toml && git add disarm.h\n\n"
            "Then check the diff below is ADDITIVE. Widening an existing function's "
            "signature breaks every linked caller; add a new `_opts` entry point instead "
            "and keep the original delegating to it, as disarm_transliterate does.\n\n"
            f"{diff}"
        )


def test_header_declares_the_stable_two_arg_entry_points() -> None:
    """Pin the arity of the entry points that shipped before 0.14 (#574 regression).

    A byte-diff makes any change visible, but visible is not the same as understood.
    These are the signatures a caller compiled against 0.13 relies on; if one of them
    changes shape, this fails by name rather than as one line in a 346-line diff.
    """
    if not HEADER.exists():  # pragma: no cover
        pytest.skip("bindings/cabi/disarm.h not present")
    header = HEADER.read_text(encoding="utf-8")

    # (symbol, number of comma-separated parameters)
    stable = [
        ("disarm_normalize_confusables", 2),
        ("disarm_transliterate", 1),
        ("disarm_normalize", 2),
        ("disarm_strip_obfuscation", 1),
        ("disarm_analyze_hostname", 1),
        ("disarm_string_free", 1),
    ]
    for symbol, arity in stable:
        decl = _declaration(header, symbol)
        assert decl is not None, f"{symbol} is no longer exported"
        params = decl[decl.index("(") + 1 : decl.rindex(")")].strip()
        found = 0 if params == "void" else params.count(",") + 1
        assert found == arity, (
            f"{symbol} now takes {found} argument(s), was {arity}. Widening an exported "
            f"function breaks every linked caller — add a `_opts` variant instead."
        )


def _declaration(header: str, symbol: str) -> str | None:
    """The single-line declaration for `symbol`, with newlines collapsed."""
    import re

    match = re.search(rf"^[^\n]*\b{re.escape(symbol)}\s*\([^;]*\);", header, re.M | re.S)
    return " ".join(match.group(0).split()) if match else None
