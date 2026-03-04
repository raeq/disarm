#!/usr/bin/env python3
"""Generate src/tables/emoji_data.rs from Unicode CLDR annotation files.

Usage:
    python scripts/gen_emoji_data.py

Requires data/cldr/en.xml and data/cldr/en_derived.xml to be present.
Download from:
    https://raw.githubusercontent.com/unicode-org/cldr/main/common/annotations/en.xml
    https://raw.githubusercontent.com/unicode-org/cldr/main/common/annotationsDerived/en.xml
"""

import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_tts_entries(*paths: Path) -> dict[tuple[int, ...], str]:
    entries: dict[tuple[int, ...], str] = {}
    for path in paths:
        tree = ET.parse(path)
        for ann in tree.getroot().iter("annotation"):
            if ann.get("type") == "tts":
                cp = ann.get("cp")
                text = (ann.text or "").strip()
                codepoints = tuple(ord(c) for c in cp)
                entries[codepoints] = text
    return entries


def filter_emoji(entries: dict[tuple[int, ...], str]) -> dict[tuple[int, ...], str]:
    """Keep only entries with at least one codepoint >= U+2000."""
    return {cps: text for cps, text in entries.items() if any(c >= 0x2000 for c in cps)}


def escape_rust_str(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def generate(entries: dict[tuple[int, ...], str]) -> str:
    single = {cps[0]: text for cps, text in entries.items() if len(cps) == 1}
    multi = {cps: text for cps, text in entries.items() if len(cps) > 1}

    lines = [
        "//! Emoji annotation data derived from Unicode CLDR.",
        "//! Generated from CLDR annotations/en.xml and annotationsDerived/en.xml.",
        "//! Do not edit manually — regenerate with scripts/gen_emoji_data.py.",
        "",
        "use phf::phf_map;",
        "",
        f"/// Single-codepoint emoji to short name ({len(single)} entries).",
        "pub static EMOJI_SINGLE: phf::Map<char, &'static str> = phf_map! {",
    ]
    for cp in sorted(single):
        lines.append(f"    '\\u{{{cp:04X}}}' => \"{escape_rust_str(single[cp])}\",")
    lines.append("};")
    lines.append("")

    lines.append(f"/// Multi-codepoint emoji sequences to short name ({len(multi)} entries).")
    lines.append("/// Key format: codepoints as uppercase hex separated by underscores.")
    lines.append("pub static EMOJI_MULTI: phf::Map<&'static str, &'static str> = phf_map! {")
    for cps in sorted(multi):
        key = "_".join(f"{c:04X}" for c in cps)
        lines.append(f'    "{key}" => "{escape_rust_str(multi[cps])}",')
    lines.append("};")
    lines.append("")

    starters = sorted({cps[0] for cps in multi})
    lines.append(f"/// Codepoints that can begin a multi-codepoint emoji sequence ({len(starters)} entries).")
    lines.append("pub static EMOJI_MULTI_STARTERS: phf::Set<char> = phf::phf_set! {")
    for cp in starters:
        lines.append(f"    '\\u{{{cp:04X}}}',")
    lines.append("};")
    lines.append("")

    max_len = max(len(cps) for cps in multi) if multi else 1
    lines.append(f"/// Maximum codepoint length of any emoji sequence in EMOJI_MULTI.")
    lines.append(f"pub const MAX_EMOJI_SEQ_LEN: usize = {max_len};")
    lines.append("")

    return "\n".join(lines)


def main():
    base = ROOT / "data" / "cldr" / "en.xml"
    derived = ROOT / "data" / "cldr" / "en_derived.xml"
    entries = filter_emoji(parse_tts_entries(base, derived))
    content = generate(entries)

    out = ROOT / "src" / "tables" / "emoji_data.rs"
    out.write_text(content)
    print(f"Wrote {out} ({len(entries)} entries, {len(content)} bytes)")


if __name__ == "__main__":
    main()
