#!/usr/bin/env python3
"""Generate Presets/Tables.lean: the per-character data the model's steps read.

The model works on code points (`Nat`). Its *input alphabet* is `SEEDS` below, one or two
representatives per class the step code branches on. Its *domain* is the closure of the
seeds under every per-character map a step applies (case fold, the raw confusable row under
each digit policy, transliteration, NFD/NFKD) and under canonical composition of any base
with any mark in the domain, so no step can produce a code point the tables do not
describe.

Every per-character map is read from the built library, not written by hand:

* ``fold``            <- ``disarm.fold_case(ch)``
* ``conf pol``        <- ``disarm.TextPipeline(confusables=True, digit_policy=pol)(ch)``,
                         which with no normalize form is the single-pass per-character
                         lookup ``normalize_confusables_into`` (src/pipeline.rs)
* ``translitP/I``     <- ``disarm.transliterate(ch, errors="preserve"/"ignore")``
* ``script``          <- ``disarm.detect_scripts(ch)`` (Latin / Common / Inherited or not)

The Unicode properties (decompositions, combining class, general category) come from
Python's ``unicodedata``; the characters in the alphabet are all old enough that its
version does not matter, and the differential test would catch a disagreement.

The predicates the strip steps test (zero-width, bidi, control, whitespace, tags, PUA,
...) are restated from the Rust source they cite, then checked against the library in
``check_predicates`` before anything is written.

Run from the repository root:  python3 formal/lean/Presets/scripts/gen_tables.py
"""

from __future__ import annotations

import pathlib
import unicodedata

import disarm

OUT = pathlib.Path(__file__).resolve().parents[1] / "Presets" / "Tables.lean"

# (code point, why it is in the alphabet). Escapes only: see the README.
SEEDS = [
    (0x61, "a: inert lowercase ASCII letter"),
    (0x65, "e: composes with U+0301"),
    (0x75, "u: composes with U+0308"),
    (0x79, "y: composes with U+0301"),
    (0x6C, "l: the prototype of the I family"),
    (0x49, "I: prototype fold source, case-folds to i"),
    (0x41, "A: uppercase ASCII"),
    (0x31, "1: tr39 prototype digit"),
    (0x7C, "|: the ASCII confusable source that folds to l"),
    (0x20, "space"),
    (0x09, "TAB: a whitespace control, folded not stripped"),
    (0x0A, "LF: a line break for the deletion resolver"),
    (0x08, "BS: erases the preceding cell"),
    (0x00, "NUL: a removed control that occupies a cell"),
    (0x301, "combining acute, ccc 230"),
    (0x308, "combining diaeresis, ccc 230"),
    (0x338, "combining long solidus overlay, ccc 1: a negation overlay (#749)"),
    (0xE9, "e with acute, precomposed"),
    (0xFD, "y with acute, precomposed"),
    (0x3B0, "Greek upsilon with dialytika and tonos: case-folds to three code points"),
    (0x3C5, "Greek upsilon: confusable u, transliterates y"),
    (0xA2, "cent sign: a symbol whose confusable row is a letter (c)"),
    (0xA5, "yen sign: confusable Y, transliterates JPY"),
    (0x3D, "=: a relation, a surviving negation base"),
    (0x440, "Cyrillic er: confusable p, transliterates r"),
    (0xA760, "Latin capital VY: no confusable row, case-folds to U+A761"),
    (0xA761, "Latin small vy: confusable w"),
    (0x1C1, "Latin letter lateral click: transliterates to two vertical bars"),
    (0x100, "A with macron: case-folds to U+0101, whose tr39 row is a with tilde"),
    (0x200B, "ZWSP: zero-width, occupies no cell"),
    (0xAD, "soft hyphen: stripped by strip_bidi, occupies a cell"),
    (0x34F, "CGJ: a combining mark (ccc 0) that strip-invisible removes"),
    (0xFE0F, "VS16: a variation selector, a mark with ccc 0"),
    (0xE000, "Private Use Area"),
    (0x202E, "RLO: a bidi control"),
    (0xFF21, "fullwidth A: NFKC-unstable"),
    (0x1100, "Hangul choseong kiyeok: a conjoining L jamo"),
    (0x1161, "Hangul jungseong a: L + V composes to U+AC00, a composition of two starters"),
]

#: Not in the input alphabet, but reachable: compose-at-lookup (src/compose.rs) turns a
#: diaeresis + acute cluster into the composition-excluded U+0344 through the widening map.
EXTRA = [0x344]

ROOT = pathlib.Path(__file__).resolve().parents[4]
EXCLUDED = ROOT / "src" / "tables" / "data" / "excluded_compositions.tsv"

POLICIES = ["numeric", "tr39", "preserve"]
PIPE = {p: disarm.TextPipeline(confusables=True, digit_policy=p) for p in POLICIES}


def is_mark(c: int) -> bool:
    return unicodedata.category(chr(c)).startswith("M")


def cps(s: str) -> list[int]:
    return [ord(ch) for ch in s]


def closure(seeds: list[int], rounds: int = 6) -> list[int]:
    dom = set(seeds)
    for _ in range(rounds):
        new = set()
        for c in list(dom):
            ch = chr(c)
            images = [
                disarm.fold_case(ch),
                disarm.transliterate(ch, errors="preserve"),
                disarm.transliterate(ch, errors="ignore"),
                unicodedata.normalize("NFD", ch),
                unicodedata.normalize("NFKD", ch),
                unicodedata.normalize("NFKC", ch),
            ] + [PIPE[p](ch) for p in POLICIES]
            for s in images:
                new.update(cps(s))
        marks = [m for m in dom | new if is_mark(m)]
        bases = [b for b in dom | new if not is_mark(b)]
        for b in bases:
            for c in bases:
                t = unicodedata.normalize("NFC", chr(b) + chr(c))
                if len(t) == 1:
                    new.add(ord(t))
            for m in marks:
                s = unicodedata.normalize("NFC", chr(b) + chr(m))
                if len(s) == 1:
                    new.add(ord(s))
                for m2 in marks:
                    s = unicodedata.normalize("NFC", chr(b) + chr(m) + chr(m2))
                    new.update(cps(s))
        if new <= dom:
            break
        dom |= new
    return sorted(dom)


# --- predicates restated from src/ -----------------------------------------------------


def is_zero_width(c: int) -> bool:  # whitespace.rs is_zero_width / invisibles.rs
    return (
        c in (0x200B, 0x200C, 0x200D, 0xFEFF, 0x180E)
        or 0x2060 <= c <= 0x2064
        or (0x1BCA0 <= c <= 0x1BCA3 or 0x1D173 <= c <= 0x1D17A)
    )


def is_bidi_or_format(c: int) -> bool:  # presets.rs is_bidi_or_format
    return (
        c in (0x61C, 0x200E, 0x200F, 0xAD)
        or 0x202A <= c <= 0x202E
        or 0x2066 <= c <= 0x2069
        or 0x206A <= c <= 0x206F
        or 0xFFF9 <= c <= 0xFFFB
    )


def is_fold_ws(c: int) -> bool:  # whitespace.rs is_fold_whitespace
    return (
        0x09 <= c <= 0x0D
        or 0x1C <= c <= 0x1F
        or c in (0x85, 0x20, 0xA0, 0x1680, 0x2028, 0x2029, 0x202F, 0x205F, 0x3000)
        or 0x2000 <= c <= 0x200A
    )


def is_blank_render(c: int) -> bool:
    return c in (0x2800, 0x115F, 0x1160, 0x3164, 0xFFA0)


def is_control(c: int) -> bool:  # Rust char::is_control: general category Cc
    return unicodedata.category(chr(c)) == "Cc"


def is_tag(c: int) -> bool:
    return 0xE0000 <= c <= 0xE007F


def is_vs(c: int) -> bool:
    return 0xFE00 <= c <= 0xFE0F or 0xE0100 <= c <= 0xE01EF


def is_nonchar(c: int) -> bool:
    return 0xFDD0 <= c <= 0xFDEF or (c & 0xFFFF) >= 0xFFFE


def is_pua(c: int) -> bool:
    return 0xE000 <= c <= 0xF8FF or 0xF0000 <= c <= 0xFFFFD or 0x100000 <= c <= 0x10FFFD


def is_dif(c: int) -> bool:  # invisibles.rs is_default_ignorable_format
    return 0x1BCA0 <= c <= 0x1BCA3 or 0x1D173 <= c <= 0x1D17A


def is_alnum(c: int) -> bool:  # Rust char::is_alphanumeric, on this alphabet
    return unicodedata.category(chr(c))[0] in "LN"


def occupies_cell(c: int) -> bool:  # deletions.rs occupies_cell
    return not (
        is_mark(c)
        or is_zero_width(c)
        or is_vs(c)
        or is_dif(c)
        or is_tag(c)
        or (is_bidi_or_format(c) and c != 0xAD)
    )


def survives_neg(c: int) -> bool:  # transliterate.rs survives_as_a_negation_base
    ch = chr(c)
    if is_control(c) or ch.isspace() or is_nonchar(c):
        return False
    if c in (0x115F, 0x1160, 0x3164, 0xFFA0, 0x2800) or is_zero_width(c) or is_dif(c) or is_tag(c):
        return False
    first = unicodedata.normalize("NFKC", ch)[:1]
    return bool(first) and not first.isspace() and not is_control(ord(first))


def keeps_script(c: int) -> bool:  # presets.rs transliterate_preserving_latin_into
    if c < 0x80:
        return True
    scripts = [
        str(s.value if hasattr(s, "value") else s).lower() for s in disarm.detect_scripts(chr(c))
    ]
    return scripts == [] or scripts == ["latin"] or is_mark(c)


def check_predicates(dom: list[int]) -> None:
    for c in dom:
        ch = chr(c)
        assert (disarm.strip_zero_width_chars(ch) == "") == is_zero_width(c), hex(c)
        assert (disarm.strip_bidi(ch) == "") == is_bidi_or_format(c), hex(c)
        removed = disarm.strip_control_chars(ch) == ""
        assert removed == (is_control(c) and not is_fold_ws(c)), hex(c)
        folded = disarm.collapse_whitespace("a" + ch + "a") == "a a"
        assert folded == (is_fold_ws(c) or is_blank_render(c)), hex(c)
        assert (disarm.strip_pua(ch) == "") == is_pua(c), hex(c)
        assert unicodedata.normalize("NFD", ch) == disarm.normalize(ch, form="NFD"), hex(c)
        assert unicodedata.normalize("NFKD", ch) == disarm.normalize(ch, form="NFKD"), hex(c)


def lean_list(xs: list[int]) -> str:
    return "[" + ", ".join(f"0x{x:X}" for x in xs) + "]"


def table(name: str, doc: str, rows: dict[int, list[int]]) -> str:
    out = [
        f"/-- {doc} Identity (`none`) off the listed rows. -/",
        f"def {name} : Nat -> Option (List Nat)",
    ]
    for c in sorted(rows):
        out.append(f"  | 0x{c:X} => some {lean_list(rows[c])}")
    out.append("  | _ => none")
    return "\n".join(out) + "\n"


def pred(name: str, doc: str, dom: list[int], f) -> str:
    hits = [c for c in dom if f(c)]
    if not hits:
        return f"/-- {doc} -/\ndef {name} (_c : Nat) : Bool := false\n"
    body = " || ".join(f"c == 0x{c:X}" for c in hits)
    return f"/-- {doc} -/\ndef {name} (c : Nat) : Bool := {body}\n"


def main() -> None:
    seeds = [c for c, _ in SEEDS]
    dom = closure(seeds + EXTRA)
    check_predicates(dom)
    widen = []
    for line in EXCLUDED.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        key, val = line.split("\t")
        kcps = [int(x, 16) for x in key.split()]
        if all(k in dom for k in kcps) and (kcps, int(val, 16)) not in widen:
            widen.append((kcps, int(val, 16)))
    comps = {}
    for b in dom:
        for m in dom:
            s = unicodedata.normalize("NFC", chr(b) + chr(m))
            if len(s) == 1 and unicodedata.normalize("NFD", s) != s and ord(s) in dom:
                # primary composite: NFD of the result starts with b's NFD and ends with m
                comps[(b, m)] = ord(s)

    parts = [
        "/-!\nGenerated by `scripts/gen_tables.py` from the built library and `unicodedata`.",
        "Do not edit by hand. Code points are written in hex; see the README for what each",
        "input-alphabet entry represents.\n-/\n",
        "namespace Presets\n",
        f"/-- The input alphabet: one or two representatives per class the steps branch on. -/\ndef inputAlphabet : List Nat := {lean_list(seeds)}\n",
        f"/-- The domain: the closure of `inputAlphabet` under every per-character map. -/\ndef domain : List Nat := {lean_list(dom)}\n",
    ]
    ccc = {c: [unicodedata.combining(chr(c))] for c in dom if unicodedata.combining(chr(c))}
    parts.append(table("cccT", "Canonical combining class, as a singleton list.", ccc))
    parts.append(
        table(
            "nfdT",
            "Full canonical decomposition.",
            {
                c: cps(unicodedata.normalize("NFD", chr(c)))
                for c in dom
                if unicodedata.normalize("NFD", chr(c)) != chr(c)
            },
        )
    )
    parts.append(
        table(
            "nfkdT",
            "Full compatibility decomposition.",
            {
                c: cps(unicodedata.normalize("NFKD", chr(c)))
                for c in dom
                if unicodedata.normalize("NFKD", chr(c)) != chr(c)
            },
        )
    )
    comp_rows = "\n".join(
        f"  | 0x{b:X}, 0x{m:X} => some 0x{r:X}" for (b, m), r in sorted(comps.items())
    )
    parts.append(
        "/-- Primary composites: `compose b m = some r` when NFC composes the pair. -/\n"
        "def compose : Nat -> Nat -> Option Nat\n" + comp_rows + "\n  | _, _ => none\n"
    )
    parts.append(
        table(
            "foldT",
            "Full case folding (`disarm.fold_case`).",
            {c: cps(disarm.fold_case(chr(c))) for c in dom if disarm.fold_case(chr(c)) != chr(c)},
        )
    )
    for p in POLICIES:
        parts.append(
            table(
                f"conf_{p}",
                f"The raw single-pass confusable row under `{p}`.",
                {c: cps(PIPE[p](chr(c))) for c in dom if PIPE[p](chr(c)) != chr(c)},
            )
        )
    parts.append(
        table(
            "translitP",
            'Transliteration, `errors="preserve"`, one code point at a time.',
            {
                c: cps(disarm.transliterate(chr(c), errors="preserve"))
                for c in dom
                if disarm.transliterate(chr(c), errors="preserve") != chr(c)
            },
        )
    )
    parts.append(
        table(
            "translitI",
            'Transliteration, `errors="ignore"`, one code point at a time.',
            {
                c: cps(disarm.transliterate(chr(c), errors="ignore"))
                for c in dom
                if disarm.transliterate(chr(c), errors="ignore") != chr(c)
            },
        )
    )
    parts.append(
        "/-- The compose-at-lookup widening map (`EXCLUDED_COMPOSITIONS`, src/compose.rs),\n"
        "restricted to keys inside the domain. -/\n"
        "def widenKeys : List (Prod (List Nat) Nat) := ["
        + ", ".join(f"({lean_list(k)}, 0x{v:X})" for k, v in widen)
        + "]\n"
    )
    parts.append(pred("isMark", "General_Category = M (`is_combining_mark`).", dom, is_mark))
    parts.append(pred("isZeroWidth", "`whitespace::is_zero_width`.", dom, is_zero_width))
    parts.append(pred("isBidiOrFormat", "`presets::is_bidi_or_format`.", dom, is_bidi_or_format))
    parts.append(pred("isFoldWs", "`whitespace::is_fold_whitespace`.", dom, is_fold_ws))
    parts.append(pred("isBlankRender", "`whitespace::is_blank_render`.", dom, is_blank_render))
    parts.append(pred("isControl", "`char::is_control` (Cc).", dom, is_control))
    parts.append(pred("isTag", "`invisibles::is_tag`.", dom, is_tag))
    parts.append(pred("isVS", "`invisibles::is_variation_selector`.", dom, is_vs))
    parts.append(pred("isNonchar", "`invisibles::is_noncharacter`.", dom, is_nonchar))
    parts.append(pred("isPUA", "`invisibles::is_pua`.", dom, is_pua))
    parts.append(pred("isDIF", "`invisibles::is_default_ignorable_format`.", dom, is_dif))
    parts.append(pred("isAlnum", "`char::is_alphanumeric`.", dom, is_alnum))
    parts.append(pred("occupiesCell", "`deletions::occupies_cell`.", dom, occupies_cell))
    parts.append(
        pred("survivesNeg", "`transliterate::survives_as_a_negation_base`.", dom, survives_neg)
    )
    parts.append(
        pred(
            "keepsScript",
            "Latin, Common or Inherited: kept verbatim by `sort_key`'s transliteration.",
            dom,
            keeps_script,
        )
    )
    parts.append("end Presets\n")
    OUT.write_text("\n".join(parts), encoding="ascii")
    print(f"domain {len(dom)} code points, {len(comps)} composites -> {OUT}")


if __name__ == "__main__":
    main()
