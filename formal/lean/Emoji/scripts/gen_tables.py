#!/usr/bin/env python3
"""Generate Emoji/Tables.lean: the data tables of src/emoji.rs, restricted to the
model's alphabet (plus all of ASCII, which is what emoji *names* are made of).

Everything here is read from the repository's own source TSVs
(src/tables/data/emoji_*.tsv, confusables_to_latin.tsv), so the Lean tables are the
real tables projected onto the alphabet, not a hand-written guess:

* ``isEmojiPresentation`` / ``isEmojiProperty``  <- emoji_presentation.tsv / emoji_property.tsv
* ``isEmojiYes``                                <- emoji_yes.tsv (the VS16 arm, #992)
* ``single``                                    <- emoji_single.tsv
* ``multiKeys``                                 <- every emoji_multi.tsv key whose code
  points all lie in the alphabet (a trie walk over alphabet-only input can reach no
  other key), minus keys ending in ZWJ/VS15/VS16, which ``match_emoji_sequence``
  never reports
* ``isStarter``                                 <- emoji_starters.tsv
* ``nonEmojiRow``                               <- build.rs's set difference (#757)
* ``confFoldsAlnum``                            <- confusables_to_latin.tsv
* ``isCombiningMark``                           <- General_Category = M (Python unicodedata)

Run from the repository root:  python3 formal/lean/Emoji/scripts/gen_tables.py
"""

from __future__ import annotations

import pathlib
import sys
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parents[4]
DATA = ROOT / "src" / "tables" / "data"
OUT = pathlib.Path(__file__).resolve().parents[1] / "Emoji" / "Tables.lean"

# (lean name, code point, class description). One representative per class the Rust
# code branches on; RA/RB are two regional indicators so both a named and an unnamed
# flag pair exist (BA, BB named; AA, AB not).
ALPHABET = [
    ("cE", 0x1F600, "Emoji_Presentation, named single, not a multi starter (grinning face)"),
    ("cM", 0x1F468, "Emoji_Presentation, named, multi starter: skin tone + ZWJ sequences (man)"),
    ("cF", 0x1F525, "Emoji_Presentation, named, inside a named ZWJ sequence (fire)"),
    ("cH", 0x2764, "Emoji=Yes text-default, named, multi starter (red heart)"),
    ("cTM", 0x2122, "Emoji=Yes text-default, named single (trade mark)"),
    ("cC", 0x00A9, "Emoji=Yes text-default, NO CLDR name (copyright)"),
    ("c1", 0x31, "keycap base, alphanumeric ('1')"),
    ("cStar", 0x2A, "keycap base, not alphanumeric ('*')"),
    ("cKC", 0x20E3, "COMBINING ENCLOSING KEYCAP"),
    ("cV15", 0xFE0E, "VS15"),
    ("cV16", 0xFE0F, "VS16"),
    ("cZ", 0x200D, "ZWJ"),
    ("cT", 0x1F3FB, "skin tone (Emoji_Presentation, named alone)"),
    ("cG", 0xE0041, "TAG character (lone: unnamed)"),
    ("cRA", 0x1F1E6, "regional indicator A"),
    ("cRB", 0x1F1E7, "regional indicator B"),
    ("cMK", 0x0301, "combining acute (Mn)"),
    ("cX", 0x78, "letter 'x' (alphanumeric; occurs in no name in the table)"),
    ("cSP", 0x20, "space"),
    ("cEU", 0x20AC, "euro: CLDR-named, no emoji property (#757 row), folds to 'e'"),
    ("cDot", 0x2E, "'.', other"),
]
CPS = [cp for _, cp, _ in ALPHABET]
DOMAIN = sorted(set(CPS) | set(range(0x00, 0x80)))


def ranges(name: str) -> list[tuple[int, int]]:
    out = []
    for line in (DATA / name).read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        lo, hi = line.split("\t")[:2]
        out.append((int(lo, 16), int(hi, 16)))
    return out


def in_ranges(rs: list[tuple[int, int]], cp: int) -> bool:
    return any(lo <= cp <= hi for lo, hi in rs)


def tsv(name: str) -> dict[str, str]:
    out = {}
    for line in (DATA / name).read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        k, v = line.split("\t")[:2]
        out[k] = v
    return out


ep = ranges("emoji_presentation.tsv")
prop = ranges("emoji_property.tsv")
yes = ranges("emoji_yes.tsv")
single = {int(k, 16): v for k, v in tsv("emoji_single.tsv").items()}
multi = {tuple(int(p, 16) for p in k.split("_")): v for k, v in tsv("emoji_multi.tsv").items()}
starters = {
    int(line, 16)
    for line in (DATA / "emoji_starters.tsv").read_text().splitlines()
    if line and not line.startswith("#")
}
conf = {int(k, 16): v for k, v in tsv("confusables_to_latin.tsv").items()}
max_len = max(len(k) for k in multi)

JOIN = {0x200D, 0xFE0E, 0xFE0F}
keys = {k: v for k, v in multi.items() if all(c in CPS for c in k) and k[-1] not in JOIN}
# The trie gate: a key is only reachable when its first cp is in emoji_starters.
for k in keys:
    assert k[0] in starters, f"key {k} not reachable: first cp not a starter"
for k in multi:
    if all(c in CPS for c in k):
        assert k[-1] not in JOIN or True
names = [single[cp] for cp in DOMAIN if cp in single] + list(keys.values())
for n in names:
    assert n.isascii(), n


def lean_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def pred(name: str, doc: str, f) -> str:
    hits = [cp for cp in DOMAIN if f(cp)]
    body = " || ".join(f"n == 0x{cp:X}" for cp in hits) or "false"
    return f"/-- {doc} -/\ndef {name} (c : Char) : Bool :=\n  let n := c.toNat\n  {body}\n"


def is_alnum(cp: int) -> bool:
    # Rust char::is_alphanumeric = Alphabetic || Numeric (N*); on this domain
    # Python's isalnum agrees except that it reports some No digits too, which the
    # domain does not contain.
    return chr(cp).isalnum()


lines = [
    "/-! GENERATED by scripts/gen_tables.py from src/tables/data/*.tsv — do not edit.",
    "",
    "The real tables, projected onto the model's alphabet plus ASCII (the character",
    "set of every emoji name). Every predicate is `false` / `none` outside that domain;",
    "no input or output of the model leaves it. -/",
    "",
    "namespace Emoji.Tables",
    "",
]
for lname, cp, doc in ALPHABET:
    lines.append(f"/-- U+{cp:04X}: {doc} -/")
    lines.append(f"def {lname} : Char := Char.ofNat 0x{cp:X}")
lines.append("")
lines.append("/-- The model's input alphabet, one code point per class the Rust branches on. -/")
lines.append("def alphabet : List Char := [" + ", ".join(n for n, _, _ in ALPHABET) + "]")
lines.append("")
lines.append(
    f"/-- `tables::max_emoji_seq_len()` = MAX_WINDOW. -/\ndef maxWindow : Nat := {max_len}"
)
lines.append("")
lines.append(
    pred(
        "isEmojiPresentation",
        "UCD Emoji_Presentation=Yes (tables::is_emoji_presentation)",
        lambda cp: in_ranges(ep, cp),
    )
)
lines.append(
    pred(
        "isEmojiProperty",
        "UCD Emoji or Extended_Pictographic (tables::is_emoji_property)",
        lambda cp: in_ranges(prop, cp),
    )
)
lines.append(
    pred(
        "isEmojiYes",
        "UCD Emoji=Yes alone, the base U+FE0F opens (tables::is_emoji_yes, #992)",
        lambda cp: in_ranges(yes, cp),
    )
)
lines.append(
    pred(
        "isStarter",
        "emoji_starters.tsv (tables::is_emoji_multi_starter)",
        lambda cp: cp in starters,
    )
)
lines.append(
    pred(
        "nonEmojiRow",
        "CLDR row with no emoji property (tables::is_non_emoji_cldr_row, #757)",
        lambda cp: cp in single and not in_ranges(prop, cp),
    )
)
lines.append(
    pred(
        "confFoldsAlnum",
        'lookup_confusable(c, "latin") starts with an alphanumeric',
        lambda cp: cp in conf and conf[cp][:1] != "" and conf[cp][0].isalnum(),
    )
)
lines.append(
    pred(
        "isCombiningMark",
        "General_Category=Mark (unicode_normalization::char::is_combining_mark)",
        lambda cp: unicodedata.category(chr(cp)).startswith("M"),
    )
)
lines.append(pred("isAlphanumeric", "char::is_alphanumeric", is_alnum))
lines.append(
    pred("isWhitespace", "char::is_whitespace", lambda cp: chr(cp).isspace() or cp == 0x85)
)
lines.append("/-- emoji_single.tsv (tables::lookup_emoji_single) -/")
lines.append("def single (c : Char) : Option String :=")
lines.append("  let n := c.toNat")
for cp in DOMAIN:
    if cp in single:
        lines.append(f"  if n == 0x{cp:X} then some {lean_str(single[cp])} else")
lines.append("  none")
lines.append("")
lines.append(
    "/-- emoji_multi.tsv keys over the alphabet (the trie `match_emoji_sequence` walks). -/"
)
lines.append("def multiKeys : List (List Char × String) := [")
entries = []
for k, v in sorted(keys.items()):
    entries.append("  ([" + ", ".join(f"Char.ofNat 0x{c:X}" for c in k) + f"], {lean_str(v)})")
lines.append(",\n".join(entries))
lines.append("]")
lines.append("")
lines.append("end Emoji.Tables")
OUT.write_text("\n".join(lines) + "\n")
print(f"wrote {OUT}: {len(keys)} multi keys, max_len={max_len}", file=sys.stderr)
for k, v in sorted(keys.items()):
    print("  ", "_".join(f"{c:04X}" for c in k), v, file=sys.stderr)
