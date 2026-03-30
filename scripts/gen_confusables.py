#!/usr/bin/env python3
"""Generate confusables_data.rs from Unicode TR39 confusables.txt.

Downloads the latest confusables.txt from unicode.org and produces a PHF
map of non-Latin → Latin confusable mappings for use in translit's
homoglyph detection and normalization.

Usage:
    python scripts/gen_confusables.py > src/tables/confusables_data.rs

Or with a local file:
    python scripts/gen_confusables.py --input confusables.txt
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

CONFUSABLES_URL = "https://www.unicode.org/Public/security/latest/confusables.txt"


def is_combining_mark(cp: int) -> bool:
    """True if codepoint is a Unicode combining mark."""
    return (
        (0x0300 <= cp <= 0x036F)  # Combining Diacritical Marks
        or (0x1AB0 <= cp <= 0x1AFF)  # Combining Diacritical Marks Extended
        or (0x1DC0 <= cp <= 0x1DFF)  # Combining Diacritical Marks Supplement
        or (0x20D0 <= cp <= 0x20FF)  # Combining Diacritical Marks for Symbols
        or (0xFE20 <= cp <= 0xFE2F)  # Combining Half Marks
    )


def is_latin_or_common(cp: int) -> bool:
    """True if codepoint is Latin script, ASCII Common, or combining mark."""
    return (
        (0x0000 <= cp <= 0x007F)  # Basic Latin (ASCII)
        or (0x00C0 <= cp <= 0x024F)  # Latin Extended-A/B
        or (0x1E00 <= cp <= 0x1EFF)  # Latin Extended Additional
        or (0x2C60 <= cp <= 0x2C7F)  # Latin Extended-C
        or (0xA720 <= cp <= 0xA7FF)  # Latin Extended-D
        or (0xAB30 <= cp <= 0xAB6F)  # Latin Extended-E
        or is_combining_mark(cp)  # Combining marks (stripped downstream)
    )


def is_latin_source(cp: int) -> bool:
    """True if codepoint is in a Latin block (exclude from source)."""
    return (
        (0x0041 <= cp <= 0x005A)  # A-Z
        or (0x0061 <= cp <= 0x007A)  # a-z
        or (0x00C0 <= cp <= 0x024F)  # Latin Extended-A/B
        or (0x1E00 <= cp <= 0x1EFF)  # Latin Extended Additional
        or (0x2C60 <= cp <= 0x2C7F)  # Latin Extended-C
        or (0xA720 <= cp <= 0xA7FF)  # Latin Extended-D
        or (0xAB30 <= cp <= 0xAB6F)  # Latin Extended-E
    )


def parse_confusables(text: str) -> list[tuple[int, list[int]]]:
    """Parse confusables.txt into (source_cp, target_cps) pairs."""
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(";")
        if len(parts) < 3:
            continue
        source_cp = int(parts[0].strip(), 16)
        target_cps = [int(h, 16) for h in parts[1].strip().split()]
        entries.append((source_cp, target_cps))
    return entries


def strip_combining(target_cps: list[int]) -> list[int]:
    """Remove combining marks from target codepoints.

    TR39 targets sometimes include combining marks (e.g. η → n̩ where
    U+0329 is COMBINING VERTICAL LINE BELOW). Since our pipeline strips
    accents/marks downstream, we drop them here to avoid rejecting
    otherwise valid Latin targets.
    """
    return [cp for cp in target_cps if not is_combining_mark(cp)]


def fix_case_mismatch(source_cp: int, target_str: str) -> str:
    """Ensure uppercase sources map to uppercase Latin targets.

    TR39 maps all members of a confusable class to a single prototype.
    For the {I, l, 1, Ι} class, the prototype is 'l'. But an uppercase
    non-Latin source (like Greek Ι) should map to 'I' (uppercase Latin),
    not 'L' (which would be a naive upper() of 'l').

    Special case: prototype 'l' + uppercase source → 'I', because
    Latin I (not L) is the uppercase member of the l/I/1 class.
    For all other single lowercase ASCII targets, upper() is correct.
    """
    import unicodedata

    if len(target_str) != 1 or not target_str.isascii() or not target_str.isalpha():
        return target_str
    source_cat = unicodedata.category(chr(source_cp))
    if source_cat == "Lu" and target_str.islower():
        # The {I, l, 1} class: uppercase member is I, not L
        if target_str == "l":
            return "I"
        return target_str.upper()
    return target_str


def filter_to_latin(
    entries: list[tuple[int, list[int]]],
) -> list[tuple[int, str]]:
    """Keep only non-Latin source → Latin/ASCII target mappings."""
    result = []
    for source_cp, target_cps in entries:
        # Skip Latin→Latin (not useful for confusable detection)
        if is_latin_source(source_cp):
            continue
        # Skip digits and basic punctuation as sources
        if 0x0030 <= source_cp <= 0x0039:
            continue
        # Strip combining marks from target (stripped downstream anyway)
        cleaned_cps = strip_combining(target_cps)
        # Target must be entirely Latin/Common (after stripping marks)
        if not all(is_latin_or_common(cp) for cp in cleaned_cps):
            continue
        # Target must contain at least one visible character
        target_str = "".join(chr(cp) for cp in cleaned_cps)
        if not target_str.strip():
            continue
        # Fix case: uppercase source should map to uppercase target
        target_str = fix_case_mismatch(source_cp, target_str)
        result.append((source_cp, target_str))
    return result


def rust_char_literal(cp: int) -> str:
    """Format a codepoint as a Rust char literal."""
    return f"'\\u{{{cp:04X}}}'"


def rust_str_escape(s: str) -> str:
    """Escape a string for Rust string literal."""
    result = []
    for ch in s:
        cp = ord(ch)
        if 0x20 <= cp <= 0x7E and ch != '"' and ch != "\\":
            result.append(ch)
        else:
            result.append(f"\\u{{{cp:04X}}}")
    return "".join(result)


def generate_rust(mappings: list[tuple[int, str]], version_line: str) -> str:
    """Generate the confusables_data.rs file content."""
    # Sort by codepoint for reproducibility
    mappings.sort(key=lambda x: x[0])

    lines = []
    lines.append("//! Unicode TR39 confusable character mappings (non-Latin → Latin).")
    lines.append("//!")
    lines.append("//! Auto-generated from confusables.txt by scripts/gen_confusables.py.")
    lines.append(f"//! {version_line}")
    lines.append("//!")
    lines.append(f"//! Contains {len(mappings)} mappings from non-Latin scripts to Latin")
    lines.append("//! equivalents. Uses compile-time perfect hash maps (`phf`) for O(1)")
    lines.append("//! lookups. Covers Cyrillic, Greek, Armenian, Georgian, CJK compatibility,")
    lines.append("//! mathematical symbols, fullwidth forms, and other confusable characters.")
    lines.append("//!")
    lines.append("//! DO NOT EDIT — regenerate with: python scripts/gen_confusables.py")
    lines.append("")
    lines.append("use phf::phf_map;")
    lines.append("")
    lines.append("/// Non-Latin → Latin confusable mappings (O(1) PHF lookup).")
    lines.append("///")
    lines.append("/// Maps visually similar non-Latin characters to their Latin prototypes")
    lines.append("/// per Unicode Technical Report #39.")
    lines.append("static TO_LATIN: phf::Map<char, &'static str> = phf_map! {")

    for source_cp, target_str in mappings:
        source_char = rust_char_literal(source_cp)
        target_escaped = rust_str_escape(target_str)
        # Add a comment with character names for readability
        source_name = chr(source_cp)
        if len(target_str) == 1:
            comment = f"// {source_name} → {target_str}"
        else:
            comment = f'// {source_name} → "{target_str}"'
        lines.append(f'    {source_char} => "{target_escaped}", {comment}')

    lines.append("};")
    lines.append("")
    lines.append("/// Look up a confusable mapping for a character to the target script.")
    lines.append("///")
    lines.append("/// Returns the Latin prototype string if the character is a known")
    lines.append("/// confusable, or None if it is not.")
    lines.append("#[inline]")
    lines.append("pub fn lookup(ch: char, target_script: &str) -> Option<&'static str> {")
    lines.append('    if target_script != "latin" {')
    lines.append("        return None;")
    lines.append("    }")
    lines.append("")
    lines.append("    TO_LATIN.get(&ch).copied()")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate confusables_data.rs")
    parser.add_argument("--input", type=Path, help="Local confusables.txt (default: download)")
    args = parser.parse_args()

    if args.input:
        text = args.input.read_text(encoding="utf-8")
    else:
        print("Downloading confusables.txt...", file=sys.stderr)
        with urllib.request.urlopen(CONFUSABLES_URL) as resp:
            text = resp.read().decode("utf-8")

    # Extract version line
    version_line = ""
    for line in text.splitlines():
        if line.startswith("# Version:"):
            version_line = line.lstrip("# ").strip()
            break

    entries = parse_confusables(text)
    mappings = filter_to_latin(entries)

    print(
        f"Parsed {len(entries)} total entries, "
        f"filtered to {len(mappings)} non-Latin → Latin mappings",
        file=sys.stderr,
    )

    rust_code = generate_rust(mappings, version_line)
    print(rust_code)


if __name__ == "__main__":
    main()
