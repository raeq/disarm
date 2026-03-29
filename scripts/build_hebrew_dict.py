#!/usr/bin/env python3
"""Build Hebrew context dictionary (unigrams + bigrams) from niqqud-pointed text.

Reads Hebrew text files WITH niqqud (vowel points) and produces a binary
dictionary for context-aware transliteration. Same format as Arabic dict.

Usage:
    # From Project Ben Yehuda diacritized texts:
    python scripts/build_hebrew_dict.py data/corpora/ben_yehuda/txt_with_diacritics/ \
        -o data/hebrew_dict.bin

    # Stats only:
    python scripts/build_hebrew_dict.py data/corpora/ben_yehuda/txt_with_diacritics/ --stats
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Hebrew niqqud handling
# ---------------------------------------------------------------------------

# Hebrew niqqud (vowel points) and cantillation marks
HEBREW_NIQQUD = frozenset(
    "\u05b0"  # SHEVA
    "\u05b1"  # HATAF SEGOL
    "\u05b2"  # HATAF PATAH
    "\u05b3"  # HATAF QAMATS
    "\u05b4"  # HIRIQ
    "\u05b5"  # TSERE
    "\u05b6"  # SEGOL
    "\u05b7"  # PATAH
    "\u05b8"  # QAMATS
    "\u05b9"  # HOLAM
    "\u05ba"  # HOLAM HASER
    "\u05bb"  # QUBUTS
    "\u05bc"  # DAGESH
    "\u05bd"  # METEG
    "\u05bf"  # RAFE
    "\u05c1"  # SHIN DOT
    "\u05c2"  # SIN DOT
    "\u05c4"  # UPPER DOT
    "\u05c5"  # LOWER DOT
)

# Cantillation marks (taamim) — also strip these
HEBREW_CANTILLATION = frozenset(chr(c) for c in range(0x0591, 0x05B0))


def strip_niqqud(word: str) -> str:
    """Strip all Hebrew niqqud and cantillation from a word."""
    return "".join(c for c in word if c not in HEBREW_NIQQUD and c not in HEBREW_CANTILLATION)


def is_hebrew_word(word: str) -> bool:
    """Check if a word contains Hebrew script characters."""
    return any("\u05d0" <= c <= "\u05ea" for c in word)


def has_niqqud(word: str) -> bool:
    """Check if a word contains at least one Hebrew niqqud mark."""
    return any(c in HEBREW_NIQQUD for c in word)


def tokenize(text: str) -> list[str]:
    """Split Hebrew text into words on whitespace."""
    import re

    return [w for w in re.split(r"\s+", text.strip()) if w]


# ---------------------------------------------------------------------------
# Corpus processing (same structure as Arabic builder)
# ---------------------------------------------------------------------------


def process_file(
    path: Path,
    unigram_counts: dict[str, Counter[str]],
    bigram_counts: dict[tuple[str, str], Counter[str]],
    total_words: list[int],
) -> None:
    """Process a single niqqud-pointed text file."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        print(f"  Skipping {path.name}: {e}", file=sys.stderr)
        return

    words = tokenize(text)
    prev_skeleton: str | None = None

    for word in words:
        if not is_hebrew_word(word):
            prev_skeleton = None
            continue

        if not has_niqqud(word):
            prev_skeleton = strip_niqqud(word)
            continue

        total_words[0] += 1
        skeleton = strip_niqqud(word)

        unigram_counts[skeleton][word] += 1

        if prev_skeleton is not None:
            bigram_counts[(prev_skeleton, skeleton)][word] += 1

        prev_skeleton = skeleton


def process_corpus(
    input_path: Path,
) -> tuple[dict[str, Counter[str]], dict[tuple[str, str], Counter[str]], int]:
    """Process all text files in a directory or a single file."""
    unigram_counts: dict[str, Counter[str]] = defaultdict(Counter)
    bigram_counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    total_words = [0]

    if input_path.is_file():
        files = [input_path]
    elif input_path.is_dir():
        files = sorted(input_path.rglob("*.txt"))
        if not files:
            files = sorted(f for f in input_path.rglob("*") if f.is_file())
    else:
        print(f"Error: {input_path} is not a file or directory", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(files)} files...", file=sys.stderr)

    for i, f in enumerate(files):
        if (i + 1) % 500 == 0 or i == 0:
            print(f"  [{i + 1}/{len(files)}] {f.name}", file=sys.stderr)
        process_file(f, unigram_counts, bigram_counts, total_words)

    return dict(unigram_counts), dict(bigram_counts), total_words[0]


# ---------------------------------------------------------------------------
# Dictionary compilation (identical format to Arabic — reuse TRLD v1)
# ---------------------------------------------------------------------------

MAGIC = b"TRLD"
VERSION = 1


def compile_dictionary(
    unigram_counts: dict[str, Counter[str]],
    bigram_counts: dict[tuple[str, str], Counter[str]],
    output_path: Path,
    min_freq: int = 2,
    max_bigrams: int = 200_000,
) -> None:
    """Compile unigram and bigram tables to binary format."""
    unigrams: dict[str, list[tuple[str, int]]] = {}
    for skeleton, forms in sorted(unigram_counts.items()):
        filtered = [(form, freq) for form, freq in forms.items() if freq >= min_freq]
        if filtered:
            filtered.sort(key=lambda x: -x[1])
            unigrams[skeleton] = filtered

    bigrams: dict[tuple[str, str], str] = {}
    for (prev, curr), forms in bigram_counts.items():
        if curr not in unigrams:
            continue
        bigram_winner = forms.most_common(1)[0][0]
        unigram_winner = unigrams[curr][0][0]
        if bigram_winner != unigram_winner:
            bigrams[(prev, curr)] = bigram_winner

    if len(bigrams) > max_bigrams:
        bigram_freqs = {k: sum(bigram_counts[k].values()) for k in bigrams}
        top_bigrams = sorted(bigram_freqs, key=bigram_freqs.get, reverse=True)[:max_bigrams]
        bigrams = {k: bigrams[k] for k in top_bigrams}

    print(f"Compiled: {len(unigrams)} unigrams, {len(bigrams)} bigrams", file=sys.stderr)

    buf = bytearray()
    buf.extend(MAGIC)
    buf.extend(struct.pack("<I", VERSION))
    buf.extend(struct.pack("<I", len(unigrams)))
    buf.extend(struct.pack("<I", len(bigrams)))
    unigram_offset_pos = len(buf)
    buf.extend(struct.pack("<I", 0))
    bigram_offset_pos = len(buf)
    buf.extend(struct.pack("<I", 0))

    struct.pack_into("<I", buf, unigram_offset_pos, len(buf))
    for skeleton in sorted(unigrams):
        forms = unigrams[skeleton]
        skel_bytes = skeleton.encode("utf-8")
        buf.extend(struct.pack("<H", len(skel_bytes)))
        buf.extend(skel_bytes)
        buf.extend(struct.pack("<H", len(forms)))
        for form, freq in forms:
            form_bytes = form.encode("utf-8")
            buf.extend(struct.pack("<H", len(form_bytes)))
            buf.extend(form_bytes)
            buf.extend(struct.pack("<I", freq))

    struct.pack_into("<I", buf, bigram_offset_pos, len(buf))
    for prev, curr in sorted(bigrams):
        form = bigrams[(prev, curr)]
        prev_bytes = prev.encode("utf-8")
        curr_bytes = curr.encode("utf-8")
        form_bytes = form.encode("utf-8")
        buf.extend(struct.pack("<H", len(prev_bytes)))
        buf.extend(prev_bytes)
        buf.extend(struct.pack("<H", len(curr_bytes)))
        buf.extend(curr_bytes)
        buf.extend(struct.pack("<H", len(form_bytes)))
        buf.extend(form_bytes)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(bytes(buf))
    print(f"Written: {output_path} ({len(buf):,} bytes)", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Hebrew context dictionary from niqqud-pointed text"
    )
    parser.add_argument("input", type=Path, help="Niqqud-pointed text file or directory")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output binary dict path")
    parser.add_argument("--stats", action="store_true", help="Print stats only, no output")
    parser.add_argument("--min-freq", type=int, default=2, help="Minimum frequency threshold")
    parser.add_argument("--max-bigrams", type=int, default=200_000, help="Maximum bigram entries")
    parser.add_argument("--json-stats", type=Path, default=None, help="Write stats to JSON file")
    args = parser.parse_args()

    unigrams, bigrams, total_words = process_corpus(args.input)

    unique_skeletons = len(unigrams)
    ambiguous = sum(1 for forms in unigrams.values() if len(forms) > 1)
    total_forms = sum(len(forms) for forms in unigrams.values())

    print("\n--- Statistics ---", file=sys.stderr)
    print(f"Total niqqud-pointed words processed: {total_words:,}", file=sys.stderr)
    print(f"Unique skeletons (unigrams):          {unique_skeletons:,}", file=sys.stderr)
    print(f"Ambiguous skeletons (>1 form):        {ambiguous:,}", file=sys.stderr)
    print(f"Total pointed forms:                  {total_forms:,}", file=sys.stderr)
    print(f"Unique bigram contexts:               {len(bigrams):,}", file=sys.stderr)
    print(
        f"Avg forms per skeleton:               {total_forms / max(unique_skeletons, 1):.1f}",
        file=sys.stderr,
    )

    if args.json_stats:
        stats = {
            "total_words": total_words,
            "unique_skeletons": unique_skeletons,
            "ambiguous_skeletons": ambiguous,
            "total_forms": total_forms,
            "unique_bigrams": len(bigrams),
        }
        args.json_stats.write_text(json.dumps(stats, indent=2))

    if args.stats:
        return

    if args.output is None:
        print("Error: --output is required (or use --stats)", file=sys.stderr)
        sys.exit(1)

    compile_dictionary(
        unigrams, bigrams, args.output, min_freq=args.min_freq, max_bigrams=args.max_bigrams
    )


if __name__ == "__main__":
    main()
