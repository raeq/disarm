#!/usr/bin/env python3
"""Generate confusable TSV files from Unicode TR39 confusables.txt.

Downloads the latest confusables.txt from unicode.org and produces TSV files
for each supported target script. Each TSV maps non-target characters to their
visual equivalents in the target script.

TR39 maps every confusable character to a single prototype, forming equivalence
classes. To generate mappings *to* a target script, we:
  1. Group all characters by their prototype (equivalence class)
  2. For each class, find the member(s) that belong to the target script
  3. Map all non-target members to the target-script member

Output files (written to src/tables/data/):
  confusables_to_latin.tsv    — non-Latin → Latin
  confusables_to_cyrillic.tsv — non-Cyrillic → Cyrillic

(Exact mapping counts vary with the Unicode version; the script prints the
per-file totals it wrote on completion.)

Usage:
    python scripts/gen_confusables.py
    python scripts/gen_confusables.py --input confusables.txt
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
import urllib.request
from collections import defaultdict
from pathlib import Path

CONFUSABLES_URL = "https://www.unicode.org/Public/security/latest/confusables.txt"
DATA_DIR = Path(__file__).resolve().parent.parent / "src" / "tables" / "data"
# Pinned, version-controlled source so regeneration is reproducible (see header).
BUNDLED_CONFUSABLES = Path(__file__).resolve().parent.parent / "data" / "confusables.txt"


# ---------------------------------------------------------------------------
# Codepoint classification
# ---------------------------------------------------------------------------


def is_combining_mark(cp: int) -> bool:
    """True if codepoint is a Unicode combining mark (category M*)."""
    return unicodedata.category(chr(cp)).startswith("M")


def is_latin(cp: int) -> bool:
    """True if codepoint is in a Latin block."""
    return (
        (0x0041 <= cp <= 0x005A)  # A-Z
        or (0x0061 <= cp <= 0x007A)  # a-z
        or (0x00C0 <= cp <= 0x024F)  # Latin Extended-A/B
        or (0x1E00 <= cp <= 0x1EFF)  # Latin Extended Additional
        or (0x2C60 <= cp <= 0x2C7F)  # Latin Extended-C
        or (0xA720 <= cp <= 0xA7FF)  # Latin Extended-D
        or (0xAB30 <= cp <= 0xAB6F)  # Latin Extended-E
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


def is_basic_ascii_letter(cp: int) -> bool:
    """True if codepoint is a basic ASCII letter A-Z / a-z (already canonical)."""
    return (0x0041 <= cp <= 0x005A) or (0x0061 <= cp <= 0x007A)


def is_cyrillic(cp: int) -> bool:
    """True if codepoint is in a Cyrillic block."""
    return (
        (0x0400 <= cp <= 0x04FF)  # Cyrillic
        or (0x0500 <= cp <= 0x052F)  # Cyrillic Supplement
        or (0x2DE0 <= cp <= 0x2DFF)  # Cyrillic Extended-A
        or (0xA640 <= cp <= 0xA69F)  # Cyrillic Extended-B
    )


# ---------------------------------------------------------------------------
# Target script definitions
# ---------------------------------------------------------------------------

SCRIPTS = {
    "latin": {
        "is_target": is_latin,
        "is_target_or_common": is_latin_or_common,
    },
    "cyrillic": {
        "is_target": is_cyrillic,
        "is_target_or_common": lambda cp: is_cyrillic(cp) or is_combining_mark(cp),
    },
}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


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


def build_equivalence_classes(
    entries: list[tuple[int, list[int]]],
) -> dict[tuple[int, ...], set[int]]:
    """Build equivalence classes from TR39 confusables.

    TR39 maps each source character to a prototype. Characters sharing the
    same prototype form an equivalence class. We group all sources by their
    prototype and also include the prototype itself.

    Returns: {prototype_key: {member_cp, ...}}
    """
    classes: dict[tuple[int, ...], set[int]] = defaultdict(set)
    for source_cp, target_cps in entries:
        key = tuple(target_cps)
        classes[key].add(source_cp)
        # If the prototype is a single codepoint, it's also a class member
        if len(target_cps) == 1:
            classes[key].add(target_cps[0])
    return dict(classes)


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def strip_combining(target_cps: list[int]) -> list[int]:
    """Remove combining marks from target codepoints."""
    return [cp for cp in target_cps if not is_combining_mark(cp)]


def fix_case_mismatch(source_cp: int, target_str: str) -> str:
    """Ensure case consistency between source and target.

    If source is uppercase and target is lowercase (or vice versa),
    adjust the target to match. Special case: the {I, l, 1} class
    where uppercase should map to I, not L.
    """
    if len(target_str) != 1 or not target_str.isalpha():
        return target_str
    source_cat = unicodedata.category(chr(source_cp))
    target_cat = unicodedata.category(target_str)
    if source_cat == "Lu" and target_cat == "Ll":
        if target_str == "l":
            return "I"
        return target_str.upper()
    if source_cat == "Ll" and target_cat == "Lu":
        return target_str.lower()
    return target_str


def filter_direct(
    entries: list[tuple[int, list[int]]],
    script_name: str,
) -> list[tuple[int, str]]:
    """Direct filtering: keep entries where the TR39 target is in the target script.

    This is the original approach — works well for Latin (where the prototype
    IS the Latin character) but misses cases where the target script member
    is a source, not a prototype.
    """
    script = SCRIPTS[script_name]
    is_target = script["is_target"]
    is_target_or_common = script["is_target_or_common"]

    result = []
    for source_cp, target_cps in entries:
        # Skip same-script → same-script
        if is_target(source_cp):
            continue
        # Skip digits as sources
        if 0x0030 <= source_cp <= 0x0039:
            continue
        cleaned_cps = strip_combining(target_cps)
        if not all(is_target_or_common(cp) for cp in cleaned_cps):
            continue
        target_str = "".join(chr(cp) for cp in cleaned_cps)
        if not target_str.strip():
            continue
        target_str = fix_case_mismatch(source_cp, target_str)
        result.append((source_cp, target_str))
    return result


def filter_via_classes(
    entries: list[tuple[int, list[int]]],
    script_name: str,
) -> list[tuple[int, str]]:
    """Equivalence-class filtering: for each class, map non-target members
    to the target-script member.

    This catches cases like Latin A → Cyrillic А, where TR39 maps
    Cyrillic А → Latin A (prototype). We invert: Latin A → Cyrillic А.
    """
    script = SCRIPTS[script_name]
    is_target = script["is_target"]
    classes = build_equivalence_classes(entries)

    result_map: dict[int, str] = {}

    for _proto_key, members in classes.items():
        # Find single-codepoint target-script members in this class
        target_members_upper: list[int] = []
        target_members_lower: list[int] = []
        target_members_other: list[int] = []

        for m in members:
            if is_target(m):
                # Never accept a combining mark as a target: it is invisible on
                # its own and folding a visible source onto one would itself be
                # an obfuscation vector. Skipping drops classes whose only
                # target-script member is a combining mark.
                if is_combining_mark(m):
                    continue
                cat = unicodedata.category(chr(m))
                if cat == "Lu":
                    target_members_upper.append(m)
                elif cat == "Ll":
                    target_members_lower.append(m)
                else:
                    target_members_other.append(m)

        if not (target_members_upper or target_members_lower or target_members_other):
            continue

        # Prefer lowest codepoint (basic block) over extended/supplement
        target_members_upper.sort()
        target_members_lower.sort()
        target_members_other.sort()

        # For each non-target member, map to the appropriate target member
        for m in members:
            if is_target(m):
                continue  # Don't map target→target
            # Skip digits
            if 0x0030 <= m <= 0x0039:
                continue

            source_cat = unicodedata.category(chr(m))

            # Pick the target member with matching case
            target_cp = None
            if source_cat == "Lu" and target_members_upper:
                target_cp = target_members_upper[0]
            elif source_cat == "Ll" and target_members_lower:
                target_cp = target_members_lower[0]
            elif target_members_lower:
                target_cp = target_members_lower[0]
            elif target_members_upper:
                target_cp = target_members_upper[0]
            elif target_members_other:
                target_cp = target_members_other[0]

            if target_cp is not None:
                target_str = chr(target_cp)
                target_str = fix_case_mismatch(m, target_str)
                # Only keep if not already mapped (direct takes priority)
                if m not in result_map:
                    result_map[m] = target_str

    return list(result_map.items())


def filter_latin_homoglyphs(
    entries: list[tuple[int, list[int]]],
) -> list[tuple[int, str]]:
    """Latin-script characters that are confusable with a *basic ASCII* letter.

    ``filter_direct`` skips every Latin-script source for the Latin target
    (``is_target(source_cp)`` is true), which drops genuine homoglyphs of ASCII
    letters that happen to live in Latin Extended blocks — e.g. þ→p, ſ→f, ı→i,
    ƒ→f, Ɩ→l. These must fold for confusable normalization. This pass recovers
    exactly that case: a non-ASCII Latin-script source whose TR39 prototype is a
    single basic ASCII letter.
    """
    result: dict[int, str] = {}
    for source_cp, target_cps in entries:
        if not is_latin(source_cp):
            continue  # cross-script sources are handled by filter_direct
        if is_basic_ascii_letter(source_cp):
            continue  # already canonical
        if 0x0030 <= source_cp <= 0x0039:
            continue  # digits
        cleaned = strip_combining(target_cps)
        if len(cleaned) != 1 or not is_basic_ascii_letter(cleaned[0]):
            continue  # prototype must be a single basic ASCII letter
        target_str = fix_case_mismatch(source_cp, chr(cleaned[0]))
        if target_str == chr(source_cp):
            continue  # never self-map
        result[source_cp] = target_str
    return list(result.items())


def generate_mappings(
    entries: list[tuple[int, list[int]]],
    script_name: str,
) -> list[tuple[int, str]]:
    """Generate all mappings for a target script.

    For Latin: use direct filtering only (TR39 prototypes are Latin, so
    direct filtering catches everything).

    For non-Latin targets (Cyrillic, etc.): combine direct filtering with
    equivalence-class inversion. Direct catches entries where the TR39
    prototype happens to be in the target script. Class-based catches the
    common case where the target-script member is a *source* in TR39
    (e.g. Cyrillic А → Latin A), which we invert to Latin A → Cyrillic А.
    """
    # Direct: picks up entries where the prototype IS in the target script
    direct = filter_direct(entries, script_name)

    if script_name == "latin":
        # Direct covers cross-script → Latin. Add the intra-Latin homoglyphs of
        # basic ASCII letters that direct skips (þ→p, ſ→f, ı→i, …); direct wins.
        merged = dict(direct)
        for cp, target in filter_latin_homoglyphs(entries):
            merged.setdefault(cp, target)
        # A character that IS a digit (its NFKC decomposition is a single ASCII
        # digit — e.g. the Mathematical Alphanumeric digits 𝟎/𝟏) must fold to
        # that digit, not to a look-alike letter (𝟎→O, 𝟏→l). TR39 puts 0/1 in
        # the O/l confusable classes, so the generic logic picks the letter;
        # override digits here so normalize_confusables keeps numbers numeric (#89).
        for cp in list(merged):
            digit = unicodedata.normalize("NFKC", chr(cp))
            if len(digit) == 1 and "0" <= digit <= "9":
                merged[cp] = digit
        return list(merged.items())

    # For non-Latin: also invert equivalence classes
    direct_map = dict(direct)
    class_based = filter_via_classes(entries, script_name)

    # Merge: direct takes priority
    merged = dict(direct_map)
    for cp, target in class_based:
        if cp not in merged:
            merged[cp] = target

    return list(merged.items())


# ---------------------------------------------------------------------------
# TSV output
# ---------------------------------------------------------------------------


def write_tsv(mappings: list[tuple[int, str]], path: Path) -> None:
    """Write mappings as TSV: HEX_CODEPOINT<tab>value."""
    mappings.sort(key=lambda x: x[0])
    with open(path, "w", encoding="utf-8") as f:
        for source_cp, target_str in mappings:
            escaped = []
            for ch in target_str:
                cp = ord(ch)
                if 0x20 <= cp <= 0x7E and ch != "\\":
                    escaped.append(ch)
                else:
                    escaped.append(f"\\u{{{cp:04X}}}")
            f.write(f"{source_cp:04X}\t{''.join(escaped)}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate confusable TSV files from TR39 confusables.txt"
    )
    parser.add_argument(
        "--input", type=Path, help="Local confusables.txt (default: bundled data/confusables.txt)"
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Fetch the latest confusables.txt from unicode.org instead of the pinned bundled copy",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DATA_DIR,
        help=f"Output directory for TSV files (default: {DATA_DIR})",
    )
    args = parser.parse_args()

    if args.input:
        text = args.input.read_text(encoding="utf-8")
    elif args.download:
        print("Downloading confusables.txt...", file=sys.stderr)
        with urllib.request.urlopen(CONFUSABLES_URL, timeout=30) as resp:  # noqa: S310
            text = resp.read().decode("utf-8")
    else:
        print(f"Using bundled {BUNDLED_CONFUSABLES}", file=sys.stderr)
        text = BUNDLED_CONFUSABLES.read_text(encoding="utf-8")

    entries = parse_confusables(text)
    print(f"Parsed {len(entries)} total entries", file=sys.stderr)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    for script_name in SCRIPTS:
        mappings = generate_mappings(entries, script_name)
        out_path = args.output_dir / f"confusables_to_{script_name}.tsv"
        write_tsv(mappings, out_path)
        print(
            f"  → {script_name}: {len(mappings)} mappings → {out_path.name}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
