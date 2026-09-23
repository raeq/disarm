#!/usr/bin/env python3
"""Reproduce every finding in README.md on the installed library.

    python3 scripts/repro.py

Each line prints the call, what the library returned, and what the property requires.
Exit status is the number of findings that did NOT reproduce (0 = all reproduced).
Non-ASCII test data is written as escapes only.
"""

from __future__ import annotations

import sys
import unicodedata

import disarm

f = disarm.sanitize_filename
s = disarm.slugify
failed = 0


def check(label: str, got, reproduced: bool, note: str) -> None:
    global failed
    mark = "REPRODUCED" if reproduced else "not reproduced"
    print(f"[{label}] {mark}: {ascii(got)}  -- {note}")
    if not reproduced:
        failed += 1


RESERVED = (
    {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(10)} | {f"LPT{i}" for i in range(10)}
)

# Finding 1
for t in ["_.con", "*.con", " .nul", "/.aux", "../.con", "\x00.com1", "?.LPT1"]:
    o = f(t)
    check(
        "F1",
        (t, o, f(o)),
        o.upper() in RESERVED,
        "a bare reserved device name; a second call prefixes it",
    )
o = f("*.NUL", platform="windows")
check("F1", ("*.NUL", "windows", o), o.upper() in RESERVED, "platform='windows' too")

# Finding 2
o = f("con _", separator=" ", max_length=4, preserve_extension=False)
check("F2", o, o == "con", "separator=' ' + truncation yields a bare 'con'")
o = f("AUX .txt", separator=" ", preserve_extension=False)
check("F2", o, o == "AUX .txt", "stem 'AUX ' passes the check; Windows strips the space")
o = f("../etc/passwd", separator="/")
check("F2", o, o == "/etc/passwd", "separator='/' yields an absolute path")
o = f("a b", separator="\x00")
check("F2", o, "\x00" in o, "separator='\\x00' puts NUL in the name")
try:
    disarm.strip_log_injection("x", replacement="\r")
    check("F2-contrast", "accepted", False, "strip_log_injection validates its replacement")
except Exception as e:  # noqa: BLE001
    print(f"[F2-contrast] strip_log_injection rejects a bad replacement: {type(e).__name__}")

# Finding 3
for t, kw in [
    ("_.x.*", {}),
    ("ab_cd", {"max_length": 3, "preserve_extension": False}),
    ("a.bcd.txt", {"max_length": 6}),
    ("a. .b", {"separator": "", "preserve_extension": False}),
    (". ./", {"separator": "-", "preserve_extension": False}),
]:
    o = f(t, **kw)
    o2 = f(o, **kw)
    check("F3", (t, kw, o, o2), o2 != o, "not a fixed point")

# Finding 4: allow_unicode keeps 130 So symbols
o = s("\u24b6dmin", allow_unicode=True)
check("F4", o, o == "\u24d0dmin", "circled letter (So) kept; docs say symbols become separators")
n = sum(
    1
    for cp in range(0x110000)
    if not 0xD800 <= cp <= 0xDFFF
    and unicodedata.category(chr(cp)) == "So"
    and s(chr(cp), allow_unicode=True)
)
check("F4", n, n > 0, "count of So characters slugify(allow_unicode=True) keeps")

# Finding 5
o = s("a b", separator="-_", max_length=2)
check(
    "F5",
    (o, s("a b", separator="-_", max_length=2, word_boundary=True)),
    o == "a-",
    "partial separator left by plain truncation; word_boundary=True strips it",
)

# Finding 6
o = s("very long title here", max_length=9, word_boundary=True)
check("F6", o, o == "very", "'very-long' is 9 bytes and ends on a word (python-slugify returns it)")

# Finding 7
o = s("The Fox", stopwords=["The"])
check("F7", o, o == "the-fox", "Rust docs: stopwords are case-insensitive")

# Finding 8
o = s("abc", separator="", stopwords=["b"])
check("F8", o, o == "ac", "with separator='' each character is tested as a word")

# Finding 9
u = disarm.UniqueSlugifier(max_length=5)
o = [u("ab cd") for _ in range(3)]
check("F9", o, o[1] == "ab--1", "doubled separator")
u = disarm.UniqueSlugifier(max_length=2)
o = [u("ab") for _ in range(3)]
check("F9", o, o[1] == "-1", "leading separator, base dropped")
u = disarm.UniqueSlugifier()
o = [u("!!!") for _ in range(3)]
check("F9", o, o[1] == "-1", "empty slug suffixed to a leading-separator slug")
u = disarm.UniqueSlugifier(max_length=13, allow_unicode=True)
o = [u("a\u0915\u094d\u200d\u0937") for _ in range(2)]
check("F9", o, o[1] == "a\u0915\u094d\u200d-1", "ZWJ at the end of a token; cluster split")

# Finding 10
a = s("T\u0308", allow_unicode=True)
b = s("\u1e97", allow_unicode=True)
check(
    "F10",
    (a, b),
    a != b and not unicodedata.is_normalized("NFC", a),
    "same text after lowercasing, two slugs; the first is not NFC and not a fixed point",
)
check("F10", s(a, allow_unicode=True), s(a, allow_unicode=True) != a, "second call recomposes")

# Finding 11
o = s("\u1f82", allow_unicode=True)
nfd = unicodedata.normalize("NFD", o)
check(
    "F11", o, sum(1 for c in nfd if unicodedata.combining(c)) == 3, "three marks on one base kept"
)

# Finding 12
for h in [
    "e\u00advil.com",
    "e\u115fvil.com",
    "e\u034fvil.com",
    "e\u180bvil.com",
    "e\U0001bca0vil.com",
]:
    sus, an = disarm.is_suspicious_hostname(h)
    check(
        "F12",
        (h, sus, an.has_invisible, an.compat_fold, an.canonical, disarm.has_anomalies(h)),
        not sus and an.canonical == "evil.com",
        "UTS #46 deletes it; screens clean",
    )

# Finding 13
for t, ml in [("a\u200db", 4), ("a\u200cb", 4), ("ab\u200dc", 5)]:
    o = s(t, allow_unicode=True, max_length=ml)
    check(
        "F13",
        (t, ml, o),
        o[-1:] in ("\u200c", "\u200d"),
        "the grapheme-boundary cut keeps a joiner attached to the character before it",
    )
o = s("a\u200db", allow_unicode=True, max_length=4, word_boundary=True)
check("F13", o, o == "a\u200d", "word_boundary=True too")

# Finding 14
o = disarm.decode_to_utf8(b"\xfe\xff\x00A", "utf-8", strict=True)
check(
    "F14",
    o,
    o == ("A", False),
    "explicit UTF-8 + strict: invalid UTF-8 bytes decoded as UTF-16BE, no error",
)
o = disarm.decode_to_utf8(b"\xff\xfeA\x00B\x00", "iso-8859-1")
check("F14", o, o == ("AB", False), "explicit ISO-8859-1 overridden by a UTF-16LE BOM")

# Finding 15
o = f("%\uff05\uff12\uff25\uff05\uff12\uff25\uff05\uff12\uff26etc.txt")
check("F15", o, "%2E%2E%2F" in o, "one typed '%' lets the manufactured %2E%2E%2F through")

print(f"\n{failed} not reproduced")
sys.exit(failed)
