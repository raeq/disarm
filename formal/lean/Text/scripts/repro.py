#!/usr/bin/env python3
"""Minimal reproductions of every finding in README.md, on the installed library.

    python3 scripts/repro.py

Each block prints the actual value next to the value the documentation or the standard
leads a caller to expect. Exit status is the number of findings that did NOT reproduce
(0 means every finding is live on this build).

All non-ASCII characters in this file are written as escapes (see #802).
"""

from __future__ import annotations

import sys
import unicodedata

import disarm

live = 0
dead = 0


def show(name: str, reproduced: bool, lines: list[str]) -> None:
    global live, dead
    print(f"\n{name}: {'REPRODUCED' if reproduced else 'not reproduced'}")
    for line in lines:
        print("   ", line)
    if reproduced:
        live += 1
    else:
        dead += 1


def marks(s: str, m: str) -> int:
    return unicodedata.normalize("NFD", s).count(m)


# Z1: a class-0 mark between two runs of one mark resets the count.
ac = "\u0301"
s1 = "a" + ac * 3 + "\u034f" + ac * 3  # CGJ, which renders as nothing
s2 = "a" + (ac * 3 + "\u0e31") * 10  # a visible Thai vowel sign
s3 = "a" + (ac + "\u180b") * 20  # Mongolian FVS1: invisible, and canonicalize keeps it
show(
    "Z1 zalgo stack split by a class-0 mark",
    (
        not disarm.is_zalgo(s1)
        and marks(disarm.strip_zalgo(s1), ac) == 6
        and not disarm.is_zalgo(s2)
        and marks(disarm.strip_zalgo(s2), ac) == 30
        and marks(disarm.canonicalize(s3), ac) == 20
    ),
    [
        f"is_zalgo(a + 3*U+0301 + U+034F + 3*U+0301) = {disarm.is_zalgo(s1)}  (a run of 6 on one base)",
        f"U+0301 left by strip_zalgo(same) = {marks(disarm.strip_zalgo(s1), ac)}  (cap is 3)",
        f"is_zalgo(a + (3*U+0301 + U+0E31)*10) = {disarm.is_zalgo(s2)}; "
        f"U+0301 left by strip_zalgo = {marks(disarm.strip_zalgo(s2), ac)}",
        f"U+0301 left by canonicalize(a + (U+0301 + U+180B)*20) = {marks(disarm.canonicalize(s3), ac)}; "
        f"U+180B kept: {chr(0x180B) in disarm.canonicalize(s3)}",
        f"control: is_zalgo(a + 6*U+0301) = {disarm.is_zalgo('a' + ac * 6)}",
    ],
)

# Z2: the transform keeps one negation overlay beyond the cap, and the predicate counts it.
n4 = "=" + "\u0338" * 4
out = disarm.strip_zalgo(n4)
show(
    "Z2 strip_zalgo output is still zalgo (negation overlay)",
    (
        disarm.is_zalgo(out)
        and disarm.is_zalgo(disarm.strip_zalgo("\u2260", max_marks=0), threshold=0)
    ),
    [
        f"strip_zalgo('=' + 4*U+0338) = {ascii(out)}; is_zalgo of that = {disarm.is_zalgo(out)}",
        f"strip_zalgo(U+2260, max_marks=0) = {ascii(disarm.strip_zalgo(chr(0x2260), max_marks=0))}; "
        f"is_zalgo(that, threshold=0) = {disarm.is_zalgo(disarm.strip_zalgo(chr(0x2260), max_marks=0), threshold=0)}",
    ],
)

# Z3: the documented cap is per base; the code caps per combining class.
s = "a" + "\u0301" * 3 + "\u0316" * 3 + "\u0334" * 3
show(
    "Z3 'caps the marks per base character' (docstrings)",
    (
        not disarm.is_zalgo(s)
        and sum(
            1
            for c in unicodedata.normalize("NFD", disarm.strip_zalgo(s))
            if unicodedata.combining(c)
        )
        == 9
    ),
    [
        f"is_zalgo(a + 3*U+0301 + 3*U+0316 + 3*U+0334) = {disarm.is_zalgo(s)}; "
        f"marks kept by strip_zalgo = {sum(1 for c in unicodedata.normalize('NFD', disarm.strip_zalgo(s)) if unicodedata.combining(c))}",
    ],
)

# W1: a cluster opening with a zero-width Prepend measures 0.
show(
    "W1 Prepend cluster measures 0",
    (
        disarm.terminal_width("\u0600" + "1") == 0
        and disarm.terminal_width("\u0600" + "123") == 2
        and disarm.terminal_width(("\u0600" + "A") * 100) == 0
    ),
    [
        f"grapheme_split(U+0600 + '1') = {[ascii(x) for x in disarm.grapheme_split(chr(0x600) + '1')]}",
        f"terminal_width(U+0600 + '1') = {disarm.terminal_width(chr(0x600) + '1')}  (terminal_width('1') = 1)",
        f"terminal_width(U+0600 + '123') = {disarm.terminal_width(chr(0x600) + '123')}  (expected 3)",
        f"terminal_width((U+0600 + 'A') * 100) = {disarm.terminal_width((chr(0x600) + 'A') * 100)}  (expected 100)",
        f"terminal_width(U+110BD + 'x') = {disarm.terminal_width(chr(0x110BD) + 'x')}",
    ],
)
a = "\u0600"
show(
    "W1b limitations.md: 'the separator always starts a fresh cluster'",
    (disarm.grapheme_len(a + " ok") == 3),
    [
        f"grapheme_len(U+0600 + ' ' + 'ok') = {disarm.grapheme_len(a + ' ok')}  (the claim gives 1 + 1 + 2 = 4)",
        f"terminal_width(U+0600 + ' ' + 'ok') = {disarm.terminal_width(a + ' ok')}  "
        f"(terminal_width(a) + 1 + terminal_width('ok') = {disarm.terminal_width(a) + 1 + 2})",
    ],
)

# W2: stray VS16 widens a non-emoji base; stray VS15 is ignored.
show(
    "W2 stray VS16 widens a non-emoji base",
    (disarm.grapheme_width("a\ufe0f") == 2 and disarm.grapheme_width("a\ufe0e") == 1),
    [
        f"grapheme_width('a' + U+FE0F) = {disarm.grapheme_width('a' + chr(0xFE0F))}, "
        f"grapheme_width('a' + U+FE0E) = {disarm.grapheme_width('a' + chr(0xFE0E))}, grapheme_width('a') = 1",
        f"terminal_width('abc' with U+FE0F after each letter) = "
        f"{disarm.terminal_width(''.join(c + chr(0xFE0F) for c in 'abc'))}",
    ],
)

# C1: is_case_fold_stable is documented as fold_case(t) == t.lower(); the lowercase it
# compares with is Rust's, not the host's.
c = "\u1c89"
host_says = disarm.fold_case(c) == c.lower()
show(
    f"C1 is_case_fold_stable vs the host's str.lower (host UCD {unicodedata.unidata_version})",
    (disarm.is_case_fold_stable(c) != host_says),
    [
        f"is_case_fold_stable(U+1C89) = {disarm.is_case_fold_stable(c)}; "
        f"fold_case(U+1C89) == U+1C89.lower() on this host = {host_says}",
        f"fold_case(U+1C89) = {ascii(disarm.fold_case(c))}; U+1C89.casefold() = {ascii(c.casefold())}",
    ],
)

# C2: the #718 toolchain dependence is live: Unicode 17 letters the Unicode 16 fold table
# leaves alone read unstable on a build whose to_lowercase is Unicode 17.
new17 = ["\ua7ce", "\ua7d2", "\U00016ea0"]
show(
    "C2 is_case_fold_stable depends on the building toolchain's Unicode",
    (
        not any(disarm.is_case_fold_stable(x) for x in new17)
        and all(disarm.fold_case(x) == x for x in new17)
    ),
    [
        f"is_case_fold_stable of U+A7CE, U+A7D2, U+16EA0 = {[disarm.is_case_fold_stable(x) for x in new17]}",
        f"fold_case leaves them: {[disarm.fold_case(x) == x for x in new17]} "
        "(all three are unassigned in UCD 16.0, the table's version and rustc 1.88's)",
    ],
)

# D1: strip_zero_width_chars removes more than the set its docstring calls exact.
show(
    "D1 strip_zero_width_chars docstring 'the set is exactly' (10 code points)",
    (disarm.strip_zero_width_chars("a\U0001d173b") == "ab"),
    [
        f"strip_zero_width_chars('a' + U+1D173 + 'b') = {ascii(disarm.strip_zero_width_chars(chr(0x1D173).join('ab')))}",
    ],
)

# D2: limitations.md says canonicalize keeps 18 Default_Ignorable code points, including
# U+1BCA0..U+1BCA3 and U+1D173..U+1D17A.
show(
    "D2 limitations.md: the 18 Default_Ignorable code points canonicalize keeps",
    (
        disarm.canonicalize("a\U0001d173b") == "ab"
        and disarm.canonicalize("a\U0001bca0b") == "ab"
        and "\u180b" in disarm.canonicalize("a\u180bb")
    ),
    [
        f"canonicalize('a' + U+1D173 + 'b') = {ascii(disarm.canonicalize(chr(0x1D173).join('ab')))}",
        f"canonicalize('a' + U+1BCA0 + 'b') = {ascii(disarm.canonicalize(chr(0x1BCA0).join('ab')))}",
    ],
)

# D3: fold_punctuation's documented classes are not complete.
t = "a\u1680b\u201bc\u201fd\u2034e"
show(
    "D3 fold_punctuation leaves members of the classes it names",
    (disarm.fold_punctuation(t) == t),
    [
        f"fold_punctuation('a' U+1680 'b' U+201B 'c' U+201F 'd' U+2034 'e') = {ascii(disarm.fold_punctuation(t))}",
        f"collapse_whitespace('a' + U+1680 + 'b') = {disarm.collapse_whitespace(chr(0x1680).join('ab'))!r}",
    ],
)

print(f"\n{live} reproduced, {dead} not reproduced")
sys.exit(dead)
