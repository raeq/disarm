#!/usr/bin/env python3
"""Every Unicode scalar (and targeted pairs and triples) against each claimed property.

    python3 scripts/sweep.py

Needs an importable `disarm`. Two independent oracles are used when importable and skipped
(with a note) otherwise: the `regex` module (UAX #29 `\\X`, and the UCD properties
White_Space, Default_Ignorable_Code_Point, Grapheme_Cluster_Break, Grapheme_Extend,
Emoji_Presentation) and `unicodedata2` pinned to 15.1.0, the UCD the width table was built
from. Put them on `TEXT_ORACLE_PATH` (a `os.pathsep`-separated list of directories), for
example the unpacked wheels of `regex` and `unicodedata2==15.1.0`.

The host's own `unicodedata` is used for categories and combining classes; its version is
printed, and a property it cannot judge (a scalar it does not know) is skipped rather than
counted. Exit status is 0; this script reports, it does not gate.

All non-ASCII characters in this file are written as escapes (see #802).
"""

from __future__ import annotations

import os
import random
import sys
import unicodedata
from collections import Counter

for p in reversed(os.environ.get("TEXT_ORACLE_PATH", "").split(os.pathsep)):
    if p:
        sys.path.insert(0, p)

import disarm  # noqa: E402

try:
    import regex  # noqa: E402
except ImportError:
    regex = None
try:
    import unicodedata2 as ucd151  # noqa: E402

    if ucd151.unidata_version != "15.1.0":
        ucd151 = None
except ImportError:
    ucd151 = None

HOST = unicodedata.unidata_version


def scalars():
    for cp in range(0x110000):
        if not 0xD800 <= cp <= 0xDFFF:
            yield chr(cp)


def assigned(c: str) -> bool:
    return unicodedata.category(c) != "Cn"


def h(c: str) -> str:
    return f"U+{ord(c):04X}"


def section(title: str) -> None:
    print(f"\n== {title}")


# White_Space (PropList.txt, stable since Unicode 6.3) and Bidi_Control.
WHITE_SPACE = {
    *range(0x09, 0x0E),
    0x20,
    0x85,
    0xA0,
    0x1680,
    *range(0x2000, 0x200B),
    0x2028,
    0x2029,
    0x202F,
    0x205F,
    0x3000,
}
BIDI_CONTROL = {0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A)}


def sweep_case() -> None:
    section(f"fold_case / is_case_fold_stable (host UCD {HOST})")
    bad = Counter()
    unknown_to_host = []
    for c in scalars():
        f = disarm.fold_case(c)
        if not f:
            bad["empty"] += 1
        if disarm.fold_case(f) != f:
            bad["not idempotent"] += 1
        if any("A" <= x <= "Z" for x in f):
            bad["ASCII uppercase left"] += 1
        if c.isascii() and not f.isascii():
            bad["ASCII to non-ASCII"] += 1
        if assigned(c):
            if f != c.casefold():
                bad["differs from str.casefold on a scalar the host knows"] += 1
            if disarm.is_case_fold_stable(c) != (f == c.lower()):
                bad["is_case_fold_stable != (fold == lower) on a scalar the host knows"] += 1
        elif disarm.is_case_fold_stable(c) != (f == c.lower()):
            unknown_to_host.append(h(c))
    print("  per-scalar premise failures:", dict(bad) or "none")
    print(
        f"  scalars the host does not know where is_case_fold_stable(c) != (fold_case(c) == c.lower()):"
        f" {len(unknown_to_host)} {unknown_to_host[:8]}"
    )


def sweep_whitespace() -> None:
    section("collapse_whitespace / strip_control_chars / strip_zero_width_chars")
    folded, stripped_c, stripped_z = set(), set(), set()
    bad = Counter()
    for c in scalars():
        s = "a" + c + "b"
        if disarm.collapse_whitespace(s) == "a b":
            folded.add(ord(c))
        elif disarm.collapse_whitespace(s) != s:
            bad["collapse does something else"] += 1
        if disarm.strip_control_chars(s) == "ab":
            stripped_c.add(ord(c))
        if disarm.strip_zero_width_chars(s) == "ab":
            stripped_z.add(ord(c))
        once = disarm.collapse_whitespace(f"x{c}{c}y{c}z")
        if (
            disarm.collapse_whitespace(once) != once
            or "  " in once
            or once[:1] == " "
            or once[-1:] == " "
        ):
            bad["run-context invariant"] += 1
    want = WHITE_SPACE | set(range(0x1C, 0x20)) | {0x2800, 0x115F, 0x1160, 0x3164, 0xFFA0}
    print(
        "  fold set == White_Space + U+001C..U+001F + blank-render:",
        folded == want,
        sorted(map(hex, folded ^ want)),
    )
    cc = {ord(c) for c in scalars() if unicodedata.category(c) == "Cc"}
    print("  strip_control set == Cc - fold set:", stripped_c == cc - want)
    print(
        f"  strip_zero_width_chars removes {len(stripped_z)}:", [hex(x) for x in sorted(stripped_z)]
    )
    print("  other failures:", dict(bad) or "none")


def sweep_bidi_and_invisibles() -> None:
    section("strip_bidi / strip_tags / strip_variation_selectors / strip_noncharacters / strip_pua")
    sets = {n: set() for n in ("bidi", "tags", "vs", "nonch", "pua")}
    fns = {
        "bidi": disarm.strip_bidi,
        "tags": disarm.strip_tags,
        "vs": disarm.strip_variation_selectors,
        "nonch": disarm.strip_noncharacters,
        "pua": disarm.strip_pua,
    }
    for c in scalars():
        s = "a" + c + "b"
        for n, fn in fns.items():
            r = fn(s)
            if r == "ab":
                sets[n].add(ord(c))
            elif r != s:
                print("  unexpected", n, h(c))
    want = {
        "bidi": BIDI_CONTROL | {0xAD, *range(0x206A, 0x2070), *range(0xFFF9, 0xFFFC)},
        "tags": set(range(0xE0000, 0xE0080)),
        "vs": set(range(0xFE00, 0xFE10)) | set(range(0xE0100, 0xE01F0)),
        "nonch": set(range(0xFDD0, 0xFDF0))
        | {p * 0x10000 + x for p in range(17) for x in (0xFFFE, 0xFFFF)},
        "pua": set(range(0xE000, 0xF900))
        | set(range(0xF0000, 0xFFFFE))
        | set(range(0x100000, 0x10FFFE)),
    }
    for n in fns:
        print(
            f"  {n}: removes exactly the documented set: {sets[n] == want[n]}",
            sorted(map(hex, sets[n] ^ want[n]))[:8],
        )
    print("  Bidi_Control is a subset of strip_bidi:", BIDI_CONTROL <= sets["bidi"])


def sweep_marks() -> None:
    section("strip_accents / strip_zalgo(0) / strip_zalgo idempotence and NFC")
    bad = Counter()
    for c in scalars():
        for s in (c, c + "\u0338", "=" + c, c + "\u0301", c + "\u0301" * 5):
            a = disarm.strip_accents(s)
            if a != disarm.strip_zalgo(s, max_marks=0):
                bad["strip_accents != strip_zalgo(0)"] += 1
            if disarm.strip_accents(a) != a:
                bad["strip_accents not idempotent"] += 1
            z = disarm.strip_zalgo(s)
            if disarm.strip_zalgo(z) != z:
                bad["strip_zalgo not idempotent"] += 1
            if assigned(c) and not unicodedata.is_normalized("NFC", z):
                bad["strip_zalgo output not NFC"] += 1
            if assigned(c):
                left = [
                    x
                    for x in unicodedata.normalize("NFD", a)
                    if unicodedata.category(x)[0] == "M" and x not in "\u0338\u20d2"
                ]
                if left:
                    bad["strip_accents leaves a mark"] += 1
    print("  failures:", dict(bad) or "none")


def sweep_zalgo_separators() -> None:
    section("is_zalgo: every class-0 mark as a separator (Finding Z1)")
    nonzero = [
        c
        for c in scalars()
        if assigned(c) and unicodedata.category(c)[0] == "M" and unicodedata.combining(c) != 0
    ]
    zero = [
        c
        for c in scalars()
        if assigned(c) and unicodedata.category(c)[0] == "M" and unicodedata.combining(c) == 0
    ]
    print(f"  marks with a non-zero class: {len(nonzero)}; class-0 marks: {len(zero)}")
    # 1) every class-0 mark splits a run of U+0301
    seps = [z for z in zero if not disarm.is_zalgo("a" + "\u0301" * 3 + z + "\u0301" * 3)]
    print(
        f"  class-0 marks that hide 6 x U+0301 on one base from is_zalgo: {len(seps)}/{len(zero)}"
    )
    # 2) U+034F splits a run of every non-zero-class mark
    hid = [
        m
        for m in nonzero
        if not disarm.is_zalgo("a" + m * 3 + "\u034f" + m * 3) and disarm.is_zalgo("a" + m * 6)
    ]
    print(f"  non-zero-class marks whose 6-stack U+034F hides: {len(hid)}/{len(nonzero)}")
    if regex is not None:
        di = regex.compile(r"\p{Default_Ignorable_Code_Point}")
        inv = [h(z) for z in seps if di.match(z)]
        print(f"  of the separators, Default_Ignorable (render as nothing): {inv}")
        kept = [h(z) for z in seps if di.match(z) and z in disarm.canonicalize("a" + z + "b")]
        print(f"  ... and of those, kept by canonicalize: {kept}")


def sweep_width() -> None:
    section("grapheme_width per scalar, and the Prepend clusters (Finding W1)")
    if regex is None or ucd151 is None:
        print("  skipped: needs regex and unicodedata2==15.1.0 on TEXT_ORACLE_PATH")
        return
    di = regex.compile(r"\p{Default_Ignorable_Code_Point}")
    ge = regex.compile(r"\p{Grapheme_Extend}")
    ep = regex.compile(r"\p{Emoji_Presentation}")
    ri = regex.compile(r"\p{Regional_Indicator}")
    pre = regex.compile(r"\p{Grapheme_Cluster_Break=Prepend}")

    def oracle(c: str, amb: bool) -> int:
        cp = ord(c)
        if cp < 0x80:
            return 0 if cp < 0x20 or cp == 0x7F else 1
        if ep.match(c) or ri.match(c):
            return 2
        if (
            ucd151.category(c) in ("Cc", "Cf", "Mn", "Me")
            or di.match(c)
            or ge.match(c)
            or 0x1160 <= cp <= 0x11FF
        ):
            return 0
        e = ucd151.east_asian_width(c)
        return 2 if e in ("W", "F") else (2 if amb and e == "A" else 1)

    diffs = Counter()
    for c in scalars():
        if ucd151.category(c) == "Cn":
            continue  # the oracle's other properties come from a newer UCD
        for amb in (False, True):
            if disarm.grapheme_width(c, ambiguous_wide=amb) != oracle(c, amb):
                diffs[(ucd151.category(c), amb)] += 1
    print(
        f"  per-scalar differences from UAX #11 + the documented zero-width rule (UCD 15.1): {dict(diffs) or 'none'}"
    )
    prepends = [c for c in scalars() if pre.match(c)]
    zero = []
    for p in prepends:
        s = p + "7"
        if disarm.grapheme_len(s) == 1 and disarm.terminal_width(s) == 0:
            zero.append(h(p))
    print(
        f"  Prepend scalars: {len(prepends)}; Prepend + '7' is one cluster of width 0 for: {zero}"
    )
    # The limitations.md claim: the separator always starts a fresh cluster on its left.
    glued = [h(p) for p in prepends if disarm.grapheme_len(p + " ok") != 1 + 1 + 2]
    print(
        f"  a + ' ' + b with a = one Prepend scalar: the space does not start a cluster for {len(glued)}"
    )


def sweep_graphemes() -> None:
    section("grapheme_split / grapheme_len / grapheme_truncate")
    bad = Counter()
    x = regex.compile(r"\X") if regex is not None else None
    for c in scalars():
        for s in ("a" + c + "b", c + c, "\u0600" + c, c + "\u200d\U0001f600"):
            parts = disarm.grapheme_split(s)
            if "".join(parts) != s:
                bad["split does not concatenate back"] += 1
            if len(parts) != disarm.grapheme_len(s):
                bad["len != len(split)"] += 1
            if x is not None and parts != x.findall(s):
                bad["differs from regex \\X"] += 1
    rng = random.Random(29)
    pool = [
        "a",
        "\r",
        "\n",
        "\u0301",
        "\u200d",
        "\U0001f600",
        "\U0001f1e6",
        "\u1100",
        "\u1161",
        "\u11a8",
        "\u0600",
        "\u0915",
        "\u094d",
        "\ufe0f",
        "\U0001f3fb",
        " ",
    ]
    for _ in range(200_000):
        s = "".join(rng.choice(pool) for _ in range(rng.randint(0, 12)))
        n = rng.randint(0, 8)
        t = disarm.grapheme_truncate(s, n)
        parts = disarm.grapheme_split(s)
        if not s.startswith(t) or disarm.grapheme_split(t) != parts[:n]:
            bad["truncate is not the first n clusters"] += 1
    print("  failures:", dict(bad) or "none", "" if x else "(no regex oracle)")


def sweep_punct() -> None:
    section("fold_punctuation")
    changed = {}
    bad = Counter()
    for c in scalars():
        r = disarm.fold_punctuation(c)
        if r != c:
            changed[ord(c)] = r
        if disarm.fold_punctuation(r) != r:
            bad["not idempotent"] += 1
        if c.isascii() and r != c:
            bad["changes ASCII"] += 1
    print(f"  scalars folded: {len(changed)}; failures: {dict(bad) or 'none'}")
    zs = [
        h(c)
        for c in scalars()
        if unicodedata.category(c) == "Zs" and c != " " and ord(c) not in changed
    ]
    pi_pf = [
        h(c) for c in scalars() if unicodedata.category(c) in ("Pi", "Pf") and ord(c) not in changed
    ]
    pd = [
        h(c)
        for c in scalars()
        if unicodedata.category(c) == "Pd" and c != "-" and ord(c) not in changed
    ]
    print(f"  Zs not folded: {zs}")
    print(f"  Pi/Pf (quotes) not folded: {pi_pf}")
    print(f"  Pd (dashes) not folded: {len(pd)} {pd[:12]}")


def main() -> int:
    print(
        f"disarm {disarm.__version__}; host UCD {HOST}; regex oracle: {regex is not None}; "
        f"UCD 15.1 oracle: {ucd151 is not None}"
    )
    for f in (
        sweep_case,
        sweep_whitespace,
        sweep_bidi_and_invisibles,
        sweep_marks,
        sweep_zalgo_separators,
        sweep_width,
        sweep_graphemes,
        sweep_punct,
    ):
        f()
    return 0


if __name__ == "__main__":
    sys.exit(main())
