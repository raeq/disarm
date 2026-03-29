#!/usr/bin/env python3
"""Build Arabic context dictionary (unigrams + bigrams) from diacritized text.

Reads diacritized Arabic text files and produces a binary dictionary for
context-aware transliteration. The dictionary maps:

  Unigrams: consonant skeleton → [(diacritized form, frequency), ...]
  Bigrams:  (prev_skeleton, curr_skeleton) → best diacritized form

Usage:
    # From a directory of diacritized text files:
    python scripts/build_arabic_dict.py data/corpora/tashkeela/ -o data/arabic_dict.bin

    # From a single file:
    python scripts/build_arabic_dict.py corpus.txt -o data/arabic_dict.bin

    # Stats only (no output):
    python scripts/build_arabic_dict.py data/corpora/tashkeela/ --stats
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Arabic diacritic handling
# ---------------------------------------------------------------------------

# Arabic diacritical marks (tashkeel)
ARABIC_DIACRITICS = frozenset(
    "\u064b"  # FATHATAN
    "\u064c"  # DAMMATAN
    "\u064d"  # KASRATAN
    "\u064e"  # FATHA
    "\u064f"  # DAMMA
    "\u0650"  # KASRA
    "\u0651"  # SHADDA
    "\u0652"  # SUKUN
    "\u0653"  # MADDAH ABOVE
    "\u0654"  # HAMZA ABOVE
    "\u0655"  # HAMZA BELOW
    "\u0670"  # SUPERSCRIPT ALEF
)

# Tatweel (kashida) — decorative elongation, not semantic
TATWEEL = "\u0640"


def strip_tashkeel(word: str) -> str:
    """Strip all Arabic diacritics and tatweel from a word.

    Returns the consonant skeleton (unpointed form).
    """
    return "".join(c for c in word if c not in ARABIC_DIACRITICS and c != TATWEEL)


def is_arabic_word(word: str) -> bool:
    """Check if a word contains Arabic script characters."""
    return any("\u0600" <= c <= "\u06ff" or "\ufb50" <= c <= "\ufdff" for c in word)


def is_diacritized(word: str) -> bool:
    """Check if a word contains at least one Arabic diacritic."""
    return any(c in ARABIC_DIACRITICS for c in word)


def tokenize(text: str) -> list[str]:
    """Split Arabic text into words on whitespace and punctuation."""
    import re

    # Split on whitespace, keeping words with diacritics intact
    return [w for w in re.split(r"\s+", text.strip()) if w]


# ---------------------------------------------------------------------------
# Corpus processing
# ---------------------------------------------------------------------------


def process_file(
    path: Path,
    unigram_counts: dict[str, Counter[str]],
    bigram_counts: dict[tuple[str, str], Counter[str]],
    total_words: list[int],
) -> None:
    """Process a single diacritized text file."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        print(f"  Skipping {path}: {e}", file=sys.stderr)
        return

    words = tokenize(text)
    prev_skeleton: str | None = None

    for word in words:
        if not is_arabic_word(word):
            prev_skeleton = None
            continue

        if not is_diacritized(word):
            # Undiacritized word — can't learn from it, but track as skeleton
            prev_skeleton = strip_tashkeel(word)
            continue

        total_words[0] += 1
        skeleton = strip_tashkeel(word)

        # Record unigram: skeleton → diacritized form
        unigram_counts[skeleton][word] += 1

        # Record bigram: (prev_skeleton, skeleton) → diacritized form
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
            # Try without extension filter
            files = sorted(
                f for f in input_path.rglob("*") if f.is_file() and f.suffix in ("", ".txt", ".xml")
            )
    else:
        print(f"Error: {input_path} is not a file or directory", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(files)} files...", file=sys.stderr)

    for i, f in enumerate(files):
        if (i + 1) % 50 == 0 or i == 0:
            print(f"  [{i + 1}/{len(files)}] {f.name}", file=sys.stderr)
        process_file(f, unigram_counts, bigram_counts, total_words)

    return dict(unigram_counts), dict(bigram_counts), total_words[0]


# ---------------------------------------------------------------------------
# Dictionary compilation
# ---------------------------------------------------------------------------

# Binary format:
# Header: magic (4 bytes) + version (4 bytes) + unigram_count (4 bytes)
#         + bigram_count (4 bytes) + unigram_offset (4 bytes) + bigram_offset (4 bytes)
# Unigrams: sorted by skeleton, each entry:
#   skeleton_len (2 bytes) + skeleton (UTF-8) + num_forms (2 bytes)
#   + [form_len (2 bytes) + form (UTF-8) + freq (4 bytes)] * num_forms
# Bigrams: sorted by (prev+"\0"+curr), each entry:
#   prev_len (2 bytes) + prev (UTF-8) + curr_len (2 bytes) + curr (UTF-8)
#   + form_len (2 bytes) + form (UTF-8)

MAGIC = b"TRLD"  # translit dictionary
VERSION = 1


def compile_dictionary(
    unigram_counts: dict[str, Counter[str]],
    bigram_counts: dict[tuple[str, str], Counter[str]],
    output_path: Path,
    min_freq: int = 2,
    max_bigrams: int = 500_000,
) -> None:
    """Compile unigram and bigram tables to binary format."""

    # Filter unigrams: keep forms with freq >= min_freq
    unigrams: dict[str, list[tuple[str, int]]] = {}
    for skeleton, forms in sorted(unigram_counts.items()):
        filtered = [(form, freq) for form, freq in forms.items() if freq >= min_freq]
        if filtered:
            # Sort by frequency descending
            filtered.sort(key=lambda x: -x[1])
            unigrams[skeleton] = filtered

    # Filter bigrams: keep only those that disambiguate
    # (where the bigram winner differs from the unigram winner)
    bigrams: dict[tuple[str, str], str] = {}
    for (prev, curr), forms in bigram_counts.items():
        if curr not in unigrams:
            continue
        bigram_winner = forms.most_common(1)[0][0]
        unigram_winner = unigrams[curr][0][0]
        if bigram_winner != unigram_winner:
            # This bigram actually disambiguates — keep it
            bigrams[(prev, curr)] = bigram_winner

    # Sort bigrams by frequency and cap at max_bigrams
    if len(bigrams) > max_bigrams:
        # Keep the most frequent bigram contexts
        bigram_freqs = {k: sum(bigram_counts[k].values()) for k in bigrams}
        top_bigrams = sorted(bigram_freqs, key=bigram_freqs.get, reverse=True)[:max_bigrams]
        bigrams = {k: bigrams[k] for k in top_bigrams}

    print(f"Compiled: {len(unigrams)} unigrams, {len(bigrams)} bigrams", file=sys.stderr)

    # Write binary format
    buf = bytearray()

    # Header
    buf.extend(MAGIC)
    buf.extend(struct.pack("<I", VERSION))
    buf.extend(struct.pack("<I", len(unigrams)))
    buf.extend(struct.pack("<I", len(bigrams)))
    # Offsets will be filled later
    unigram_offset_pos = len(buf)
    buf.extend(struct.pack("<I", 0))  # placeholder
    bigram_offset_pos = len(buf)
    buf.extend(struct.pack("<I", 0))  # placeholder

    # Unigrams
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

    # Bigrams
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
        description="Build Arabic context dictionary from diacritized text"
    )
    parser.add_argument("input", type=Path, help="Diacritized text file or directory")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output binary dict path")
    parser.add_argument("--stats", action="store_true", help="Print stats only, no output")
    parser.add_argument("--min-freq", type=int, default=2, help="Minimum frequency threshold")
    parser.add_argument("--max-bigrams", type=int, default=500_000, help="Maximum bigram entries")
    parser.add_argument("--json-stats", type=Path, default=None, help="Write stats to JSON file")
    args = parser.parse_args()

    unigrams, bigrams, total_words = process_corpus(args.input)

    # Stats
    unique_skeletons = len(unigrams)
    ambiguous = sum(1 for forms in unigrams.values() if len(forms) > 1)
    total_forms = sum(len(forms) for forms in unigrams.values())

    print("\n--- Statistics ---", file=sys.stderr)
    print(f"Total diacritized words processed: {total_words:,}", file=sys.stderr)
    print(f"Unique skeletons (unigrams):       {unique_skeletons:,}", file=sys.stderr)
    print(f"Ambiguous skeletons (>1 form):     {ambiguous:,}", file=sys.stderr)
    print(f"Total diacritized forms:           {total_forms:,}", file=sys.stderr)
    print(f"Unique bigram contexts:            {len(bigrams):,}", file=sys.stderr)
    print(
        f"Avg forms per skeleton:            {total_forms / max(unique_skeletons, 1):.1f}",
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
        print(f"Stats written to {args.json_stats}", file=sys.stderr)

    if args.stats:
        return

    if args.output is None:
        print("Error: --output is required (or use --stats)", file=sys.stderr)
        sys.exit(1)

    compile_dictionary(
        unigrams,
        bigrams,
        args.output,
        min_freq=args.min_freq,
        max_bigrams=args.max_bigrams,
    )


if __name__ == "__main__":
    main()
