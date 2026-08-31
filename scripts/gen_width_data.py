#!/usr/bin/env python3
"""Generate the emoji/width data tables read by build.rs from the pinned UCD.

Emits three sorted-range TSVs under src/tables/data/:

  char_width.tsv          start;end;class   class in {Z,W,A}  (narrow = default)
  emoji_presentation.tsv  start;end         Emoji_Presentation code points
  emoji_property.tsv      start;end         Emoji OR Extended_Pictographic

The first two become binary-searchable range tables (no runtime data, no unsafe).
The third is a *build-time input only* (#757): build.rs intersects it with
emoji_single.tsv to derive the CLDR rows that name a code point carrying no emoji
property at all, and ships only that set.

East Asian Width and general category come from Python's ``unicodedata`` (the
pinned UCD — keep the generating Python's ``unidata_version`` in sync). The
derived properties not exposed by ``unicodedata`` (Default_Ignorable_Code_Point,
Grapheme_Extend, Emoji_Presentation) are read from the matching UCD release.

Usage:
    python scripts/gen_width_data.py            # uses UCD_VERSION below
"""

from __future__ import annotations

import sys
import unicodedata
import urllib.request
from pathlib import Path

UCD_VERSION = "15.1.0"
BASE = f"https://www.unicode.org/Public/{UCD_VERSION}/ucd"
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tables" / "data" if (ROOT / "tables").exists() else ROOT / "src" / "tables" / "data"
CACHE = Path("/tmp/translit_ucd_cache")
MAX_CP = 0x110000


def _fetch(name: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / name.replace("/", "_")
    if not dest.exists():
        url = f"{BASE}/{name}"
        print(f"  downloading {url}")
        with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 (pinned UCD URL)
            dest.write_bytes(resp.read())
    return dest.read_text(encoding="utf-8")


def _parse_property(text: str, want: str) -> set[int]:
    """Return the set of code points assigned property ``want`` in a UCD file.

    UCD property files have lines ``CP ; Prop`` or ``START..END ; Prop``.
    """
    out: set[int] = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ";" not in line:
            continue
        cps, _, prop = (p.strip() for p in line.partition(";"))
        if prop != want:
            continue
        if ".." in cps:
            lo, hi = cps.split("..")
            out.update(range(int(lo, 16), int(hi, 16) + 1))
        else:
            out.add(int(cps, 16))
    return out


def _coalesce(values: dict[int, str]) -> list[tuple[int, int, str]]:
    """Coalesce a {cp: class} map into sorted (start, end, class) ranges."""
    ranges: list[tuple[int, int, str]] = []
    for cp in sorted(values):
        cls = values[cp]
        if ranges and ranges[-1][1] == cp - 1 and ranges[-1][2] == cls:
            s, _, c = ranges[-1]
            ranges[-1] = (s, cp, c)
        else:
            ranges.append((cp, cp, cls))
    return ranges


def _coalesce_set(cps: set[int]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for cp in sorted(cps):
        if ranges and ranges[-1][1] == cp - 1:
            ranges[-1] = (ranges[-1][0], cp)
        else:
            ranges.append((cp, cp))
    return ranges


def main() -> int:
    if unicodedata.unidata_version != UCD_VERSION:
        print(
            f"WARNING: Python unicodedata is {unicodedata.unidata_version}, "
            f"expected {UCD_VERSION}. EAW/category will use the running version.",
            file=sys.stderr,
        )

    dcp = _fetch("DerivedCoreProperties.txt")
    emoji = _fetch("emoji/emoji-data.txt")
    default_ignorable = _parse_property(dcp, "Default_Ignorable_Code_Point")
    grapheme_extend = _parse_property(dcp, "Grapheme_Extend")
    emoji_presentation = _parse_property(emoji, "Emoji_Presentation")
    # #757: the union CLDR `annotationsDerived` overshoots. A row is a real emoji if it
    # carries either property; everything else is punctuation, currency or a math
    # operator that CLDR happens to annotate.
    #
    # Pinned to UCD_VERSION, the same release emoji_presentation is read from, so the
    # tree carries one emoji-data.txt version rather than two. 16.0.0 classifies the
    # 1,727 CLDR rows identically. 17.0.0 narrows Extended_Pictographic (3,537 -> 2,848
    # code points) and moves three of them out — U+266A eighth note, U+266D flat,
    # U+266F sharp — so a UCD bump here is a deliberate three-row behaviour change, not
    # a refresh.
    emoji_property = _parse_property(emoji, "Emoji") | _parse_property(
        emoji, "Extended_Pictographic"
    )

    width_class: dict[int, str] = {}
    for cp in range(MAX_CP):
        ch = chr(cp)
        cat = unicodedata.category(ch)
        # Zero-width (A4, A5): controls (Cc), format chars (Cf — ZWSP/ZWNJ/ZWJ,
        # bidi controls, prepended format), combining marks (Mn/Me),
        # default-ignorable / grapheme-extend (variation selectors etc.), and
        # conjoining Hangul Jungseong/Jongseong.
        if (
            cat in ("Cc", "Cf", "Mn", "Me")
            or cp in default_ignorable
            or cp in grapheme_extend
            or 0x1160 <= cp <= 0x11FF
        ):
            width_class[cp] = "Z"
            continue
        eaw = unicodedata.east_asian_width(ch)
        if eaw in ("W", "F"):
            width_class[cp] = "W"
        elif eaw == "A":
            width_class[cp] = "A"
        # else narrow — the default; not emitted

    DATA.mkdir(parents=True, exist_ok=True)
    header = f"# Generated by scripts/gen_width_data.py from UCD {UCD_VERSION}. Do not edit.\n"

    cw = DATA / "char_width.tsv"
    with cw.open("w", encoding="utf-8") as f:
        f.write(header)
        for s, e, c in _coalesce(width_class):
            f.write(f"{s:04X}\t{e:04X}\t{c}\n")
    print(f"  wrote {cw} ({len(width_class)} non-narrow code points)")

    for name, cps in (
        ("emoji_presentation", emoji_presentation),
        ("emoji_property", emoji_property),
    ):
        path = DATA / f"{name}.tsv"
        with path.open("w", encoding="utf-8") as f:
            f.write(header)
            for s, e in _coalesce_set(cps):
                f.write(f"{s:04X}\t{e:04X}\n")
        print(f"  wrote {path} ({len(cps)} code points)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
