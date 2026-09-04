#!/usr/bin/env python3
"""Measure what a single disarm entry point costs on `wasm32-unknown-unknown` (#695).

Builds a `cdylib` exporting exactly one function and reports its size plus whether the
Hanzi pinyin and CLDR emoji tables are linked. The table check is a byte search for
syllables and emoji names that appear nowhere else.

The size is the softer half. A module grows and shrinks for ordinary reasons, but a table
*appearing* is categorical — it is what regressed in #695, where `strip_format` declared
five steps that neither transliterate nor demojize and linked both tables anyway, at
663 KB against a possible 27 KB.

    python scripts/wasm_size_probe.py                 # every tracked surface
    python scripts/wasm_size_probe.py strip_format    # one
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: `(entry point, call expression)`. The call differs because some presets are fallible.
SURFACES = {
    "strip_format": "disarm::api::strip_format(t).len()",
    "canonicalize": "disarm::api::canonicalize(t).map(|c| c.len()).unwrap_or(0)",
    "canonicalize_strict": "disarm::api::canonicalize_strict(t).map(|c| c.len()).unwrap_or(0)",
    "strip_obfuscation": "disarm::api::strip_obfuscation(t).map(|c| c.len()).unwrap_or(0)",
    "strip_bidi": "disarm::api::strip_bidi(t).len()",
    "collapse_whitespace": "disarm::api::collapse_whitespace(t).len()",
    # #972: removing emoji reads two UCD range tables and no names, so a build that only
    # replaces must not carry the CLDR name trie. This is the surface where that claim
    # can be checked — `TextPipeline` resolves its steps at runtime and links both arms.
    "demojize_replace": 'disarm::emoji::demojize_rust_replace(t, "").len()',
}

#: Byte needles. `zhuang` is a pinyin syllable; `grinning` is a CLDR emoji name.
NEEDLES = {"pinyin": b"zhuang", "emoji": b"grinning"}

CARGO_TOML = """[package]
name = "probe"
version = "0.0.0"
edition = "2021"

[lib]
crate-type = ["cdylib"]

[dependencies]
disarm = {{ path = "{root}", default-features = false }}

[profile.release]
opt-level = "z"
lto = true
codegen-units = 1
panic = "abort"
strip = true

[workspace]
"""

LIB_RS = """#[no_mangle]
pub extern "C" fn p(s: *const std::os::raw::c_char) -> usize {{
    let t = unsafe {{ std::ffi::CStr::from_ptr(s) }}.to_str().unwrap_or("");
    {call}
}}
"""


def measure(name: str, call: str, workdir: pathlib.Path) -> dict[str, object]:
    (workdir / "src").mkdir(parents=True, exist_ok=True)
    (workdir / "Cargo.toml").write_text(CARGO_TOML.format(root=ROOT), encoding="utf-8")
    (workdir / "src" / "lib.rs").write_text(LIB_RS.format(call=call), encoding="utf-8")
    subprocess.run(
        ["cargo", "build", "--release", "--target", "wasm32-unknown-unknown"],
        cwd=workdir,
        check=True,
        capture_output=True,
    )
    wasm = (workdir / "target/wasm32-unknown-unknown/release/probe.wasm").read_bytes()
    return {
        "surface": name,
        "bytes": len(wasm),
        **{label: needle in wasm for label, needle in NEEDLES.items()},
    }


def main(argv: list[str]) -> int:
    if shutil.which("cargo") is None:
        print("cargo not found", file=sys.stderr)
        return 2
    wanted = argv or sorted(SURFACES)
    unknown = [name for name in wanted if name not in SURFACES]
    if unknown:
        print(f"unknown surface(s): {unknown}; known: {sorted(SURFACES)}", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        results = [measure(name, SURFACES[name], pathlib.Path(tmp)) for name in wanted]
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
