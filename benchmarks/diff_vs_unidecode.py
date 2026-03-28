#!/usr/bin/env python3
"""Character-level correctness diff: translit vs Unidecode vs anyascii.

For each of the 83 supported languages, iterates over EVERY codepoint in the
relevant Unicode block(s) and compares transliteration output across all three
libraries.  This is deterministic and comprehensive — it tests the full
character inventory, not a sample.

Reports:
1. Characters where outputs differ
2. Coverage: which library maps more characters (vs returning '?' or empty)
3. Language-aware differences (e.g., German Ü→Ue vs Ü→U)

Usage:
    python benchmarks/diff_vs_unidecode.py                  # summary
    python benchmarks/diff_vs_unidecode.py --detail         # per-char diffs
    python benchmarks/diff_vs_unidecode.py --markdown       # markdown report
    python benchmarks/diff_vs_unidecode.py --markdown > docs/architecture/transliteration-comparison.md
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field

import translit as tr

try:
    from unidecode import unidecode
except ImportError:
    unidecode = None

try:
    from anyascii import anyascii
except ImportError:
    anyascii = None

# ---------------------------------------------------------------------------
# Unicode block ranges per language
#
# Each language maps to (description, [(start, end), ...]) where start/end
# are inclusive codepoint boundaries.  Every assigned codepoint in these
# ranges is tested with the language's `lang` parameter.
# ---------------------------------------------------------------------------

# Shared block definitions
_LATIN_SUPPLEMENT = (0x00C0, 0x00FF)      # Latin-1 Supplement (letters only)
_LATIN_EXT_A = (0x0100, 0x017F)           # Latin Extended-A
_LATIN_EXT_B = (0x0180, 0x024F)           # Latin Extended-B
_LATIN_EXT_ADDITIONAL = (0x1E00, 0x1EFF)  # Latin Extended Additional
_CYRILLIC = (0x0400, 0x04FF)              # Cyrillic
_CYRILLIC_SUPPLEMENT = (0x0500, 0x052F)   # Cyrillic Supplement

_LATIN_BLOCKS = [_LATIN_SUPPLEMENT, _LATIN_EXT_A, _LATIN_EXT_B]

LANG_BLOCKS: dict[str, tuple[str, list[tuple[int, int]]]] = {
    # --- European (Latin-based) ---
    "bg": ("Bulgarian", [_CYRILLIC, _CYRILLIC_SUPPLEMENT]),
    "ca": ("Catalan", _LATIN_BLOCKS),
    "cs": ("Czech", _LATIN_BLOCKS),
    "cy": ("Welsh", _LATIN_BLOCKS),
    "da": ("Danish", _LATIN_BLOCKS),
    "de": ("German", _LATIN_BLOCKS),
    "el": ("Greek", [(0x0370, 0x03FF)]),  # Greek and Coptic
    "es": ("Spanish", _LATIN_BLOCKS),
    "et": ("Estonian", _LATIN_BLOCKS),
    "fi": ("Finnish", _LATIN_BLOCKS),
    "fr": ("French", _LATIN_BLOCKS),
    "ga": ("Irish", _LATIN_BLOCKS),
    "hr": ("Croatian", _LATIN_BLOCKS),
    "hu": ("Hungarian", _LATIN_BLOCKS),
    "is": ("Icelandic", _LATIN_BLOCKS),
    "it": ("Italian", _LATIN_BLOCKS),
    "lt": ("Lithuanian", _LATIN_BLOCKS),
    "lv": ("Latvian", _LATIN_BLOCKS),
    "mt": ("Maltese", _LATIN_BLOCKS),
    "nl": ("Dutch", _LATIN_BLOCKS),
    "no": ("Norwegian", _LATIN_BLOCKS),
    "pl": ("Polish", _LATIN_BLOCKS),
    "pt": ("Portuguese", _LATIN_BLOCKS),
    "ro": ("Romanian", _LATIN_BLOCKS),
    "sk": ("Slovak", _LATIN_BLOCKS),
    "sl": ("Slovenian", _LATIN_BLOCKS),
    "sq": ("Albanian", _LATIN_BLOCKS),
    "sr": ("Serbian", [_CYRILLIC, _CYRILLIC_SUPPLEMENT]),
    "sv": ("Swedish", _LATIN_BLOCKS),
    "tr": ("Turkish", _LATIN_BLOCKS),
    "uk": ("Ukrainian", [_CYRILLIC, _CYRILLIC_SUPPLEMENT]),
    "vi": ("Vietnamese", _LATIN_BLOCKS + [_LATIN_EXT_ADDITIONAL]),
    # --- East Asian ---
    "ja": ("Japanese", [
        (0x3040, 0x309F),   # Hiragana
        (0x30A0, 0x30FF),   # Katakana
        (0xFF65, 0xFF9F),   # Half-width Katakana
    ]),
    "ja-kunrei": ("Japanese Kunrei", [
        (0x3040, 0x309F),   # Hiragana
        (0x30A0, 0x30FF),   # Katakana
    ]),
    "ko": ("Korean", [(0xAC00, 0xD7A3)]),  # Hangul Syllables
    "zh": ("Chinese", [(0x4E00, 0x9FFF)]),  # CJK Unified Ideographs
    # --- Semitic ---
    "ar": ("Arabic", [(0x0600, 0x06FF)]),
    "fa": ("Persian", [(0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF)]),
    "he": ("Hebrew", [(0x0590, 0x05FF)]),
    # --- Indic (Brahmic) ---
    "hi": ("Hindi", [(0x0900, 0x097F)]),         # Devanagari
    "bn": ("Bengali", [(0x0980, 0x09FF)]),
    "ta": ("Tamil", [(0x0B80, 0x0BFF)]),
    "te": ("Telugu", [(0x0C00, 0x0C7F)]),
    "gu": ("Gujarati", [(0x0A80, 0x0AFF)]),
    "kn": ("Kannada", [(0x0C80, 0x0CFF)]),
    "ml": ("Malayalam", [(0x0D00, 0x0D7F)]),
    "mr": ("Marathi", [(0x0900, 0x097F)]),       # Devanagari
    "ne": ("Nepali", [(0x0900, 0x097F)]),         # Devanagari
    "or": ("Odia", [(0x0B00, 0x0B7F)]),
    "pa": ("Punjabi", [(0x0A00, 0x0A7F)]),       # Gurmukhi
    "sa": ("Sanskrit", [(0x0900, 0x097F)]),       # Devanagari
    "as": ("Assamese", [(0x0980, 0x09FF)]),       # Bengali block
    # --- Caucasian ---
    "hy": ("Armenian", [(0x0530, 0x058F)]),
    "ka": ("Georgian", [(0x10A0, 0x10FF)]),
    # --- South/Southeast Asian ---
    "si": ("Sinhala", [(0x0D80, 0x0DFF)]),
    "th": ("Thai", [(0x0E00, 0x0E7F)]),
    "lo": ("Lao", [(0x0E80, 0x0EFF)]),
    "km": ("Khmer", [(0x1780, 0x17FF)]),
    "my": ("Myanmar", [(0x1000, 0x109F)]),
    # --- Tibetan ---
    "bo": ("Tibetan", [(0x0F00, 0x0FFF)]),
    # --- Ethiopic ---
    "am": ("Amharic", [(0x1200, 0x137F), (0x1380, 0x139F)]),
    # --- Russian ---
    "ru": ("Russian", [_CYRILLIC, _CYRILLIC_SUPPLEMENT]),
    # --- Other ---
    "dv": ("Dhivehi", [(0x0780, 0x07BF)]),       # Thaana
    "jv": ("Javanese", [(0xA980, 0xA9DF)]),
    "mn": ("Mongolian", [(0x1800, 0x18AF)]),      # Mongolian
    # --- New scripts (Tier 2) ---
    "su": ("Sundanese", [(0x1B80, 0x1BBF)]),
    "nod": ("Tai Tham", [(0x1A20, 0x1AAF)]),
    "cjm": ("Cham", [(0xAA00, 0xAA5F)]),
    "btk": ("Batak", [(0x1BC0, 0x1BFF)]),
    "bug": ("Buginese", [(0x1A00, 0x1A1F)]),
    "tl": ("Tagalog", [(0x1700, 0x171F)]),
    "hnn": ("Hanunoo", [(0x1720, 0x173F)]),
    "bku": ("Buhid", [(0x1740, 0x175F)]),
    "tbw": ("Tagbanwa", [(0x1760, 0x177F)]),
    "mni": ("Meetei Mayek", [(0xABC0, 0xABFF), (0xAAE0, 0xAAFF)]),
    "ber": ("Tifinagh", [(0x2D30, 0x2D7F)]),
    "lis": ("Lisu", [(0xA4D0, 0xA4FF)]),
    "sat": ("Ol Chiki", [(0x1C50, 0x1C7F)]),
    "bax": ("Bamum", [(0xA6A0, 0xA6FF)]),
    "bal": ("Balinese", [(0x1B00, 0x1B7F)]),
    "nko": ("N'Ko", [(0x07C0, 0x07FF)]),
    "vai": ("Vai", [(0xA500, 0xA63F)]),
    "cop": ("Coptic", [(0x2C80, 0x2CFF)]),
}


@dataclass
class CharDiff:
    """A single character where libraries produce different output."""
    char: str
    codepoint: int
    name: str
    translit_out: str
    unidecode_out: str | None
    anyascii_out: str | None


@dataclass
class LangReport:
    """Comparison report for one language."""
    lang: str
    description: str
    block_chars: int = 0              # assigned codepoints in the block(s)
    total_non_ascii: int = 0          # chars where at least one lib maps
    translit_mapped: int = 0
    unidecode_mapped: int = 0
    anyascii_mapped: int = 0
    diffs_translit_vs_unidecode: list[CharDiff] = field(default_factory=list)
    diffs_translit_vs_anyascii: list[CharDiff] = field(default_factory=list)
    translit_only: int = 0
    unidecode_only: int = 0
    translit_only_chars: list[CharDiff] = field(default_factory=list)
    unidecode_only_chars: list[CharDiff] = field(default_factory=list)


def is_mapped(output: str | None, original: str) -> bool:
    """Check if a library actually mapped the character."""
    if output is None or not output or output == original:
        return False
    if all(c in ("[", "]", "?") for c in output):
        return False
    return True


def iter_block_chars(blocks: list[tuple[int, int]]) -> list[str]:
    """Yield every assigned non-ASCII character in the given Unicode blocks."""
    chars: list[str] = []
    for start, end in blocks:
        for cp in range(start, end + 1):
            if cp < 128:
                continue
            ch = chr(cp)
            cat = unicodedata.category(ch)
            # Skip unassigned (Cn), private use (Co), surrogates (Cs),
            # and format chars (Cf) — these aren't meaningful for transliteration
            if cat.startswith("C"):
                continue
            chars.append(ch)
    return chars


def compare_char(ch: str, lang: str) -> CharDiff:
    """Compare transliteration of a single character across libraries."""
    t_out = tr.transliterate(ch, lang=lang, errors="ignore")
    u_out = unidecode(ch) if unidecode else None
    a_out = anyascii(ch) if anyascii else None
    try:
        name = unicodedata.name(ch)
    except ValueError:
        name = f"U+{ord(ch):04X}"
    return CharDiff(
        char=ch,
        codepoint=ord(ch),
        name=name,
        translit_out=t_out,
        unidecode_out=u_out,
        anyascii_out=a_out,
    )


def analyze_language(lang: str, desc: str, blocks: list[tuple[int, int]]) -> LangReport:
    """Run full comparison for one language over its Unicode block(s)."""
    chars = iter_block_chars(blocks)

    report = LangReport(lang=lang, description=desc, block_chars=len(chars))

    for ch in chars:
        diff = compare_char(ch, lang)

        t_mapped = is_mapped(diff.translit_out, ch)
        u_mapped = is_mapped(diff.unidecode_out, ch)
        a_mapped = is_mapped(diff.anyascii_out, ch)

        # Only count chars where at least one library maps
        if t_mapped or u_mapped or a_mapped:
            report.total_non_ascii += 1

        if t_mapped:
            report.translit_mapped += 1
        if u_mapped:
            report.unidecode_mapped += 1
        if a_mapped:
            report.anyascii_mapped += 1

        if t_mapped and not u_mapped:
            report.translit_only += 1
            report.translit_only_chars.append(diff)
        if u_mapped and not t_mapped:
            report.unidecode_only += 1
            report.unidecode_only_chars.append(diff)

        # Record diffs where both map but produce different output
        if t_mapped and u_mapped and diff.translit_out != diff.unidecode_out:
            report.diffs_translit_vs_unidecode.append(diff)
        if t_mapped and a_mapped and diff.translit_out != diff.anyascii_out:
            report.diffs_translit_vs_anyascii.append(diff)

    return report


def print_summary(reports: list[LangReport]) -> None:
    """Print summary table to stdout."""
    print(f"{'Lang':<12} {'Description':<16} {'Block':>5} {'Mapped':>6} "
          f"{'translit':>8} {'Unidec':>6} {'anyasc':>6} "
          f"{'t-only':>6} {'u-only':>6} {'diffs':>5}")
    print("-" * 100)

    totals = defaultdict(int)
    for r in reports:
        diffs = len(r.diffs_translit_vs_unidecode)
        print(f"{r.lang:<12} {r.description:<16} {r.block_chars:>5} "
              f"{r.total_non_ascii:>6} "
              f"{r.translit_mapped:>8} {r.unidecode_mapped:>6} {r.anyascii_mapped:>6} "
              f"{r.translit_only:>6} {r.unidecode_only:>6} {diffs:>5}")
        totals["block"] += r.block_chars
        totals["mapped"] += r.total_non_ascii
        totals["translit"] += r.translit_mapped
        totals["unidecode"] += r.unidecode_mapped
        totals["anyascii"] += r.anyascii_mapped
        totals["t_only"] += r.translit_only
        totals["u_only"] += r.unidecode_only
        totals["diffs"] += diffs

    print("-" * 100)
    print(f"{'TOTAL':<12} {'':<16} {totals['block']:>5} "
          f"{totals['mapped']:>6} "
          f"{totals['translit']:>8} {totals['unidecode']:>6} {totals['anyascii']:>6} "
          f"{totals['t_only']:>6} {totals['u_only']:>6} {totals['diffs']:>5}")


def print_detail(reports: list[LangReport]) -> None:
    """Print per-character diffs."""
    for r in reports:
        if not r.diffs_translit_vs_unidecode:
            continue
        print(f"\n=== {r.lang} ({r.description}) — "
              f"{len(r.diffs_translit_vs_unidecode)} differences ===")
        for d in r.diffs_translit_vs_unidecode[:50]:
            print(f"  {d.char} U+{d.codepoint:04X} {d.name:<40} "
                  f"translit={d.translit_out!r:<12} unidecode={d.unidecode_out!r:<12}"
                  + (f" anyascii={d.anyascii_out!r}"
                     if d.anyascii_out is not None else ""))
        if len(r.diffs_translit_vs_unidecode) > 50:
            print(f"  ... and "
                  f"{len(r.diffs_translit_vs_unidecode) - 50} more")


def _print_lang_section(r: LangReport) -> None:
    """Print a Notable Differences section for a single language."""
    print(f"### {r.lang} — {r.description}")
    print()
    print(f"Block: {r.block_chars} assigned codepoints, "
          f"{r.total_non_ascii} mapped by at least one library.")
    print()
    if r.translit_only > 0 or r.unidecode_only > 0:
        print(f"Coverage: translit maps "
              f"{r.translit_mapped}/{r.total_non_ascii}, "
              f"Unidecode maps "
              f"{r.unidecode_mapped}/{r.total_non_ascii}. "
              f"**{r.translit_only}** mapped only by translit, "
              f"**{r.unidecode_only}** mapped only by Unidecode.")
        print()
        if r.translit_only_chars:
            print("**Mapped only by translit** "
                  "(Unidecode returns empty/`[?]`):")
            print()
            print("| Char | Codepoint | Name | translit |")
            print("|------|-----------|------|----------|")
            for d in r.translit_only_chars[:30]:
                print(f"| {d.char} | U+{d.codepoint:04X} | "
                      f"{d.name} | `{d.translit_out}` |")
            if len(r.translit_only_chars) > 30:
                print(f"| | | *...{len(r.translit_only_chars) - 30} "
                      f"more* | |")
            print()
        if r.unidecode_only_chars:
            print("**Mapped only by Unidecode** "
                  "(translit returns empty):")
            print()
            print("| Char | Codepoint | Name | Unidecode |")
            print("|------|-----------|------|-----------|")
            for d in r.unidecode_only_chars[:30]:
                print(f"| {d.char} | U+{d.codepoint:04X} | "
                      f"{d.name} | `{d.unidecode_out}` |")
            if len(r.unidecode_only_chars) > 30:
                print(f"| | | *...{len(r.unidecode_only_chars) - 30} "
                      f"more* | |")
            print()
    if r.diffs_translit_vs_unidecode:
        print("| Char | Codepoint | Name | translit | "
              "Unidecode | anyascii |")
        print("|------|-----------|------|----------|"
              "-----------|----------|")
        for d in r.diffs_translit_vs_unidecode[:50]:
            a_col = (f"`{d.anyascii_out}`"
                     if d.anyascii_out else "\u2014")
            print(f"| {d.char} | U+{d.codepoint:04X} | {d.name} | "
                  f"`{d.translit_out}` | `{d.unidecode_out}` | "
                  f"{a_col} |")
        if len(r.diffs_translit_vs_unidecode) > 50:
            remaining = len(r.diffs_translit_vs_unidecode) - 50
            print(f"| | | *...{remaining} more differences* | "
                  f"| | |")
        print()


def _print_latin_group(group: list[LangReport]) -> None:
    """Print a combined section for Latin-block languages with shared stats."""
    # Use first report for shared stats (all have same block/coverage)
    ref = group[0]
    lang_list = ", ".join(f"{r.lang} ({r.description})" for r in group)
    print(f"### Latin-script languages ({len(group)} languages)")
    print()
    print(f"**Languages**: {lang_list}")
    print()
    print(f"All {len(group)} languages share the same Unicode blocks "
          f"(Latin-1 Supplement + Latin Extended-A + Latin Extended-B) "
          f"with {ref.block_chars} assigned codepoints, "
          f"{ref.total_non_ascii} mapped by at least one library.")
    print()
    if ref.translit_only > 0 or ref.unidecode_only > 0:
        print(f"Coverage: translit maps "
              f"{ref.translit_mapped}/{ref.total_non_ascii}, "
              f"Unidecode maps "
              f"{ref.unidecode_mapped}/{ref.total_non_ascii}. "
              f"**{ref.translit_only}** mapped only by translit, "
              f"**{ref.unidecode_only}** mapped only by Unidecode.")
        print()
        if ref.translit_only_chars:
            print("**Mapped only by translit** "
                  "(Unidecode returns empty/`[?]`):")
            print()
            print("| Char | Codepoint | Name | translit |")
            print("|------|-----------|------|----------|")
            for d in ref.translit_only_chars[:30]:
                print(f"| {d.char} | U+{d.codepoint:04X} | "
                      f"{d.name} | `{d.translit_out}` |")
            print()

    # Collect shared diffs (present in all languages) vs per-language diffs
    # Build a set of codepoints that differ per language (due to lang overrides)
    all_diff_cps: dict[int, dict[str, CharDiff]] = {}
    for r in group:
        for d in r.diffs_translit_vs_unidecode:
            if d.codepoint not in all_diff_cps:
                all_diff_cps[d.codepoint] = {}
            all_diff_cps[d.codepoint][r.lang] = d

    # Shared diffs: same translit output across all languages that have them
    shared_diffs: list[CharDiff] = []
    per_lang_diffs: dict[str, list[CharDiff]] = {r.lang: [] for r in group}
    for cp in sorted(all_diff_cps):
        langs_with_diff = all_diff_cps[cp]
        outputs = {d.translit_out for d in langs_with_diff.values()}
        if len(outputs) == 1 and len(langs_with_diff) == len(group):
            # All languages produce the same diff — it's shared
            shared_diffs.append(next(iter(langs_with_diff.values())))
        else:
            # Language-specific diff
            for lang, d in langs_with_diff.items():
                per_lang_diffs[lang].append(d)

    if shared_diffs:
        print(f"**Shared differences** (same output across all "
              f"{len(group)} languages):")
        print()
        print("| Char | Codepoint | Name | translit | "
              "Unidecode | anyascii |")
        print("|------|-----------|------|----------|"
              "-----------|----------|")
        for d in shared_diffs[:50]:
            a_col = (f"`{d.anyascii_out}`"
                     if d.anyascii_out else "\u2014")
            print(f"| {d.char} | U+{d.codepoint:04X} | {d.name} | "
                  f"`{d.translit_out}` | `{d.unidecode_out}` | "
                  f"{a_col} |")
        if len(shared_diffs) > 50:
            remaining = len(shared_diffs) - 50
            print(f"| | | *...{remaining} more differences* | "
                  f"| | |")
        print()

    # Print per-language diffs only for languages that have unique ones
    langs_with_unique = [(lang, diffs) for lang, diffs
                         in per_lang_diffs.items() if diffs]
    if langs_with_unique:
        print("**Language-specific differences** "
              "(due to language override tables):")
        print()
        for lang, diffs in sorted(langs_with_unique):
            desc = LANG_BLOCKS[lang][0]
            print(f"#### {lang} — {desc}")
            print()
            print("| Char | Codepoint | Name | translit | "
                  "Unidecode | anyascii |")
            print("|------|-----------|------|----------|"
                  "-----------|----------|")
            for d in diffs[:30]:
                a_col = (f"`{d.anyascii_out}`"
                         if d.anyascii_out else "\u2014")
                print(f"| {d.char} | U+{d.codepoint:04X} | {d.name} | "
                      f"`{d.translit_out}` | `{d.unidecode_out}` | "
                      f"{a_col} |")
            if len(diffs) > 30:
                remaining = len(diffs) - 30
                print(f"| | | *...{remaining} more* | | | |")
            print()


def print_markdown(reports: list[LangReport]) -> None:
    """Print full markdown report."""
    print("# Transliteration Comparison: translit vs Unidecode vs anyascii")
    print()
    print("Comprehensive character-level comparison across all 83 supported "
          "languages.")
    print("Every assigned codepoint in each language's Unicode block(s) is "
          "tested — no sampling.")
    print()
    print("## Methodology")
    print()
    print("For each language:")
    print("1. All assigned codepoints in the relevant Unicode block(s) are "
          "enumerated")
    print("2. Unassigned, private-use, surrogate, and format characters are "
          "skipped")
    print("3. Each character is transliterated by all three libraries with "
          "the language's `lang` parameter")
    print('4. "Mapped" means at least one library produced meaningful ASCII '
          "output")
    print("   (not empty, not `[?]`, not the original character)")
    print()
    print("This approach is deterministic and comprehensive — results do not "
          "depend on sample text selection.")
    print()
    print("## Summary")
    print()
    print("| Lang | Description | Block chars | Mapped | translit | "
          "Unidecode | anyascii | translit-only | Unidecode-only | "
          "Output diffs |")
    print("|------|-------------|------------|--------|----------|"
          "-----------|----------|---------------|----------------|"
          "-------------|")

    totals = defaultdict(int)
    for r in reports:
        diffs = len(r.diffs_translit_vs_unidecode)
        print(f"| {r.lang} | {r.description} | {r.block_chars} | "
              f"{r.total_non_ascii} | "
              f"{r.translit_mapped} | {r.unidecode_mapped} | "
              f"{r.anyascii_mapped} | "
              f"{r.translit_only} | {r.unidecode_only} | {diffs} |")
        totals["block"] += r.block_chars
        totals["mapped"] += r.total_non_ascii
        totals["translit"] += r.translit_mapped
        totals["unidecode"] += r.unidecode_mapped
        totals["anyascii"] += r.anyascii_mapped
        totals["t_only"] += r.translit_only
        totals["u_only"] += r.unidecode_only
        totals["diffs"] += diffs

    pct_t = 100 * totals["translit"] / max(totals["mapped"], 1)
    pct_u = 100 * totals["unidecode"] / max(totals["mapped"], 1)
    pct_a = 100 * totals["anyascii"] / max(totals["mapped"], 1)
    print(f"| **TOTAL** | | **{totals['block']}** | "
          f"**{totals['mapped']}** | "
          f"**{totals['translit']}** | **{totals['unidecode']}** | "
          f"**{totals['anyascii']}** | "
          f"**{totals['t_only']}** | **{totals['u_only']}** | "
          f"**{totals['diffs']}** |")

    # Detail sections
    print()
    print("## Notable Differences")
    print()

    # Group Latin-block languages that share the same blocks and coverage
    latin_group: list[LangReport] = []
    other_reports: list[LangReport] = []
    for r in reports:
        if (not r.diffs_translit_vs_unidecode
                and r.translit_only == 0
                and r.unidecode_only == 0):
            continue
        blocks = LANG_BLOCKS[r.lang][1]
        if blocks == _LATIN_BLOCKS:
            latin_group.append(r)
        else:
            other_reports.append(r)

    if latin_group:
        _print_latin_group(latin_group)
    for r in other_reports:
        _print_lang_section(r)

    print("## Key Takeaways")
    print()
    print(f"- **Total assigned codepoints scanned**: {totals['block']}")
    print(f"- **Mapped by at least one library**: {totals['mapped']}")
    print(f"- **translit coverage**: {totals['translit']}/{totals['mapped']}"
          f" ({pct_t:.1f}%)")
    print(f"- **Unidecode coverage**: "
          f"{totals['unidecode']}/{totals['mapped']}"
          f" ({pct_u:.1f}%)")
    print(f"- **anyascii coverage**: "
          f"{totals['anyascii']}/{totals['mapped']}"
          f" ({pct_a:.1f}%)")
    print(f"- **Characters mapped only by translit**: {totals['t_only']}")
    print(f"- **Characters mapped only by Unidecode**: {totals['u_only']}")
    print(f"- **Different output (both mapped)**: {totals['diffs']}")
    print()
    print("---")
    print()
    print("*Generated by `benchmarks/diff_vs_unidecode.py`*")


def main():
    parser = argparse.ArgumentParser(
        description="Transliteration correctness comparison "
                    "(full Unicode block scan)")
    parser.add_argument("--detail", action="store_true",
                        help="Show per-character diffs")
    parser.add_argument("--markdown", action="store_true",
                        help="Output markdown report")
    args = parser.parse_args()

    if not unidecode:
        print("WARNING: Unidecode not installed (pip install Unidecode)",
              file=sys.stderr)
    if not anyascii:
        print("WARNING: anyascii not installed (pip install anyascii)",
              file=sys.stderr)

    reports = []
    for lang, (desc, blocks) in LANG_BLOCKS.items():
        report = analyze_language(lang, desc, blocks)
        reports.append(report)

    if args.markdown:
        print_markdown(reports)
    else:
        print_summary(reports)
        if args.detail:
            print_detail(reports)


if __name__ == "__main__":
    main()
