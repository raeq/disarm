#!/usr/bin/env python3
"""Generate Confusables/Tables.lean: the confusable, case-fold and normalization tables
the model reads, projected onto a finite domain closed under every operation the model
performs.

The model's *input* alphabet is ``ALPHABET`` (one representative per class the Rust
code branches on). Its *domain* is the least superset of the alphabet closed under

* canonical and compatibility decomposition (NFD / NFKD of one code point),
* canonical composition of two domain characters (primary composites only),
* NFC of one code point (singletons such as OHM SIGN),
* full case folding (`disarm.fold_case`, i.e. ``case_folding.tsv``),
* the Latin confusable map and the tr39 digit overrides (every value character),
* the #481 widening map (a key over the domain adds its precomposed value).

So every table below is exact on every string over the domain: no model output can
leave it, and nothing is approximated inside it. Outside the domain every table
answers as for an inert character; no model run reaches that case (the difftest and
`Checks.lean` enumerate over the alphabet only).

Sources, all read from the repository or the built library, never typed by hand:

* ``latinMap``, ``tr39Override``, ``upstreamSource`` <- src/tables/data/confusables_to_latin.tsv,
  confusables_digit_tr39.tsv, confusables_upstream_sources.tsv
* ``excludedCompositions`` <- src/tables/data/excluded_compositions.tsv (#481 widening map)
* ``canonDecomp`` / ``compatDecomp`` <- ``disarm.normalize(c, "NFD"/"NFKD")`` (the library's
  own Unicode 17 normalizer, the one `compose.rs` calls)
* ``caseFold`` <- ``disarm.fold_case``
* ``ccc`` / ``isMark`` / primary composites <- Python ``unicodedata`` for the characters it
  knows; the two Kirat Rai code points (Unicode 16, newer than this Python's database)
  are stated below and cross-checked against the library's NFC/NFD.

Run from the repository root with an importable ``disarm``:
    python3 formal/lean/Confusables/scripts/gen_tables.py
"""

from __future__ import annotations

import pathlib
import unicodedata

import disarm

ROOT = pathlib.Path(__file__).resolve().parents[4]
DATA = ROOT / "src" / "tables" / "data"
OUT = pathlib.Path(__file__).resolve().parents[1] / "Confusables" / "Tables.lean"

# (lean name, code point, why it is its own class)
ALPHABET = [
    ("cA", 0x61, "'a': plain ASCII letter, the target of U+0430"),
    ("cCu", 0x43, "'C': uppercase ASCII (fold_case, guard), target of U+04AA"),
    ("cY", 0x79, "'y': composes with U+0300 to U+1EF3, a fold source"),
    ("cI", 0x49, "'I': the prototype fold's letter half (I -> l)"),
    ("c1", 0x31, "'1': the prototype fold's digit half under tr39"),
    ("cBar", 0x7C, "'|': an ASCII fold source that detection skips (#957)"),
    ("cSp", 0x20, "space: collapse_whitespace, the guard's WhitespaceOnly verdict"),
    ("cCtl", 0x01, "U+0001: a control StripControl removes"),
    ("cCyrA", 0x430, "CYRILLIC SMALL A: the basic homoglyph, folds to 'a'"),
    ("cYen", 0xA5, "YEN SIGN: folds to 'Y', which then composes with a mark (#522)"),
    (
        "cCyrS",
        0x4AA,
        "CYRILLIC CAPITAL ES WITH DESCENDER: folds to 'C'; + U+0327 composes to a source",
    ),
    ("cGrave", 0x300, "COMBINING GRAVE (Mn, ccc 230)"),
    ("cCed", 0x327, "COMBINING CEDILLA (Mn, ccc 202)"),
    ("cDia", 0x308, "COMBINING DIAERESIS (Mn, ccc 230)"),
    ("cAcute", 0x301, "COMBINING ACUTE (Mn, ccc 230)"),
    (
        "cIota3",
        0x390,
        "GREEK SMALL IOTA WITH DIALYTIKA AND TONOS: case-folds to a decomposed triple",
    ),
    ("cYGr", 0x1EF3, "y WITH GRAVE: folds to a NON-ASCII value (U+00FD)"),
    ("cDev0", 0x966, "DEVANAGARI ZERO: a digit row (numeric 0, tr39 o, preserve keeps)"),
    ("cKr", 0x16D67, "KIRAT RAI VOWEL SIGN E: a starter that composes with a starter (Unicode 16)"),
    ("cOhm", 0x2126, "OHM SIGN: an NFC singleton, only foldable after NFKC + case fold"),
    ("cAMac", 0x101, "a WITH MACRON: folds to a NON-ASCII value (U+00E3)"),
]
CPS = [cp for _, cp, _ in ALPHABET]

# Unicode 16 characters this Python's unicodedata predates. Values from UCD 16.0
# (UnicodeData.txt): ccc 0, General_Category Mc/Lo, and the single-level canonical
# decompositions below. Cross-checked against the library's normalizer further down.
EXTRA_CCC = {0x16D63: 0, 0x16D67: 0, 0x16D68: 0, 0x16D69: 0, 0x16D6A: 0}
EXTRA_MARK = {0x16D63: False, 0x16D67: False, 0x16D68: False, 0x16D69: False, 0x16D6A: False}
EXTRA_DECOMP = {
    0x16D68: (0x16D67, 0x16D67),
    0x16D69: (0x16D63, 0x16D67),
    0x16D6A: (0x16D69, 0x16D67),
}


def tsv(name: str) -> dict[int, str]:
    out = {}
    for line in (DATA / name).read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        out[int(parts[0], 16)] = parts[1] if len(parts) > 1 else ""
    return out


def unescape(v: str) -> str:
    out, i = [], 0
    while i < len(v):
        if v.startswith("\\u{", i):
            j = v.index("}", i)
            out.append(chr(int(v[i + 3 : j], 16)))
            i = j + 1
        else:
            out.append(v[i])
            i += 1
    return "".join(out)


latin = {k: unescape(v) for k, v in tsv("confusables_to_latin.tsv").items()}
tr39 = {k: unescape(v) for k, v in tsv("confusables_digit_tr39.tsv").items()}
upstream = set(tsv("confusables_upstream_sources.tsv"))
excluded_rows = []
for line in (DATA / "excluded_compositions.tsv").read_text().splitlines():
    if not line or line.startswith("#"):
        continue
    parts = line.split("\t")
    excluded_rows.append(parts)


def nfd(s: str) -> str:
    return disarm.normalize(s, form="NFD")


def nfkd(s: str) -> str:
    return disarm.normalize(s, form="NFKD")


def nfc(s: str) -> str:
    return disarm.normalize(s, form="NFC")


def ccc(cp: int) -> int:
    if cp in EXTRA_CCC:
        return EXTRA_CCC[cp]
    assert unicodedata.category(chr(cp)) != "Cn", f"U+{cp:04X} unknown to unicodedata"
    return unicodedata.combining(chr(cp))


def is_mark(cp: int) -> bool:
    if cp in EXTRA_MARK:
        return EXTRA_MARK[cp]
    return unicodedata.category(chr(cp)).startswith("M")


def canon_pair(cp: int) -> tuple[int, int] | None:
    if cp in EXTRA_DECOMP:
        return EXTRA_DECOMP[cp]
    d = unicodedata.decomposition(chr(cp))
    if not d or d.startswith("<"):
        return None
    parts = [int(x, 16) for x in d.split()]
    return (parts[0], parts[1]) if len(parts) == 2 else None


# Index every primary composite by its pair (composition exclusions and singletons
# are filtered by asking the library whether the composite survives NFC).
pairs: dict[tuple[int, int], int] = {}
for cp in list(range(0x110000)):
    if 0xD800 <= cp <= 0xDFFF:
        continue
    pr = canon_pair(cp)
    if pr is None:
        continue
    if nfc(nfd(chr(cp))) != chr(cp):
        continue  # excluded from composition
    pairs[pr] = cp

# Closure.
dom: set[int] = set(CPS)
while True:
    new = set(dom)
    for cp in dom:
        c = chr(cp)
        for s in (
            nfd(c),
            nfkd(c),
            nfc(c),
            disarm.fold_case(c),
            latin.get(cp, ""),
            tr39.get(cp, ""),
        ):
            new.update(ord(x) for x in s)
    for (a, b), p in pairs.items():
        if a in dom and b in dom:
            new.add(p)
    for parts in excluded_rows:  # the #481 widening map can emit its value
        if all(int(k, 16) in dom for k in parts[0].split()):
            new.add(int(parts[1], 16))
    if new == dom:
        break
    dom = new
DOM = sorted(dom)
for cp in DOM:
    assert not (0xAC00 <= cp <= 0xD7A3 or 0x1100 <= cp <= 0x11FF), "Hangul is outside the model"
    assert cp not in (0x08, 0x7F), "BS/DEL (ResolveDeletions) are outside the model"

# Cross-check the stated composition pairs against the library's NFC.
for (a, b), p in pairs.items():
    if a in dom and b in dom:
        assert nfc(chr(a) + chr(b)) == chr(p), (hex(a), hex(b), hex(p))


def lean_chars(s: str) -> str:
    return (
        "["
        + ", ".join(
            f"'\\u{ord(x):04X}'" if ord(x) <= 0xFFFF else f"(Char.ofNat 0x{ord(x):X})" for x in s
        )
        + "]"
    )


def chr_lit(cp: int) -> str:
    return f"'\\u{cp:04X}'" if cp <= 0xFFFF else f"(Char.ofNat 0x{cp:X})"


def nat_match(name: str, doc: str, ty: str, rows: list[tuple[int, str]], default: str) -> str:
    lines = [f"/-- {doc} -/", f"def {name} (c : Char) : {ty} :=", "  match c.toNat with"]
    for cp, val in rows:
        lines.append(f"  | 0x{cp:X} => {val}")
    lines.append(f"  | _ => {default}")
    return "\n".join(lines) + "\n"


def pred(name: str, doc: str, f) -> str:
    hits = [cp for cp in DOM if f(cp)]
    body = " || ".join(f"n == 0x{cp:X}" for cp in hits) or "false"
    return f"/-- {doc} -/\ndef {name} (c : Char) : Bool :=\n  let n := c.toNat\n  {body}\n"


def ws(cp: int) -> bool:
    # whitespace::is_fold_whitespace restricted to the domain (only U+0020 is in it).
    return cp in (0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x1C, 0x1D, 0x1E, 0x1F, 0x20)


def is_control(cp: int) -> bool:
    return unicodedata.category(chr(cp)) == "Cc" if cp not in EXTRA_CCC else False


def guard_nonascii(cp: int) -> bool:
    """presets.rs `acts_on_nonascii` for skeleton_key's mask (controls, collapse_ws,
    fold_case, prototype, confusables, marks, nfkc, bidi, zero_width, invisible),
    restricted to the domain, which holds no bidi/zero-width/invisible character."""
    c = chr(cp)
    return (
        is_mark(cp)
        or (is_control(cp) and not ws(cp))
        or ws(cp)
        or disarm.fold_case(c) != c
        or cp in latin
        or (0x1100 <= cp <= 0x11FF)
        or disarm.normalize(c, form="NFKC") != c
    )


out = []
out.append("/-! GENERATED by scripts/gen_tables.py from src/tables/data/*.tsv and the built")
out.append("library. Do not edit by hand. See that script's docstring for provenance. -/")
out.append("")
out.append("namespace Confusables.Tables")
out.append("")
for name, cp, why in ALPHABET:
    out.append(f"/-- {why} -/")
    out.append(f"def {name} : Char := {chr_lit(cp)}")
out.append("")
out.append("/-- The input alphabet: one representative per class the Rust code branches on. -/")
out.append("def alphabet : List Char := [" + ", ".join(n for n, _, _ in ALPHABET) + "]")
out.append("")
out.append(f"/-- The closed domain ({len(DOM)} code points). -/")
out.append("def domain : List Char := [" + ", ".join(chr_lit(cp) for cp in DOM) + "]")
out.append("")
out.append(
    nat_match(
        "ccc",
        "Canonical_Combining_Class.",
        "Nat",
        [(cp, str(ccc(cp))) for cp in DOM if ccc(cp) != 0],
        "0",
    )
)
out.append(
    pred(
        "isMark",
        "General_Category = Mark (`unicode_normalization::char::is_combining_mark`).",
        is_mark,
    )
)
out.append(
    nat_match(
        "canonDecomp",
        "Full canonical decomposition of one code point (library NFD).",
        "List Char",
        [(cp, lean_chars(nfd(chr(cp)))) for cp in DOM if nfd(chr(cp)) != chr(cp)],
        "[c]",
    )
)
out.append(
    nat_match(
        "compatDecomp",
        "Full compatibility decomposition of one code point (library NFKD).",
        "List Char",
        [(cp, lean_chars(nfkd(chr(cp)))) for cp in DOM if nfkd(chr(cp)) != chr(cp)],
        "[c]",
    )
)
comp_rows = sorted((a, b, p) for (a, b), p in pairs.items() if a in dom and b in dom)
lines = [
    "/-- Primary composites over the domain (composition exclusions removed). -/",
    "def composePair (a b : Char) : Option Char :=",
    "  match a.toNat, b.toNat with",
]
for a, b, p in comp_rows:
    lines.append(f"  | 0x{a:X}, 0x{b:X} => some {chr_lit(p)}")
lines.append("  | _, _ => none")
out.append("\n".join(lines) + "\n")
exc = []
for parts in excluded_rows:
    key = [int(x, 16) for x in parts[0].split()] if " " in parts[0] else None
    if key is None:
        continue
    if all(k in dom for k in key):
        exc.append((key, int(parts[1], 16)))
out.append(
    "/-- The #481 widening map (excluded_compositions.tsv) restricted to keys over the domain. -/"
)
out.append(
    "def excludedCompositions : List (Prod (List Char) Char) := ["
    + ", ".join(f"({lean_chars(''.join(map(chr, k)))}, {chr_lit(v)})" for k, v in exc)
    + "]"
)
out.append("")
out.append(
    nat_match(
        "latinMap",
        "confusables_to_latin.tsv.",
        "Option (List Char)",
        [(cp, f"some {lean_chars(latin[cp])}") for cp in DOM if cp in latin],
        "none",
    )
)
out.append(
    nat_match(
        "tr39Override",
        "confusables_digit_tr39.tsv.",
        "Option (List Char)",
        [(cp, f"some {lean_chars(tr39[cp])}") for cp in DOM if cp in tr39],
        "none",
    )
)
out.append(pred("upstreamSource", "confusables_upstream_sources.tsv.", lambda cp: cp in upstream))
out.append(
    nat_match(
        "caseFold",
        "Full case folding of one code point (`fold_case`).",
        "List Char",
        [
            (cp, lean_chars(disarm.fold_case(chr(cp))))
            for cp in DOM
            if disarm.fold_case(chr(cp)) != chr(cp)
        ],
        "[c]",
    )
)
out.append(pred("isControl", "`char::is_control` (General_Category = Cc).", is_control))
out.append(pred("isFoldWs", "`whitespace::is_fold_whitespace` (+ `is_blank_render`).", ws))
out.append(
    pred(
        "guardNonAscii", "presets.rs `acts_on_nonascii` under skeleton_key's mask.", guard_nonascii
    )
)
out.append("end Confusables.Tables")
OUT.write_text("\n".join(out) + "\n", encoding="ascii")
print(f"alphabet {len(CPS)}, domain {len(DOM)}, composites {len(comp_rows)}, excluded {len(exc)}")
