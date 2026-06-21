#!/usr/bin/env python3
"""Generate the build-time data that closes the form-invariance residual (#481).

The #477 oracle, once it also compares the **raw** precomposed input against its
normal forms, exposes characters whose precomposed encoding and canonical-equivalent
encodings reach *different* table entries. They split into two shapes, each handled by
a structure that already exists — entirely at build time, with **no** runtime
canonicalization pass (that would re-open the #478 decompose-then-recompose hazard):

  1. Singletons (1-to-1 canonical decompositions) -> extra rows in the existing
     char-keyed PHFs: a singleton `s` resolves exactly as its canonical target `g`.
  2. Base+mark *composition exclusions* -> entries in the compose-at-lookup map #479
     already consults. These do not recompose under canonical NFC (they are exclusions),
     so #479 leaves them decomposed; we add them as data so the cluster reaches the
     precomposed entry.

This script is the single source of truth for *which* code points are in each class,
derived from the running Python's `unicodedata` (the same dependency `gen_confusables.py`
uses — Rust `build.rs` has no Unicode data). It emits two committed artifacts:

  * ``src/tables/data/excluded_compositions.tsv`` — ``DECOMP_HEX...\tPRECOMPOSED_HEX``
    keyed on the *fully canonically decomposed* cluster, value the precomposed scalar.
    `build.rs` turns this into a ``phf::Map<&str, char>`` that `compose.rs` consults
    after canonical NFC of a cluster.
  * ``src/tables/data/canonical_singletons.tsv`` — ``SINGLETON_HEX\tTARGET_HEX`` for
    every 1-to-1 canonical singleton. The per-table generators (confusables, translit)
    resolve the target against their own data to emit the equivalent row.

Run: ``python scripts/gen_excluded_compositions.py`` (writes both TSVs in place).
Reproducible: same Unicode version in => same bytes out.
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

# Pin a floor like gen_confusables.py: the classification must not silently shrink
# under an older Unicode table than the bundled confusables data (Unicode 16.0.0+).
MIN_UNICODE = (16, 0, 0)

DATA_DIR = Path(__file__).resolve().parent.parent / "src" / "tables" / "data"
EXCLUDED_TSV = DATA_DIR / "excluded_compositions.tsv"
SINGLETON_TSV = DATA_DIR / "canonical_singletons.tsv"

# The recovery tables whose keys define "is this precomposed scalar mapped?" — a
# composition entry is only useful (and only safe) when the scalar it composes toward
# has a value here. See `_mapped_codepoints` / the build-time gate below.
RECOVERY_TABLES = (
    "translit_default.tsv",
    "confusables_to_latin.tsv",
    "confusables_to_cyrillic.tsv",
)


def _mapped_codepoints() -> set[int]:
    """Source code points that a recovery table maps to a value. The widening map is
    gated on this set: composing a base+mark cluster toward a precomposed scalar only
    helps when that scalar resolves to something. Gating here also removes the
    NFKC-recovery cycle by construction — an *unmapped* excluded composite (FORKING
    U+2ADC = NONFORKING + U+0338) is never composed toward, so the transliterate recovery
    cannot decompose it and loop. (U+0344 is NOT such a case: translit_default maps it to
    the empty string, so it is "mapped" and emitted — see the review-L-3 note in
    `classify`.)"""
    mapped: set[int] = set()
    for name in RECOVERY_TABLES:
        for line in (DATA_DIR / name).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            hex_key = line.split("\t", 1)[0].strip()
            mapped.add(int(hex_key, 16))
    return mapped


def _canonical_decomposition(cp: int) -> list[int] | None:
    """The canonical decomposition of ``cp`` as code points, or None if it has only a
    compatibility (``<...>``) decomposition or none. Canonical-only keeps this purely
    NFC/NFD-equivalent: a compatibility singleton like ``ſ`` U+017F (TR39->f vs NFKC->s)
    is never touched, so the NFKC-conflict guard on the confusables table still holds."""
    decomp = unicodedata.decomposition(chr(cp))
    if not decomp or decomp.startswith("<"):
        return None
    return [int(part, 16) for part in decomp.split()]


def _full_canonical_decomposition(cp: int) -> str:
    """Fully recursive canonical decomposition (what NFD yields), as a string."""
    return unicodedata.normalize("NFD", chr(cp))


def _is_composition_excluded(cp: int) -> bool:
    """True iff NFC does not put ``cp`` back together — i.e. the round trip
    decompose-then-NFC does not return the original scalar. This captures the
    Full_Composition_Exclusion singletons and script-specific base+mark exclusions
    without needing CompositionExclusions.txt: it is exactly the observable property."""
    return unicodedata.normalize("NFC", _full_canonical_decomposition(cp)) != chr(cp)


def classify() -> tuple[list[tuple[int, int]], list[tuple[str, int]]]:
    """Return (singletons, excluded_base_mark).

    singletons:        [(singleton_cp, target_cp)]               (1-to-1 canonical)
    excluded_base_mark:[(full_nfd_string, precomposed_cp)]       (excluded compositions)
    """
    singletons: list[tuple[int, int]] = []
    excluded: list[tuple[str, int]] = []
    mapped = _mapped_codepoints()

    for cp in range(0x20, 0x110000):
        decomp = _canonical_decomposition(cp)
        if decomp is None:
            continue
        if len(decomp) == 1:
            # 1-to-1 canonical singleton (U+1F71 -> U+03AC, U+212A -> U+004B, ...).
            singletons.append((cp, decomp[0]))
            continue
        # Length >= 2. Only the *composition-excluded* ones need the compose map; the
        # rest already recompose under #479's canonical NFC and reach the table.
        if not _is_composition_excluded(cp):
            continue
        # Build-time gate: only compose toward a scalar that a recovery table maps. This
        # is the cycle fix — a *genuinely unmapped* excluded composite (FORKING U+2ADC =
        # NONFORKING + U+0338) is skipped, so transliterate's NFKC recovery never
        # decomposes a char the compose map would rebuild. It also keeps the map to only
        # entries the recovery tables can act on.
        #
        # Note (review L-3): "mapped" includes scalars that map to the EMPTY string —
        # e.g. COMBINING GREEK DIALYTIKA TONOS U+0344 (= U+0308 U+0301) is in
        # translit_default as `0344 -> ""`. So its `0308 0301 -> 0344` row IS emitted, even
        # though both the composed scalar and its pieces transliterate to nothing, making
        # that row output-neutral. It is harmless (and the lone mark-only no-op), but it is
        # NOT skipped here — only truly *absent*-from-every-table scalars are. Dropping
        # output-neutral rows would need an output-aware pass over the recovery values.
        if cp not in mapped:
            continue
        nfd = _full_canonical_decomposition(cp)
        # Restrict to clusters that compose-at-lookup can actually form: a starter
        # followed by combining mark(s). (Excludes the rare space-prefixed presentation
        # oddities, which have no base to anchor a cluster on; those, if they surface,
        # are handled as singletons via their own canonical target.)
        if len(nfd) < 2:
            continue
        tail_all_marks = all(
            unicodedata.combining(c) != 0 or unicodedata.category(c).startswith("M")
            for c in nfd[1:]
        )
        if not tail_all_marks:
            continue
        excluded.append((nfd, cp))

    singletons.sort()
    excluded.sort(key=lambda e: (len(e[0]), e[0]))
    return singletons, excluded


def _hex(cp: int) -> str:
    return f"{cp:04X}"


def write_outputs() -> tuple[int, int]:
    singletons, excluded = classify()

    with EXCLUDED_TSV.open("w", encoding="utf-8") as fh:
        fh.write("# GENERATED by scripts/gen_excluded_compositions.py — do not edit.\n")
        fh.write(
            "# fully-canonically-decomposed cluster (space-separated hex) -> precomposed scalar\n"
        )
        for nfd, cp in excluded:
            key = " ".join(_hex(ord(c)) for c in nfd)
            fh.write(f"{key}\t{_hex(cp)}\n")

    with SINGLETON_TSV.open("w", encoding="utf-8") as fh:
        fh.write("# GENERATED by scripts/gen_excluded_compositions.py — do not edit.\n")
        fh.write("# canonical singleton scalar -> canonical target scalar (1-to-1)\n")
        for s, g in singletons:
            fh.write(f"{_hex(s)}\t{_hex(g)}\n")

    return len(singletons), len(excluded)


def main() -> int:
    version = tuple(int(p) for p in unicodedata.unidata_version.split("."))
    if version < MIN_UNICODE:
        print(
            f"refusing to generate under Unicode {unicodedata.unidata_version} "
            f"(< {'.'.join(map(str, MIN_UNICODE))}); the classification could silently shrink.",
            file=sys.stderr,
        )
        return 1
    n_single, n_excluded = write_outputs()
    print(
        f"wrote {n_single} canonical singletons -> {SINGLETON_TSV.name}\n"
        f"wrote {n_excluded} excluded base+mark compositions -> {EXCLUDED_TSV.name}\n"
        f"(Unicode {unicodedata.unidata_version})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
