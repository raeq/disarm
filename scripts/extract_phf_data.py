#!/usr/bin/env python3
"""
Extract PHF map/set data from Rust source files into TSV format.

Reads phf_map! and phf_set! macro invocations and outputs data as TSV files.
"""

import re
from pathlib import Path


def extract_char_map(content, map_name):
    r"""
    Extract entries from a char -> &'static str phf_map!

    Pattern: '\u{XXXX}' => "value",
    Returns: list of (hex_codepoint, value) tuples
    """
    entries = []

    # Find the map declaration
    map_start = content.find(f"static {map_name}:")
    if map_start == -1:
        return entries

    # Find the phf_map! { block
    map_pattern_start = content.find("phf_map! {", map_start)
    if map_pattern_start == -1:
        return entries

    # The opening brace is at position of "phf_map! " + length
    brace_open_pos = map_pattern_start + len("phf_map! ")

    # Find the closing brace - count braces but start from 1 (for the opening {)
    brace_count = 1
    i = brace_open_pos + 1
    in_string = False
    escape_next = False
    block_end = len(content)

    while i < len(content):
        char = content[i]

        if escape_next:
            escape_next = False
            i += 1
            continue

        if char == "\\":
            escape_next = True
            i += 1
            continue

        if char == '"' and not in_string:
            in_string = True
            i += 1
            continue

        if char == '"' and in_string:
            in_string = False
            i += 1
            continue

        if in_string:
            i += 1
            continue

        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0:
                block_end = i
                break

        i += 1

    block_content = content[brace_open_pos + 1 : block_end]

    # Parse char -> string entries: '\u{XXXX}' => "value",
    # Need to handle values that may contain escape sequences like \u{XXXX}
    # Use a more careful parsing approach
    pattern = r"'\\u\{([0-9A-Fa-f]+)\}'\s*=>\s*\"((?:[^\"\\]|\\.)*)\""

    for match in re.finditer(pattern, block_content):
        hex_code = match.group(1)
        value = match.group(2)

        # Keep the raw string content with escape sequences as-is
        entries.append((hex_code.upper(), value))

    return entries


def extract_str_map(content, map_name):
    r"""
    Extract entries from a &'static str -> &'static str phf_map!

    Pattern: "key" => "value",
    Returns: list of (key, value) tuples
    """
    entries = []

    # Find the map declaration
    map_start = content.find(f"static {map_name}:")
    if map_start == -1:
        return entries

    # Find the phf_map! { block
    map_pattern_start = content.find("phf_map! {", map_start)
    if map_pattern_start == -1:
        return entries

    # The opening brace is at position of "phf_map! " + length
    brace_open_pos = map_pattern_start + len("phf_map! ")

    # Find the closing brace - count braces but start from 1 (for the opening {)
    brace_count = 1
    i = brace_open_pos + 1
    in_string = False
    escape_next = False
    block_end = len(content)

    while i < len(content):
        char = content[i]

        if escape_next:
            escape_next = False
            i += 1
            continue

        if char == "\\":
            escape_next = True
            i += 1
            continue

        if char == '"' and not in_string:
            in_string = True
            i += 1
            continue

        if char == '"' and in_string:
            in_string = False
            i += 1
            continue

        if in_string:
            i += 1
            continue

        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0:
                block_end = i
                break

        i += 1

    block_content = content[brace_open_pos + 1 : block_end]

    # Parse string -> string entries: "key" => "value",
    pattern = r'"([^"]*?)"\s*=>\s*"([^"]*?)"'

    for match in re.finditer(pattern, block_content):
        key = match.group(1)
        value = match.group(2)
        entries.append((key, value))

    return entries


def extract_char_set(content, set_name):
    r"""
    Extract entries from a char phf_set!

    Pattern: '\u{XXXX}',
    Returns: list of hex_codepoint strings
    """
    entries = []

    # Find the set declaration
    set_start = content.find(f"static {set_name}:")
    if set_start == -1:
        return entries

    # Find the phf_set! { block (or phf::phf_set! {)
    map_pattern_start = content.find("phf_set! {", set_start)
    if map_pattern_start == -1:
        map_pattern_start = content.find("phf::phf_set! {", set_start)
        if map_pattern_start == -1:
            return entries
        map_pattern_start += len("phf::")
        brace_open_pos = map_pattern_start + len("phf_set! ")
    else:
        brace_open_pos = map_pattern_start + len("phf_set! ")

    # Find the closing brace - count braces but start from 1 (for the opening {)
    brace_count = 1
    i = brace_open_pos + 1
    in_string = False
    escape_next = False
    block_end = len(content)

    while i < len(content):
        char = content[i]

        if escape_next:
            escape_next = False
            i += 1
            continue

        if char == "\\":
            escape_next = True
            i += 1
            continue

        if char == '"' and not in_string:
            in_string = True
            i += 1
            continue

        if char == '"' and in_string:
            in_string = False
            i += 1
            continue

        if in_string:
            i += 1
            continue

        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0:
                block_end = i
                break

        i += 1

    block_content = content[brace_open_pos + 1 : block_end]

    # Parse char entries: '\u{XXXX}',
    pattern = r"'\\u\{([0-9A-Fa-f]+)\}'"

    for match in re.finditer(pattern, block_content):
        hex_code = match.group(1)
        entries.append(hex_code.upper())

    return entries


def write_tsv_char_map(filepath, entries):
    """Write char->str entries to TSV file."""
    with open(filepath, "w", encoding="utf-8") as f:
        for hex_code, value in entries:
            f.write(f"{hex_code}\t{value}\n")


def write_tsv_str_map(filepath, entries):
    """Write str->str entries to TSV file."""
    with open(filepath, "w", encoding="utf-8") as f:
        for key, value in entries:
            f.write(f"{key}\t{value}\n")


def write_tsv_set(filepath, entries):
    """Write set entries to TSV file (one per line)."""
    with open(filepath, "w", encoding="utf-8") as f:
        for hex_code in entries:
            f.write(f"{hex_code}\n")


def main():
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "src" / "tables" / "data"

    # Create data directory
    data_dir.mkdir(parents=True, exist_ok=True)
    print(f"Created/verified directory: {data_dir}")

    # 1. Extract hanzi_pinyin
    print("\nProcessing hanzi_pinyin.rs...")
    with open(base_dir / "src" / "tables" / "hanzi_pinyin.rs") as f:
        content = f.read()
    entries = extract_char_map(content, "HANZI_PINYIN")
    write_tsv_char_map(data_dir / "hanzi_pinyin.tsv", entries)
    print(f"  Extracted {len(entries)} entries → hanzi_pinyin.tsv")

    # 2. Confusables — TSVs are generated directly by gen_confusables.py,
    #    not extracted from Rust source. Skip extraction here.
    print("\nConfusables: TSVs generated by gen_confusables.py (skipping extraction)")

    # 3. Extract emoji data
    print("\nProcessing emoji_data.rs...")
    with open(base_dir / "src" / "tables" / "emoji_data.rs") as f:
        content = f.read()

    # EMOJI_SINGLE
    entries = extract_char_map(content, "EMOJI_SINGLE")
    write_tsv_char_map(data_dir / "emoji_single.tsv", entries)
    print(f"  Extracted {len(entries)} entries → emoji_single.tsv")

    # EMOJI_MULTI
    entries = extract_str_map(content, "EMOJI_MULTI")
    write_tsv_str_map(data_dir / "emoji_multi.tsv", entries)
    print(f"  Extracted {len(entries)} entries → emoji_multi.tsv")

    # EMOJI_MULTI_STARTERS
    entries = extract_char_set(content, "EMOJI_MULTI_STARTERS")
    write_tsv_set(data_dir / "emoji_starters.tsv", entries)
    print(f"  Extracted {len(entries)} entries → emoji_starters.tsv")

    # 4. Extract transliteration tables
    print("\nProcessing transliteration.rs...")
    with open(base_dir / "src" / "tables" / "transliteration.rs") as f:
        content = f.read()

    # DEFAULT
    entries = extract_char_map(content, "DEFAULT")
    write_tsv_char_map(data_dir / "translit_default.tsv", entries)
    print(f"  Extracted {len(entries)} entries → translit_default.tsv")

    # Language-specific maps
    lang_maps = [
        ("LANG_DE", "translit_lang_de.tsv"),
        ("LANG_NO", "translit_lang_no.tsv"),
        ("LANG_SV", "translit_lang_sv.tsv"),
        ("LANG_IS", "translit_lang_is.tsv"),
        ("LANG_ET", "translit_lang_et.tsv"),
        ("LANG_FR", "translit_lang_fr.tsv"),
        ("LANG_ES", "translit_lang_es.tsv"),
        ("LANG_PT", "translit_lang_pt.tsv"),
        ("LANG_IT", "translit_lang_it.tsv"),
        ("LANG_TR", "translit_lang_tr.tsv"),
        ("LANG_NL", "translit_lang_nl.tsv"),
        ("LANG_CA", "translit_lang_ca.tsv"),
        ("LANG_VI", "translit_lang_vi.tsv"),
        ("LANG_EL", "translit_lang_el.tsv"),
        ("LANG_BG", "translit_lang_bg.tsv"),
        ("LANG_UK", "translit_lang_uk.tsv"),
        ("ISO9", "translit_iso9.tsv"),
        ("LANG_RU", "translit_lang_ru.tsv"),
        ("LANG_SR", "translit_lang_sr.tsv"),
        ("LANG_JA", "translit_lang_ja.tsv"),
    ]

    for map_name, output_file in lang_maps:
        entries = extract_char_map(content, map_name)
        write_tsv_char_map(data_dir / output_file, entries)
        print(f"  Extracted {len(entries)} entries → {output_file}")

    print("\nDone!")


if __name__ == "__main__":
    main()
