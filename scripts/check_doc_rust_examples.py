#!/usr/bin/env python3
"""Compile-and-run every ```rust block in the docs (#50 phase 5).

The user guide shows per-language usage in tabs; the Rust tabs use `assert_eq!`
so they are real, checkable examples rather than decorative snippets. This script
is their gate — the Rust analogue of the Sybil doc-test gate for Python:

1. Extract every ```rust fenced block from docs/ (including those indented inside
   `pymdownx.tabbed` tabs).
2. Generate a throwaway integration test (one `#[test]` per block) under tests/.
3. `cargo test` it against the pure-Rust core.

`#![deny(unused_must_use)]` is set so an example that *discards* a `#[must_use]`
return (a `Result`, a `Vec`, a `Cow`) is a hard error — that forces every example
to actually assert its output, which is what keeps the documented Rust behaviour
honest. A shared `use` preamble is injected and each block's own `use` lines are
stripped, so blocks stay copy-pasteable in the docs without colliding here.

Usage:
    python3 scripts/check_doc_rust_examples.py            # generate + cargo test
    python3 scripts/check_doc_rust_examples.py --generate # write the test only
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
OUT = ROOT / "tests" / "_doc_rust_examples.rs"

_FENCE = re.compile(r"(?m)^([ \t]*)```rust\n(.*?)\n[ \t]*```", re.DOTALL)
_MAIN = re.compile(r"\s*fn main\s*\(\)\s*\{?\s*$")
# Opt-out for a block that is illustration (a trait sketch, a macro), not a
# runnable example. Deliberately NOT Sybil's `<!--- skip: next -->`: that directive
# is consumed by Sybil's Python skip state machine, and placing it before a
# (non-Python) rust block on a Sybil-executed page raises "skip: next cannot
# follow skip: next". This marker contains no `skip:` token, so Sybil ignores it.
_SKIP = "<!--- rust-skip -->"


def _unwrap(lines: list[str]) -> list[str]:
    """Keep each block verbatim — including its own `use` lines, so it is checked
    exactly as a reader would copy it — except for an optional `fn main() { ... }`
    wrapper, which is unwrapped (its closing `}` removed). A standalone `}` that
    does not belong to a `fn main` wrapper is kept (it may close a real
    `if`/`match`/closure in the snippet)."""
    kept = list(lines)
    if any(_MAIN.match(ln) for ln in kept):
        kept = [ln for ln in kept if not _MAIN.match(ln)]
        for i in range(len(kept) - 1, -1, -1):  # drop the matching close brace
            if kept[i].strip() == "}":
                del kept[i]
                break
    return kept


def _blocks() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for md in sorted(DOCS.rglob("*.md")):
        text = md.read_text(encoding="utf-8")
        for m in _FENCE.finditer(text):
            preceding = text[: m.start()].rstrip()
            if preceding.endswith(_SKIP):
                continue
            indent, body = m.group(1), m.group(2)
            lines = [ln[len(indent) :] if ln.startswith(indent) else ln for ln in body.split("\n")]
            found.append((md.relative_to(ROOT).as_posix(), "\n".join(_unwrap(lines))))
    return found


def _render(blocks: list[tuple[str, str]]) -> str:
    # The `//!` lines give the generated crate the doc that `missing_docs`
    # requires (so we satisfy that lint rather than silence it). No blanket
    # allows: examples are held to the same warnings bar as the crate (CI builds
    # with `-D warnings`), and `deny(unused_must_use)` additionally forces each
    # example to use its result. Each block carries its own `use`, so it compiles
    # exactly as a reader would copy it.
    out = [
        "//! AUTO-GENERATED doc-example tests — see scripts/check_doc_rust_examples.py.",
        "//! Do not edit or commit (gitignored).",
        "#![deny(unused_must_use)]",
    ]
    for i, (src, body) in enumerate(blocks):
        out.append(f"#[test]\nfn doc_{i}() {{ // {src}\n{body}\n}}")
    return "\n\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    blocks = _blocks()
    OUT.write_text(_render(blocks), encoding="utf-8")
    print(f"generated {OUT.relative_to(ROOT)} — {len(blocks)} rust doc blocks")
    if "--generate" in argv:
        return 0
    proc = subprocess.run(
        ["cargo", "test", "--test", "_doc_rust_examples", "--no-default-features"],
        cwd=ROOT,
    )
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
