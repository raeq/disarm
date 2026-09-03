#!/usr/bin/env python3
"""Generate confusable TSV files from Unicode TR39 confusables.txt.

Downloads the latest confusables.txt from unicode.org and produces TSV files
for each supported target script. Each TSV maps non-target characters to their
visual equivalents in the target script.

TR39 maps every confusable character to a single prototype, forming equivalence
classes. To generate mappings *to* a target script, we:
  1. Group all characters by their prototype (equivalence class)
  2. For each class, find the member(s) that belong to the target script
  3. Map all non-target members to the target-script member

Output files (written to src/tables/data/):
  confusables_to_latin.tsv    — non-Latin → Latin
  confusables_to_cyrillic.tsv — non-Cyrillic → Cyrillic

(Exact mapping counts vary with the Unicode version; the script prints the
per-file totals it wrote on completion.)

Usage:
    python scripts/gen_confusables.py
    python scripts/gen_confusables.py --input confusables.txt
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
import urllib.request
from collections import defaultdict
from pathlib import Path

CONFUSABLES_URL = "https://www.unicode.org/Public/security/latest/confusables.txt"
DATA_DIR = Path(__file__).resolve().parent.parent / "src" / "tables" / "data"
# Pinned, version-controlled source so regeneration is reproducible (see header).
BUNDLED_CONFUSABLES = Path(__file__).resolve().parent.parent / "data" / "confusables.txt"

# Digit-protection (#439) and case-folding read `unicodedata`, so the generator's
# output depends on the running Python's Unicode version. Under a table older than
# the data, a recently-assigned digit (e.g. the OUTLINED DIGITS U+1CCF0/U+1CCF1,
# or any non-ASCII digit unknown to that table) is not recognised as `Nd` and
# folds to its look-alike LETTER instead of its digit — silently corrupting the
# maps. The bundled confusables.txt is Unicode 17.0.0; require at least the floor
# below (which knows the currently-problematic digit blocks) and warn on any
# mismatch. Run under the newest Python available.
DATA_UNICODE_VERSION = "17.0.0"
# The floor is only the baseline the backfill is built against; completeness, not
# version, is what `_check_unicode_version` actually enforces.
MIN_UNICODE_VERSION = "15.1.0"
# Measured cross-script supplement folded with priority over TR39 (#342/#343).
BUNDLED_SUPPLEMENT = Path(__file__).resolve().parent.parent / "data" / "confusables_supplement.tsv"
# Measured-visual pairs admitted by multi-font SSIM agreement (#738); same row shape.
BUNDLED_VISION = Path(__file__).resolve().parent.parent / "data" / "confusables_vision.tsv"
BUNDLED_ATTESTED = Path(__file__).resolve().parent.parent / "data" / "confusables_attested.tsv"
BUNDLED_LGR = Path(__file__).resolve().parent.parent / "data" / "confusables_lgr.tsv"


# ---------------------------------------------------------------------------
# Codepoint classification
# ---------------------------------------------------------------------------


BUNDLED_UCD_BACKFILL = Path(__file__).resolve().parent.parent / "data" / "ucd_backfill.tsv"


def _decode_seq(field: str, cp: int) -> str:
    """A backfill decomposition field: `-` means "no decomposition", else code points."""
    if field == "-":
        return chr(cp)
    return "".join(chr(int(x, 16)) for x in field.split())


def _load_ucd_backfill() -> dict[int, tuple[str, int | None, str, str]]:
    """`codepoint -> (category, digit, nfkc, nfd)` for code points this Python may not know.

    `unicodedata` carries whatever table the running interpreter shipped. Under a table
    older than the data, a code point reads as `Cn`, no rule below can fire, and the
    output is wrong without being loud — a digit folds to a look-alike letter (#439), an
    uppercase source keeps TR39's lowercase prototype (#734).
    """
    out: dict[int, tuple[str, int | None, str, str]] = {}
    if not BUNDLED_UCD_BACKFILL.is_file():
        return out
    for line in BUNDLED_UCD_BACKFILL.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        cp_s, cat, dig, nfkc, nfd, *_ = line.split("\t")
        cp = int(cp_s, 16)
        out[cp] = (
            cat,
            None if dig == "-" else int(dig),
            _decode_seq(nfkc, cp),
            _decode_seq(nfd, cp),
        )
    return out


UCD_BACKFILL = _load_ucd_backfill()

# Every accessor below prefers `unicodedata` and reaches the backfill only on a `Cn`
# reading, so a newer interpreter is always authoritative and the file cannot mask it.


def ucd_category(cp: int) -> str:
    cat = unicodedata.category(chr(cp))
    if cat == "Cn" and cp in UCD_BACKFILL:
        return UCD_BACKFILL[cp][0]
    return cat


def ucd_digit(cp: int) -> int | None:
    if unicodedata.category(chr(cp)) == "Cn" and cp in UCD_BACKFILL:
        return UCD_BACKFILL[cp][1]
    return unicodedata.digit(chr(cp), None)


def ucd_nfkc(cp: int) -> str:
    if unicodedata.category(chr(cp)) == "Cn" and cp in UCD_BACKFILL:
        return UCD_BACKFILL[cp][2]
    return unicodedata.normalize("NFKC", chr(cp))


def ucd_nfd(cp: int) -> str:
    if unicodedata.category(chr(cp)) == "Cn" and cp in UCD_BACKFILL:
        return UCD_BACKFILL[cp][3]
    return unicodedata.normalize("NFD", chr(cp))


def is_combining_mark(cp: int) -> bool:
    """True if codepoint is a Unicode combining mark (category M*)."""
    return ucd_category(cp).startswith("M")


def is_latin(cp: int) -> bool:
    """True if codepoint is in a Latin block."""
    return (
        (0x0041 <= cp <= 0x005A)  # A-Z
        or (0x0061 <= cp <= 0x007A)  # a-z
        or (0x00C0 <= cp <= 0x024F)  # Latin Extended-A/B
        or (0x1E00 <= cp <= 0x1EFF)  # Latin Extended Additional
        or (0x2C60 <= cp <= 0x2C7F)  # Latin Extended-C
        or (0xA720 <= cp <= 0xA7FF)  # Latin Extended-D
        or (0xAB30 <= cp <= 0xAB6F)  # Latin Extended-E
    )


#: The three Latin *letters* in Latin-1 Supplement below U+00C0 (#590). The block
#: ranges below jump 0x007F → 0x00C0, so this stretch reads as non-Latin — but ª and º
#: are category Lo with Script=Latin, and µ is Ll. Admitting the whole 0x0080–0x00BF
#: range instead would pull in 58 rows targeting punctuation and symbols (·, °, ¶, ©),
#: whose non-ASCII targets #341 exists to keep out. Only the letters belong.
#:
#: `is_latin` (the SOURCE-side predicate) carries the identical gap. Measured: closing
#: it there changes nothing, because no upstream row uses ª/µ/º as a source. Left alone
#: rather than changed blind — if a future confusables.txt adds such a row, this note
#: is the pointer.
LATIN1_LETTERS = frozenset({0x00AA, 0x00B5, 0x00BA})  # ª µ º


def is_latin_or_common(cp: int) -> bool:
    """True if codepoint is Latin script, ASCII Common, or combining mark."""
    return (
        (0x0000 <= cp <= 0x007F)  # Basic Latin (ASCII)
        or cp in LATIN1_LETTERS  # ª µ º — Latin letters the block ranges skip (#590)
        or (0x00C0 <= cp <= 0x024F)  # Latin Extended-A/B
        or (0x1E00 <= cp <= 0x1EFF)  # Latin Extended Additional
        or (0x2C60 <= cp <= 0x2C7F)  # Latin Extended-C
        or (0xA720 <= cp <= 0xA7FF)  # Latin Extended-D
        or (0xAB30 <= cp <= 0xAB6F)  # Latin Extended-E
        or is_combining_mark(cp)  # Combining marks (stripped downstream)
    )


def strips_a_diacritic(cp: int) -> bool:
    """True if folding this source to a bare letter would remove a combining mark (#593).

    `normalize_confusables` promises accented Latin comes through intact — that is what
    makes it the right primitive when the text is a real name. `ţ` (U+0163) and `ț`
    (U+021B) both reach TR39's `ƫ` prototype, which `ASCII_FOLD` resolves to `t`, so
    recovering them would silently strip a cedilla and a comma-below. `ț` is ordinary
    Romanian orthography. `strip_obfuscation` is the tool for that job (#564).

    Detected from the source's own canonical decomposition rather than a codepoint list,
    so a future confusables.txt cannot smuggle a new accented source past it.
    """
    return any(ucd_category(ord(ch)).startswith("M") for ch in ucd_nfd(cp))


def is_basic_ascii_letter(cp: int) -> bool:
    """True if codepoint is a basic ASCII letter A-Z / a-z (already canonical)."""
    return (0x0041 <= cp <= 0x005A) or (0x0061 <= cp <= 0x007A)


def is_basic_ascii_graphic(cp: int) -> bool:
    """True if codepoint is a printable, non-whitespace ASCII character (#558).

    Widens :func:`is_basic_ascii_letter` to digits, punctuation, and symbols. A Latin
    letter that impersonates an ASCII *digit* or *punctuation mark* — EZH `\u01b7` for `3`,
    OU `\u0222` for `8`, SALTILLO `\ua78c` for an apostrophe — is the same class of
    homoglyph as one impersonating a letter, and belongs in the to-Latin table for the
    same reason.

    Whitespace is deliberately excluded. TR39 folds the whole Zs/Zl/Zp family to a
    space, but `collapse_whitespace` already owns that (it works from an explicit
    core-defined set, #433), so duplicating those rows here would put a second,
    divergent copy of the whitespace policy in the confusables table.
    """
    c = chr(cp)
    return cp < 0x80 and c.isprintable() and not c.isspace()


def is_cyrillic(cp: int) -> bool:
    """True if codepoint is in a Cyrillic block."""
    return (
        (0x0400 <= cp <= 0x04FF)  # Cyrillic
        or (0x0500 <= cp <= 0x052F)  # Cyrillic Supplement
        or (0x2DE0 <= cp <= 0x2DFF)  # Cyrillic Extended-A
        or (0xA640 <= cp <= 0xA69F)  # Cyrillic Extended-B
    )


# ---------------------------------------------------------------------------
# Custom Latin overrides
# ---------------------------------------------------------------------------

# Safe, justified mappings that TR39 does not provide directly. Each entry must
# be a non-letter look-alike whose folding cannot corrupt legitimate prose.
#
# U+2502 BOX DRAWINGS LIGHT VERTICAL → l:
#   TR39 treats U+2502 as a terminal *prototype* (FE31/FF5C/2503 fold *onto* it)
#   and never folds it onto a Latin letter, so the generator drops it from the
#   Latin table. But it is the NFKC decomposition of U+FFE8 (HALFWIDTH FORMS
#   LIGHT VERTICAL), and the confusable-bearing pipelines (e.g. strip_obfuscation)
#   run NFKC *before* confusables — so the halfwidth vertical U+FFE8 reaches the
#   confusable step as U+2502 and previously survived as non-ASCII residue. A
#   box-drawing glyph is not legitimate prose, so folding the vertical bar onto
#   'l' (matching the visual shape and the existing TR39 FFE8→l mapping) is safe.
#   This closes the residue for U+FFE8 (whose NFKC form is U+2502) and for a bare
#   U+2502 input. Note: U+2503 (heavy vertical) and U+FE31 do NOT NFKC-decompose
#   to U+2502, so they are out of scope here. See issue #245.
CUSTOM_LATIN_OVERRIDES: dict[int, str] = {
    0x2502: "l",  # │ BOX DRAWINGS LIGHT VERTICAL
}


# ---------------------------------------------------------------------------
# Basic-ASCII fold for non-ASCII Latin-extended prototypes (#341)
# ---------------------------------------------------------------------------

# TR39 folds ~140 sources onto a non-ASCII *Latin-extended* prototype (ĸ, ꞓ, ß,
# …) instead of the basic ASCII letter they visually represent. That leaves
# non-ASCII residue in slug/identifier pipelines and breaks Latin↔non-Latin
# collision: a Greek κ folds to ĸ (U+0138), so it does NOT collide with ASCII k.
# This maps each such *terminal prototype glyph* to its basic-ASCII representative
# (lowercase base — case is reconciled to the source via fix_case_mismatch, so an
# uppercase source still yields an uppercase letter). Applied to the latin output
# with priority, after the generated mappings.
#
# Glyphs with no clear, non-controversial ASCII fold are deliberately LEFT as
# non-ASCII residue (#341 "genuinely-non-ASCII, documented, not silently
# dropped"): ɂ U+0242 (glottal stop), Ƕ U+01F6 (hwair), ǂ U+01C2 (alveolar
# click), ÷ U+00F7 (division sign), and U+A7CE.
ASCII_FOLD: dict[str, str] = {
    # Clear single-letter representatives.
    # ꞓ/Ꞓ (C WITH BAR) is TR39's *skeleton* for the open-e / epsilon / Ukrainian-ie
    # class (ε, ɛ, є, ⲉ, the math epsilons, Deseret long-e, …) — its members are all
    # 'e'-shaped, not 'c'-shaped — so the class folds to e, the #336 decision.
    "ꞓ": "e",
    "Ꞓ": "e",  # LATIN (CAPITAL) LETTER C WITH BAR — epsilon/open-e class (#336)
    "ª": "a",  # FEMININE ORDINAL INDICATOR — NFKC is 'a' (#590)
    "º": "o",  # MASCULINE ORDINAL INDICATOR — NFKC is 'o' (#590)
    "ĸ": "k",  # LATIN SMALL LETTER KRA
    "ß": "b",  # LATIN SMALL LETTER SHARP S (#336)
    "ǝ": "e",
    "Ǝ": "e",
    "Ə": "e",  # turned/reversed E, schwa
    "ȷ": "j",  # LATIN SMALL LETTER DOTLESS J
    "Ⱬ": "z",
    "ⱬ": "z",  # LATIN (CAPITAL) LETTER Z WITH DESCENDER
    "Ⱶ": "h",
    "ⱶ": "h",  # LATIN (CAPITAL) LETTER HALF H
    "ꜿ": "c",
    "Ꜿ": "c",  # LATIN (CAPITAL) LETTER REVERSED C WITH DOT
    "ꟻ": "f",  # LATIN EPIGRAPHIC LETTER REVERSED F
    "Ꞇ": "t",  # LATIN CAPITAL LETTER INSULAR T
    "ƫ": "t",  # LATIN SMALL LETTER T WITH PALATAL HOOK
    "ɋ": "q",  # LATIN SMALL LETTER Q WITH HOOK TAIL
    "Þ": "p",  # LATIN CAPITAL LETTER THORN (matches the existing þ→p)
    # Ambiguous prototypes — canonical chosen by visual shape (#341, approved).
    "Ʌ": "a",  # LATIN CAPITAL LETTER TURNED V
    "ẟ": "d",  # LATIN SMALL LETTER DELTA
    "Ɛ": "e",  # LATIN CAPITAL LETTER OPEN E
    "ȝ": "z",  # LATIN SMALL LETTER YOGH
    "Ɔ": "o",  # LATIN CAPITAL LETTER OPEN O
    "Ɐ": "a",  # LATIN CAPITAL LETTER TURNED A
    "ƨ": "s",  # LATIN SMALL LETTER TONE TWO
    "ƅ": "b",  # LATIN SMALL LETTER TONE SIX
    "Ʊ": "u",  # LATIN CAPITAL LETTER UPSILON
    # esh is TR39's skeleton for the sigma / n-ary-summation family (Σ, ∑, ⅀, the
    # math sigmas, Tifinagh ⵉ). Folds to s — sigma is phonetically 's' and already
    # transliterates to S — neutralizing the Σ→S spoof that previously survived as
    # the non-ASCII Ʃ. Reverses the pre-#341 "neutralize ≠ ASCII-fold" decision
    # (#245); #341 makes ASCII the contract. (Σ folds to S via the Lu case rule.)
    "Ʃ": "s",  # LATIN CAPITAL LETTER ESH — sigma/summation class (#341)
    "Ɒ": "a",  # LATIN CAPITAL LETTER TURNED ALPHA
    # #801: three more prototypes in the same "chosen by visual shape" class as the
    # block above. Each is corroborated by the target the *capital* of the same
    # upstream class already carries here, so the choice is read off the table rather
    # than off my eye: `\u041c` М → `M` fixes `\u028d` ʍ → `m`, `\u0417` З → `3` fixes
    # `\u025c` ɜ → `3`, and `\u2c9c` Ⲝ → `3` fixes `\u0293` ʓ → `3`. Without them the
    # lowercase halves (`\u043c` м, `\u0437` з, `\u2c9d` ⲝ) stay unfolded while their
    # capitals fold, which is the asymmetry #801 is about.
    "ʍ": "m",  # LATIN SMALL LETTER TURNED W — turned-letter shape, as Ʌ→a above
    "ɜ": "3",  # LATIN SMALL LETTER REVERSED OPEN E
    "ʓ": "3",  # LATIN SMALL LETTER EZH WITH CURL
}


def _small_capital_folds() -> dict[str, str]:
    """`LATIN LETTER SMALL CAPITAL X` → `x`, derived from the character's UCD name.

    TR39's prototype for several Cyrillic homoglyph classes is a Latin **small
    capital**, not the ASCII letter: `\u0442` т maps to `\u1d1b` ᴛ, `\u043d` н to
    `\u029c` ʜ. Those prototypes are Latin, so `filter_direct` keeps them, and then
    the ASCII-only table contract drops the row — which is how the classic Cyrillic
    homoglyphs came to have a mapping on the capital and none on the lowercase (#801).

    Derived from `Name`, not enumerated: a future `confusables.txt` that routes a new
    class through a small capital is covered without an edit here. The shape is a
    letter-for-letter identity — `\u1d1b` ᴛ *is* a T — so there is no visual judgment
    to make, unlike the entries above.
    """
    out: dict[str, str] = {}
    # `unicodedata.name` directly rather than a backfilled accessor: every small
    # capital has been assigned since Unicode 4.0, so no interpreter this generator
    # runs on reads one as `Cn`, and `UCD_BACKFILL` carries no names to fall back to.
    for cp in range(0x110000):
        name = unicodedata.name(chr(cp), "")
        if not name.startswith("LATIN LETTER SMALL CAPITAL "):
            continue
        rest = name[len("LATIN LETTER SMALL CAPITAL ") :]
        if len(rest) == 1 and "A" <= rest <= "Z":
            out[chr(cp)] = rest.lower()
    return out


def _enclosed_letter_folds() -> dict[str, str]:
    """`<prefix> LATIN {CAPITAL,SMALL} LETTER X` -> `x`, derived from the UCD name (#815).

    U+1F150 and U+1F170 fold on no surface. Their *positive* counterparts `\u24d0` and
    `\u1f130` fold via NFKC, which decomposes those and does not decompose these — two
    neighbouring blocks, opposite outcomes, and nothing said so. A generator offering
    "circled" and "circled (negative)" side by side gets one neutralised and one through
    untouched.

    Same shape as `_small_capital_folds`: the name states the letter, so there is no
    visual judgment to make. Two families matching the pattern are deliberately excluded,
    because both are already handled correctly and folding them would be wrong:

    * **Tags** (U+E0041 and 51 more) are stripped as a smuggling class (#413), not folded.
      `canonicalize` already returns `ab` for a tag between two letters, and
      `has_anomalies` fires on it.
    * **Combining letters** (`\u0363` and 22 more) are category `Mn` — diacritics written
      above a base in medieval manuscripts, not letters standing in for one. They are
      `strip_accents`' business.

    The filter is therefore on category: a letter or a symbol, never a mark and never a
    format character.
    """
    out: dict[str, str] = {}
    for cp in range(0x110000):
        ch = chr(cp)
        # `.+` rather than `.*`: a bare `LATIN CAPITAL LETTER A` is ASCII `A` itself, and
        # matching it would emit 52 identity rows.
        match = re.fullmatch(r".+\bLATIN (CAPITAL|SMALL) LETTER ([A-Z])", unicodedata.name(ch, ""))
        if not match or ch.isascii():
            continue
        if ucd_category(cp)[0] not in ("L", "S"):
            continue
        # The whole point of the set: NFKC already decomposes the positive forms, and
        # a row for one of those would be redundant with a step that runs before the
        # fold. What is left is what NFKC leaves alone — 54 code points, all of them
        # negative, crossed or otherwise unmapped by the compatibility data.
        if ucd_nfkc(cp) != ch:
            continue
        # Case comes from the NAME, not from `fix_case_mismatch`. These are category `So`,
        # so the case reconciler cannot tell a capital from a small letter and left every
        # row lowercase — which made U+1F170 fold to `a` while its positive counterpart
        # U+1F130 reaches `A` through NFKC. Two spellings of the same style disagreeing is
        # the asymmetry this set exists to remove, so it must not be reintroduced here.
        letter = match.group(2)
        out[ch] = letter if match.group(1) == "CAPITAL" else letter.lower()
    return out


def _close_under_case(fold: dict[str, str]) -> dict[str, str]:
    """Give every entry's case pair the same ASCII letter (#801).

    `ASCII_FOLD` was itself case-asymmetric in fourteen of thirty-two entries — it
    carried `\u0186` Ɔ but not `\u0254` ɔ, `\u01a8` ƨ but not `\u01a7` Ƨ. That is the
    same defect as the one this closure exists to fix, one layer up: the capital
    resolved to ASCII and the lowercase it case-folds to did not, so a case fold
    converged both spellings onto the unmapped side.

    Derived, and deliberately so — the pair inherits the letter its partner was
    already given, so closing the set introduces no new visual judgment. An explicit
    entry always wins; this only fills gaps.
    """
    out = dict(fold)
    for source, target in fold.items():
        for pair in (source.lower(), source.upper()):
            if len(pair) == 1 and pair != source:
                out.setdefault(pair, target)
    return out


ASCII_FOLD = _close_under_case({**_enclosed_letter_folds(), **_small_capital_folds(), **ASCII_FOLD})


# ---------------------------------------------------------------------------
# Target script definitions
# ---------------------------------------------------------------------------


def is_arabic(cp: int) -> bool:
    """True if codepoint is in an Arabic block (#792).

    Includes the presentation-form blocks. They are removed by the NFKC step every preset
    runs before the fold, so a row keyed on one is unreachable through a preset — but
    `normalize_confusables` is callable directly, and the caller who does that is exactly
    the one who has not normalized first.
    """
    return (
        (0x0600 <= cp <= 0x06FF)  # Arabic
        or (0x0750 <= cp <= 0x077F)  # Arabic Supplement
        or (0x08A0 <= cp <= 0x08FF)  # Arabic Extended-A
        or (0xFB50 <= cp <= 0xFDFF)  # Arabic Presentation Forms-A
        or (0xFE70 <= cp <= 0xFEFF)  # Arabic Presentation Forms-B
    )


def is_hebrew(cp: int) -> bool:
    """True if codepoint is in a Hebrew block (#792)."""
    return (0x0590 <= cp <= 0x05FF) or (0xFB1D <= cp <= 0xFB4F)


SCRIPTS = {
    "latin": {
        "is_target": is_latin,
        "is_target_or_common": is_latin_or_common,
    },
    "cyrillic": {
        "is_target": is_cyrillic,
        "is_target_or_common": lambda cp: is_cyrillic(cp) or is_combining_mark(cp),
    },
    # #792: the RTL targets. 948 of the 1,007 strong-RTL sources in TR39 are unmapped
    # under both existing targets (#791), because generation drops a class entirely when
    # no member belongs to the target script — so a class whose members are all Arabic
    # survives into neither table. These give those classes somewhere to land.
    #
    # They do NOT reach an intra-Arabic pair such as `\u06a9` / `\u0643`: both members are
    # already in the target script, which `filter_direct` skips and `filter_via_classes`
    # has nothing to map from. That is #848, and it needs the generator to stop discarding
    # same-script classes rather than a new target.
    "arabic": {
        "is_target": is_arabic,
        "is_target_or_common": lambda cp: is_arabic(cp) or is_combining_mark(cp),
    },
    "hebrew": {
        "is_target": is_hebrew,
        "is_target_or_common": lambda cp: is_hebrew(cp) or is_combining_mark(cp),
    },
}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_confusables(text: str) -> list[tuple[int, list[int]]]:
    """Parse confusables.txt into (source_cp, target_cps) pairs."""
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(";")
        if len(parts) < 3:
            continue
        source_cp = int(parts[0].strip(), 16)
        target_cps = [int(h, 16) for h in parts[1].strip().split()]
        entries.append((source_cp, target_cps))
    return entries


def build_equivalence_classes(
    entries: list[tuple[int, list[int]]],
) -> dict[tuple[int, ...], set[int]]:
    """Build equivalence classes from TR39 confusables.

    TR39 maps each source character to a prototype. Characters sharing the
    same prototype form an equivalence class. We group all sources by their
    prototype and also include the prototype itself.

    Returns: {prototype_key: {member_cp, ...}}
    """
    classes: dict[tuple[int, ...], set[int]] = defaultdict(set)
    for source_cp, target_cps in entries:
        key = tuple(target_cps)
        classes[key].add(source_cp)
        # If the prototype is a single codepoint, it's also a class member
        if len(target_cps) == 1:
            classes[key].add(target_cps[0])
    return dict(classes)


def load_supplement(path: Path) -> dict[str, dict[int, str]]:
    """Parse confusables_supplement.tsv into per-target override maps (#342/#343).

    Returns ``{"latin": {source_cp: target_str, ...}, "cyrillic": {...}}``. A
    blank or ``-`` cell means "no override for that target" (keep the generated
    value). These overrides are applied with priority over the TR39-derived
    mappings, so they can both ADD a missing fold and RE-POINT an existing one.
    """
    overrides: dict[str, dict[int, str]] = {"latin": {}, "cyrillic": {}}
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.rstrip("\n")
        if not line or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        # Fail fast: this file feeds security-critical confusable mappings, so a
        # malformed row must error rather than be silently dropped.
        if len(parts) < 3:
            raise ValueError(
                f"{path.name}:{lineno}: malformed supplement row (need >=3 "
                f"tab-separated columns: source, latin, cyrillic): {raw!r}"
            )
        cp = int(parts[0].strip(), 16)
        for target, cell in (("latin", parts[1]), ("cyrillic", parts[2])):
            value = cell.strip()
            if value and value != "-":
                overrides[target][cp] = value
    return overrides


def load_lgr(path: Path) -> dict[int, str]:
    """Parse confusables_lgr.tsv into a to-Latin override map (#831).

    A third override file beside the supplement (#342) and the attested rows (#597),
    because the admission criterion is a third thing: the pair is a BLOCKED variant in
    ICANN's Latin second-level LGR whose variant comment reads "Glyphs either homoglyph
    or nearly identical" — one registry's published visual judgement about SAME-SCRIPT
    Latin pairs.

    To-Latin only. These are Latin-to-Latin pairs; there is no Cyrillic reading of them,
    and inventing one would be a different claim than the LGR makes.

    Columns are source_hex, target, target_rule. The third is validated and not consumed,
    for the reason `load_attested` gives about its own provenance columns: a row that
    cannot say how its target was chosen has no business in a security-critical table.
    """
    overrides: dict[int, str] = {}
    valid_rules = {"ascii", "lowest"}
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].rstrip() if not raw.lstrip().startswith("#") else ""
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            raise ValueError(
                f"{path.name}:{lineno}: malformed LGR row (need >=3 tab-separated "
                f"columns: source_hex, target, target_rule): {raw!r}"
            )
        # Every column stripped, including the target. `load_supplement` and
        # `load_attested` strip theirs a line later; this one did not, so a trailing
        # space in the TSV would have become part of the fold target (#870 review).
        # Unlike `confusables_to_latin.tsv`, where a trailing space can be the whole
        # value (`U+30FB` folds to one), an LGR target is always a Latin letter.
        source_hex, target, rule = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if rule not in valid_rules:
            raise ValueError(
                f"{path.name}:{lineno}: target_rule must be one of {sorted(valid_rules)}, "
                f"got {rule!r}"
            )
        source = int(source_hex, 16)
        if not target:
            raise ValueError(f"{path.name}:{lineno}: empty target")
        overrides[source] = target
    return overrides


def load_attested(path: Path) -> dict[str, dict[int, str]]:
    """Parse confusables_attested.tsv into per-target override maps (#597).

    Same shape as :func:`load_supplement` and merged with it, but a separate FILE
    because the admission criteria differ: the supplement is cross-script pairs from a
    measured confusable-vision dataset above a danger threshold, while these are
    codepoints attested in real attacker text (the BitAbuse BitCore subset) that TR39
    does not list as sources at all. 18 of them are Latin folding to Latin.

    Columns are source, latin, cyrillic, tier, occ, note. The extra three are provenance
    and are validated, not consumed: a row that cannot say which tier it belongs to has
    no business in a security-critical table.
    """
    overrides: dict[str, dict[int, str]] = {"latin": {}, "cyrillic": {}}
    valid_tiers = {"1", "2a", "2b"}
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.rstrip("\n")
        if not line or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            raise ValueError(
                f"{path.name}:{lineno}: malformed attested row (need >=5 tab-separated "
                f"columns: source, latin, cyrillic, tier, occ): {raw!r}"
            )
        cp = int(parts[0].strip(), 16)
        tier = parts[3].strip()
        if tier not in valid_tiers:
            raise ValueError(
                f"{path.name}:{lineno}: tier {tier!r} is not one of {sorted(valid_tiers)} "
                f"— tier 1 is optical, 2a positional, 2b convention (#597)"
            )
        # `occ` is provenance, not input to the fold, but a row that cannot state its
        # attestation count has not been mined — it has been guessed. Parse it so a
        # malformed one fails here rather than shipping unnoticed.
        occ = parts[4].strip()
        try:
            if int(occ) < 0:
                raise ValueError
        except ValueError:
            raise ValueError(
                f"{path.name}:{lineno}: occ {occ!r} is not a non-negative integer — it is "
                f"the BitCore occurrence count that justifies the row (#597)"
            ) from None
        for target, cell in (("latin", parts[1]), ("cyrillic", parts[2])):
            value = cell.strip()
            if value and value != "-":
                overrides[target][cp] = value
    return overrides


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def strip_combining(target_cps: list[int]) -> list[int]:
    """Remove combining marks from target codepoints."""
    return [cp for cp in target_cps if not is_combining_mark(cp)]


def uppercase_nfkc(cp: int) -> str | None:
    """The source's NFKC form, if that form is a run of ASCII uppercase letters (#734).

    `None` for everything else, including mixed-case decompositions such as `U+3392`
    SQUARE MHZ (`MHz`), which must not be rewritten.
    """
    nfkc = ucd_nfkc(cp)
    if nfkc and nfkc.isascii() and nfkc.isalpha() and nfkc.isupper():
        return nfkc
    return None


def is_uppercase_source(cp: int) -> bool:
    """True if *cp* is an uppercase letter for folding purposes (#734).

    `Lu` covers almost all of it, and used to be the whole test. Two sources in the
    capital-I family are not `Lu` — `U+2160` ROMAN NUMERAL ONE is `Nl`, `U+1CCDE`
    OUTLINED LATIN CAPITAL LETTER I is `So` — so neither was ever reconciled and both
    kept TR39's lowercase `l`. The table then contradicted itself inside one block:
    `Ⅷ` folded to `Vlll`, and the outlined alphabet read `…GHlJK…`.

    The second clause is "NFKC-decomposes to a single uppercase ASCII letter", which is
    what separates those two from the only other candidates. Of the 21 sources whose
    name contains CAPITAL, whose category is not `Lu`, and whose target is a lowercase
    letter, 20 are the small capitals (`ɢ ɪ ɴ ʀ ʏ …`) — every one `Ll`, with no NFKC
    decomposition at all, correctly keeping a lowercase target. The 21st is `U+1CCDE`.

    This reads `unicodedata`, so it is subject to the version floor enforced by
    `_check_unicode_version`: `U+1CCDE` was assigned in Unicode 16.0, and under an older
    table it is `Cn` with no decomposition and this returns False for it.
    """
    if ucd_category(cp) == "Lu":
        return True
    nfkc = ucd_nfkc(cp)
    return len(nfkc) == 1 and nfkc.isascii() and nfkc.isupper()


def fix_case_mismatch(source_cp: int, target_str: str) -> str:
    """Ensure case consistency between source and target.

    If source is uppercase and target is lowercase (or vice versa),
    adjust the target to match. Special case: the {I, l, 1} class
    where uppercase should map to I, not L.
    """
    if not target_str.isalpha():
        return target_str

    # Multi-character targets (#734). TR39 maps `Ⅷ` to `V l l l` and records its own
    # reasoning as `# →VIII→`: the right letters, reached through the lowercase `l`
    # prototype. The old guard returned early on any target longer than one character,
    # so the nine multi-character Roman numerals kept that lowercase spelling and
    # `normalize_confusables("Ⅷ")` was `Vlll`.
    #
    # Reconcile against the source's NFKC form when that form is a same-length run of
    # ASCII uppercase letters. Measured over both shipped tables, that is exactly nine
    # rows — U+2161..U+2168, U+216A, U+216B — and nothing else. The `isascii` test keeps
    # this to the Latin table: the Cyrillic targets are Cyrillic letters and are handled
    # by the single-character path below, which must stay non-ASCII-capable or the
    # palochka rows stop being reconciled.
    if len(target_str) > 1:
        nfkc = uppercase_nfkc(source_cp)
        if nfkc is not None and len(nfkc) == len(target_str) and target_str.isascii():
            return nfkc
        return target_str

    source_cat = ucd_category(source_cp)
    target_cat = ucd_category(ord(target_str))
    if is_uppercase_source(source_cp) and target_cat == "Ll":
        if target_str == "l":
            return "I"
        return target_str.upper()
    if source_cat == "Ll" and target_cat == "Lu":
        return target_str.lower()
    return target_str


def enforce_digit_target(source_cp: int, target_str: str) -> str | None:
    """A digit source must never fold to a letter (#439).

    TR39 routes OUTLINED DIGIT ZERO/ONE (U+1CCF0/U+1CCF1) through the visual chain
    0→O / 1→l, so their prototype is the *letter* O / l — but a digit must fold to
    its canonical ASCII digit, exactly as the rest of that block does
    (1CCF2–1CCF9 → 2–9). For any decimal-digit (`Nd`) source whose computed target
    is not already a single ASCII digit, remap it to the source's own digit value;
    return ``None`` to drop the row if that value is somehow indeterminate.
    """
    if ucd_category(source_cp) != "Nd":
        return target_str
    if len(target_str) == 1 and target_str.isascii() and target_str.isdigit():
        return target_str
    d = ucd_digit(source_cp)
    return str(d) if d is not None else None


def filter_direct(
    entries: list[tuple[int, list[int]]],
    script_name: str,
) -> list[tuple[int, str]]:
    """Direct filtering: keep entries where the TR39 target is in the target script.

    This is the original approach — works well for Latin (where the prototype
    IS the Latin character) but misses cases where the target script member
    is a source, not a prototype.
    """
    script = SCRIPTS[script_name]
    is_target = script["is_target"]
    is_target_or_common = script["is_target_or_common"]

    result = []
    for source_cp, target_cps in entries:
        # Skip same-script → same-script
        if is_target(source_cp):
            continue
        # Skip digits as sources
        if 0x0030 <= source_cp <= 0x0039:
            continue
        cleaned_cps = strip_combining(target_cps)
        target_str = "".join(chr(cp) for cp in cleaned_cps)
        # #801: resolve the prototype through `ASCII_FOLD` BEFORE the script gate, not
        # after. Membership in that map is itself the assertion that the prototype is a
        # Latin letter with an ASCII representative, so gating it on `is_target_or_common`
        # — a list of block ranges — rejects rows the map already answers for. `\u1d1b` ᴛ
        # sits in Phonetic Extensions, which no range on that list covers, so `\u0442` т →
        # `\u1d1b` ᴛ was dropped while `\u0422` Т → `T` was kept: the capital folded to
        # Latin and the lowercase it case-folds to did not.
        target_str = ASCII_FOLD.get(target_str, target_str)
        if not all(is_target_or_common(ord(ch)) for ch in target_str):
            continue
        if not target_str.strip():
            continue
        # #593: ASCII-fold before reconciling case, for the same reason as
        # `filter_latin_homoglyphs`. `fix_case_mismatch` uppercases, and `ß`.upper() is
        # the two-character `SS`, which then escapes the `ASCII_FOLD` pass in
        # `generate_mappings` because that only fires on a single character. That is how
        # Cherokee YE (U+13F0), a B-shape, came out as `SS` in a table about *visual*
        # confusability. Blast radius measured: this row and no other.
        target_str = fix_case_mismatch(source_cp, target_str)
        guarded = enforce_digit_target(source_cp, target_str)
        if guarded is None:
            continue
        result.append((source_cp, guarded))
    return result


def filter_via_classes(
    entries: list[tuple[int, list[int]]],
    script_name: str,
) -> list[tuple[int, str]]:
    """Equivalence-class filtering: for each class, map non-target members
    to the target-script member.

    This catches cases like Latin A → Cyrillic А, where TR39 maps
    Cyrillic А → Latin A (prototype). We invert: Latin A → Cyrillic А.
    """
    script = SCRIPTS[script_name]
    is_target = script["is_target"]
    classes = build_equivalence_classes(entries)

    result_map: dict[int, str] = {}

    for _proto_key, members in classes.items():
        # Find single-codepoint target-script members in this class
        target_members_upper: list[int] = []
        target_members_lower: list[int] = []
        target_members_other: list[int] = []

        for m in members:
            if is_target(m):
                # Never accept a combining mark as a target: it is invisible on
                # its own and folding a visible source onto one would itself be
                # an obfuscation vector. Skipping drops classes whose only
                # target-script member is a combining mark.
                if is_combining_mark(m):
                    continue
                cat = ucd_category(m)
                if cat == "Lu":
                    target_members_upper.append(m)
                elif cat == "Ll":
                    target_members_lower.append(m)
                else:
                    target_members_other.append(m)

        if not (target_members_upper or target_members_lower or target_members_other):
            continue

        # Prefer lowest codepoint (basic block) over extended/supplement
        target_members_upper.sort()
        target_members_lower.sort()
        target_members_other.sort()

        # For each non-target member, map to the appropriate target member
        for m in members:
            if is_target(m):
                continue  # Don't map target→target
            # Skip digits
            if 0x0030 <= m <= 0x0039:
                continue

            source_cat = ucd_category(m)

            # Pick the target member with matching case
            target_cp = None
            if source_cat == "Lu" and target_members_upper:
                target_cp = target_members_upper[0]
            elif source_cat == "Ll" and target_members_lower:
                target_cp = target_members_lower[0]
            elif target_members_lower:
                target_cp = target_members_lower[0]
            elif target_members_upper:
                target_cp = target_members_upper[0]
            elif target_members_other:
                target_cp = target_members_other[0]

            if target_cp is not None:
                target_str = chr(target_cp)
                target_str = fix_case_mismatch(m, target_str)
                guarded = enforce_digit_target(m, target_str)
                # Only keep if not already mapped (direct takes priority)
                if guarded is not None and m not in result_map:
                    result_map[m] = guarded

    return list(result_map.items())


def filter_latin_homoglyphs(
    entries: list[tuple[int, list[int]]],
) -> list[tuple[int, str]]:
    """Latin-script characters that are confusable with a *basic ASCII* character.

    ``filter_direct`` skips every Latin-script source for the Latin target
    (``is_target(source_cp)`` is true), which drops genuine homoglyphs of ASCII
    characters that happen to live in Latin Extended blocks — e.g. þ→p, ſ→f, ı→i,
    ƒ→f, Ɩ→l. These must fold for confusable normalization. This pass recovers
    exactly that case: a non-ASCII Latin-script source whose TR39 prototype is a
    single basic ASCII graphic character.

    #558: the prototype test was ``is_basic_ascii_letter``, which silently dropped
    every Latin-script letter whose prototype is an ASCII *digit* or *punctuation
    mark* — Ʒ→3, Ȣ→8, Ꝯ→9, ǃ→!, Ɂ→?, ꝸ→&, ꞉→:, ꞌ→' and 7 more. Nothing distinguished
    those from þ→p except the category of the target, so they were a table gap rather
    than a policy decision; the predicate is now ``is_basic_ascii_graphic``. Whitespace
    stays out (see that function).

    Note this is the *letter-impersonates-a-digit* direction. The reverse — a digit
    source folding to a look-alike letter — is guarded separately by
    :func:`enforce_digit_target` (#439) and is a different question.
    """
    result: dict[int, str] = {}
    for source_cp, target_cps in entries:
        if not is_latin(source_cp):
            continue  # cross-script sources are handled by filter_direct
        if is_basic_ascii_letter(source_cp):
            continue  # already canonical
        if 0x0030 <= source_cp <= 0x0039:
            continue  # digits
        cleaned = strip_combining(target_cps)
        if len(cleaned) != 1:
            continue  # prototype must be a single character
        prototype = chr(cleaned[0])
        # #593: accept a prototype `ASCII_FOLD` can resolve, not only one that is already
        # basic ASCII. `ASCII_FOLD` runs later, in `generate_mappings`, so gating on raw
        # ASCII here discarded rows before that table was ever consulted — Ꟛ→Ʌ among them,
        # which left the Latin lambdas not colliding with the Greek one TR39 says they are
        # confusable with.
        already_ascii = is_basic_ascii_graphic(cleaned[0])
        if not already_ascii:
            if prototype not in ASCII_FOLD:
                continue  # no ASCII representative, and none derivable
            if strips_a_diacritic(source_cp):
                continue  # folding would remove a mark; accented Latin stays (#593)
        # The diacritic guard applies to the rows this pass newly recovers, NOT to the
        # ones it always handled. `Ç`/`ç`/`Ǿ` reach a bare ASCII prototype only because
        # `strip_combining` removed the mark from TR39's target, and they have folded to
        # `C`/`c`/`O` since long before #593 — #586's fixed-point loop is built on
        # `Ç → C`. Widening the guard over them would be a silent regression, not a fix.
        # Fold to ASCII *before* reconciling case. `fix_case_mismatch` uppercases, and a
        # single-char fold would otherwise be produced from a glyph whose own case mapping
        # is richer — that is how Cherokee YE (a B-shape) came out as `SS` before #593.
        #
        # But a genuine multi-character case mapping wins, and `ẞ` is why. `ß`.upper() is
        # the two-character `SS`, which is correct German: STRAẞE and STRASSE are the same
        # word, so folding to `SS` makes them collide — the whole point of a skeleton.
        # Folding `ß`→`b` first threw that away and turned STRAẞE into STRABE (#597).
        cased = fix_case_mismatch(source_cp, prototype)
        if len(cased) > 1 and cased.isascii():
            target_str = cased
        else:
            target_str = fix_case_mismatch(source_cp, ASCII_FOLD.get(prototype, prototype))
        if target_str == chr(source_cp):
            continue  # never self-map
        result[source_cp] = target_str
    return list(result.items())


def generate_mappings(
    entries: list[tuple[int, list[int]]],
    script_name: str,
    supplement: dict[int, str] | None = None,
) -> list[tuple[int, str]]:
    """Generate all mappings for a target script.

    For Latin: use direct filtering only (TR39 prototypes are Latin, so
    direct filtering catches everything).

    For non-Latin targets (Cyrillic, etc.): combine direct filtering with
    equivalence-class inversion. Direct catches entries where the TR39
    prototype happens to be in the target script. Class-based catches the
    common case where the target-script member is a *source* in TR39
    (e.g. Cyrillic А → Latin A), which we invert to Latin A → Cyrillic А.
    """
    # Direct: picks up entries where the prototype IS in the target script
    direct = filter_direct(entries, script_name)

    if script_name == "latin":
        # Direct covers cross-script → Latin. Add the intra-Latin homoglyphs of
        # basic ASCII letters that direct skips (þ→p, ſ→f, ı→i, …); direct wins.
        merged = dict(direct)
        for cp, target in filter_latin_homoglyphs(entries):
            merged.setdefault(cp, target)
        # A character that IS a digit (its NFKC decomposition is a single ASCII
        # digit — e.g. the Mathematical Alphanumeric digits 𝟎/𝟏) must fold to
        # that digit, not to a look-alike letter (𝟎→O, 𝟏→l). TR39 puts 0/1 in
        # the O/l confusable classes, so the generic logic picks the letter;
        # override digits here so normalize_confusables keeps numbers numeric (#89).
        for cp in list(merged):
            digit = ucd_nfkc(cp)
            if len(digit) == 1 and "0" <= digit <= "9":
                merged[cp] = digit
        # Safe non-letter look-alikes TR39 does not fold onto a Latin letter
        # (e.g. the box-drawing vertical that NFKC produces from U+FFE8). These
        # take priority so the pipeline neutralizes them post-NFKC (#245).
        for cp, target in CUSTOM_LATIN_OVERRIDES.items():
            merged[cp] = target
        # #341: fold TR39's non-ASCII Latin-extended prototypes (ĸ/ꞓ/ß/…) down to
        # their basic-ASCII representative, reconciling case to the source. Glyphs
        # absent from ASCII_FOLD (esh, ɂ, Ƕ, …) are left as documented residue.
        for cp, out in list(merged.items()):
            if len(out) == 1 and out in ASCII_FOLD:
                merged[cp] = fix_case_mismatch(cp, ASCII_FOLD[out])
        # #815: the same glyphs, as SOURCES.
        #
        # The pass above resolves a small capital when it is a row's *target*, which is
        # why `\u1d0d` ᴍ folds — TR39 happens to list it as a source too
        # (`1D0D ; 028D`). `\u1d00` ᴀ is listed only as a destination, so nothing folded
        # it and a word written in small capitals half-converted: `can you` came back as
        # `cᴀn you`, matching neither the attack nor the target, and `llm_guardrail`
        # handed it to the model in that state.
        #
        # Restricted to the derived `LATIN LETTER SMALL CAPITAL X` set, not all of
        # `ASCII_FOLD`. That set is a letter-for-letter identity with no visual judgment
        # to make — `\u1d1b` ᴛ *is* a T — which is the same argument
        # `_small_capital_folds` already makes for the target direction. The hand-written
        # `ASCII_FOLD` entries (ß→b, ꞓ→e) are visual calls about glyphs that are real
        # letters in real orthographies, and turning those into sources is the open
        # policy question in #815, not this.
        #
        # An existing row always wins: this only fills gaps.
        #
        # `_enclosed_letter_folds` joins it for the same reason and on the same terms
        # (#815). U+1F150 and U+1F170 fold on no surface while their positive
        # counterparts fold via NFKC, so a generator offering "circled" and "circled
        # (negative)" side by side gets one neutralised and one through untouched.
        for source in (_small_capital_folds(), _enclosed_letter_folds()):
            for glyph, letter in source.items():
                merged.setdefault(ord(glyph), fix_case_mismatch(ord(glyph), letter))
        # #342/#343: measured cross-script supplement, applied with priority so it
        # can add a missing fold or re-point an existing one.
        for cp, target in (supplement or {}).items():
            merged[cp] = target
        return list(merged.items())

    # For non-Latin: also invert equivalence classes
    direct_map = dict(direct)
    class_based = filter_via_classes(entries, script_name)

    # Merge: direct takes priority
    merged = dict(direct_map)
    for cp, target in class_based:
        if cp not in merged:
            merged[cp] = target

    # #342/#343: measured cross-script supplement, applied with priority.
    for cp, target in (supplement or {}).items():
        merged[cp] = target

    return list(merged.items())


# ---------------------------------------------------------------------------
# TSV output
# ---------------------------------------------------------------------------


def _nfkc_image_rows(
    mappings: dict[int, str], script_name: str, latin_rows: frozenset[int]
) -> dict[int, str]:
    """Rows for the NFKC image of a source, where the image has no row of its own (#833).

    Every confusable-bearing preset runs `normalize` before `confusables` (`STEP_ORDER`),
    so the fold never sees the source code point — it sees the NFKC image. When the image
    has no row, the row that exists for the source is unreachable from every preset:

        U+03F2 GREEK LUNATE SIGMA -> `c` in the table
        NFKC(U+03F2)              -> U+03C2 GREEK SMALL FINAL SIGMA, no row
        llm_guardrail("ϲecure")   -> "oecure", never "cecure"

    #245 diagnosed this correctly for U+2502 and fixed it with one hand-written entry in
    `CUSTOM_LATIN_OVERRIDES`. The diagnosis generalises and a literal does not, which is
    why this is derived: any future `confusables.txt` that routes a new class through an
    unmapped NFKC image is covered without an edit.

    Four filters, each of which excludes rows that would be wrong rather than merely
    unnecessary:

    * The image must differ from the source and be a single code point. A multi-character
      image is a decomposition, not a look-alike.
    * The image must have no row already. An existing row is a decision; this only fills
      gaps.
    * The image must be non-ASCII. An ASCII image needs no fold, and emitting one would
      add 26 identity rows (`A` -> `A`) and break the three-ASCII-sources contract (#725).
    * The image must be a letter, or already carry a row in the Latin table. The second
      clause is what brings U+2502 to the Cyrillic side: #245 decided a box-drawing
      vertical folds to a letter shape, and that decision was applied to one target only.
      Without it the em dash would join too — U+FE58 SMALL EM DASH normalises to U+2014,
      which is a dash rather than a look-alike letter and is nobody's spoof.
    """
    # Latin and Cyrillic only, deliberately. The RTL tables are built the other way
    # round — #791/#792 invert equivalence classes and drop any class with no
    # target-script member — so a source there is often an Arabic *mathematical* variant
    # whose NFKC image is the ordinary letter. Propagating the row would fold the base
    # letter: `\u062b` ث would become `\u0649` ى, corrupting every Arabic word that
    # contains it. That is #848's intra-script case, which a cross-script table cannot
    # express, and it needs its own analysis rather than this derivation.
    if script_name not in ("latin", "cyrillic"):
        return {}

    out: dict[int, str] = {}
    for source, target in mappings.items():
        image = ucd_nfkc(source)
        if len(image) != 1 or ord(image) == source:
            continue
        image_cp = ord(image)
        if image_cp in mappings or image.isascii():
            continue
        # An image that already IS the target is an identity row. Common for the RTL
        # targets, where a presentation form's NFKC image is the very letter the row
        # points at: 33 such rows for Arabic and 4 for Hebrew, every one of them
        # `X -> X`. They fold nothing and would inflate the tables the size gates watch.
        if image == target:
            continue
        if not (ucd_category(image_cp).startswith("L") or image_cp in latin_rows):
            continue
        if script_name == "latin" and not target.isascii():
            continue
        previous = out.get(image_cp)
        if previous is not None and previous != target:
            # Two sources whose images collide on different targets. Dropping both is the
            # safe read: picking one would be an undocumented visual judgment.
            out.pop(image_cp, None)
            continue
        out[image_cp] = target
    return out


def _resolve_target_chains(mappings: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Rewrite every target through the map until it is a fixed point (#723).

    A target may itself contain a source. `044B` ы mapped to `\u0185i`, and `\u0185` ƅ is
    a source that folds to `b` — so the entry points that iterate (`normalize_confusables`,
    `canonicalize`) reached `bi` while the single-pass ones (`strip_obfuscation`, and the
    `confusables` step inside `get_pipeline`) stopped at `ƅi`. The exhaustive idempotence
    gate tested only the function that iterates, so the class was invisible.

    Resolving here rather than in the consumer is what makes it stay fixed: build.rs
    asserts no target contains a source, and that assert can only hold if the data
    already satisfies it. A `MAX_PASSES` bound rather than `while` because a cycle in the
    data would otherwise hang the generator; a cycle is a data defect and should say so.
    """
    MAX_PASSES = 8
    table = dict(mappings)
    for _ in range(MAX_PASSES):
        changed = False
        for source, target in list(table.items()):
            # Each character of the target, replaced by its own target if it has one.
            # `table.get(ord(ch), ch)` leaves a character that is not a source alone.
            resolved = "".join(table.get(ord(ch), ch) for ch in target)
            if resolved != target:
                table[source] = resolved
                changed = True
        if not changed:
            break
    else:
        raise ValueError(
            f"target chains did not converge in {MAX_PASSES} passes. Most likely a "
            "cycle — two rows folding into each other, or a longer loop — but a chain "
            "genuinely deeper than the bound would look the same. Read the rows before "
            "raising it: a cycle is a data defect and no bound fixes it."
        )
    return sorted(table.items())


def write_tsv(mappings: list[tuple[int, str]], path: Path, script_name: str) -> None:
    """Write mappings as TSV: HEX_CODEPOINT<tab>value, with a provenance header.

    The leading ``#`` comment records the bundled Unicode/UTS#39 vintage so the
    security-critical confusables tables carry their own provenance (#548); build.rs
    skips ``#`` lines. Keep it in sync with ``docs/provenance.md``.
    """
    mappings.sort(key=lambda x: x[0])
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            f"# Unicode UTS#39 confusables.txt {DATA_UNICODE_VERSION}, folded to "
            f"{script_name.capitalize()}, plus disarm cross-script additions (#336). "
            f"Generated by scripts/gen_confusables.py - see docs/provenance.md.\n"
        )
        for source_cp, target_str in mappings:
            escaped = []
            for ch in target_str:
                cp = ord(ch)
                if 0x20 <= cp <= 0x7E and ch != "\\":
                    escaped.append(ch)
                else:
                    escaped.append(f"\\u{{{cp:04X}}}")
            f.write(f"{source_cp:04X}\t{''.join(escaped)}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _check_unicode_version(sources: list[int] | None = None) -> None:
    """Refuse to generate from a table this interpreter cannot fully classify (#439, #734).

    The old check was a version floor, and a floor is the wrong shape twice over. Set
    below `DATA_UNICODE_VERSION` it permits exactly the corruption it exists to prevent —
    regenerating under UCD 16.0.0 against 17.0.0 data folded `U+11DE0` TOLONG SIKI DIGIT
    ZERO to the letter `O`, because `enforce_digit_target` cannot protect a code point it
    does not know is a digit. Set equal to it, table generation is pinned to whichever
    CPython ships that UCD, which for data that leads the release cycle means an alpha.

    The real requirement is neither: every code point the data references must be
    classifiable, by `unicodedata` or by `data/ucd_backfill.tsv`. That is what is checked.
    """
    cur = unicodedata.unidata_version
    as_tuple = lambda v: tuple(int(p) for p in v.split("."))  # noqa: E731
    if as_tuple(cur) < as_tuple(MIN_UNICODE_VERSION):
        sys.exit(
            f"gen_confusables requires unicodedata >= {MIN_UNICODE_VERSION}, but this "
            f"Python ships {cur}. The backfill in {BUNDLED_UCD_BACKFILL.name} is built "
            f"against that baseline and does not describe the gap below it."
        )
    if not sources:
        return
    blind = [
        cp for cp in sources if unicodedata.category(chr(cp)) == "Cn" and cp not in UCD_BACKFILL
    ]
    if blind:
        shown = ", ".join(f"U+{cp:04X}" for cp in blind[:10])
        sys.exit(
            f"{len(blind)} code point(s) in confusables.txt are unassigned in this "
            f"Python's UCD ({cur}) and absent from {BUNDLED_UCD_BACKFILL.name}: {shown}"
            f"{' …' if len(blind) > 10 else ''}.\n"
            f"Their category, digit value and decomposition are unknown, so the digit "
            f"guard (#439) and the case reconciliation (#734) cannot fire and the maps "
            f"would be silently wrong. Regenerate the backfill under a UCD "
            f"{DATA_UNICODE_VERSION} interpreter:\n"
            f"    uv run --python 3.15 python scripts/gen_ucd_backfill.py"
        )


def write_upstream_sources(entries: list[tuple[int, list[int]]], path: Path) -> int:
    """Write every source codepoint in upstream ``confusables.txt`` as a char-set TSV.

    #563: the generator reads the whole upstream file and then discards everything it
    does not fold, so the coverage question — *which confusable sources does the
    bundled table not map?* — could only be answered by a harness built outside the
    library against a cached copy of the same file. Emitting the source set here turns
    that into a generated table, and the discard set becomes a runtime derivation
    (upstream sources minus the bundled map's keys) rather than a second artifact that
    can go stale against the table it describes.

    Deliberately the *full* source set, not the pre-computed latin miss list: the
    library has two confusable tables, and deriving the misses per target at runtime
    keeps the answer correct when either table gains a row.

    Returns the number of sources written.
    """
    sources = sorted({cp for cp, _ in entries})
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            f"# Unicode UTS#39 confusables.txt {DATA_UNICODE_VERSION} — every SOURCE "
            f"codepoint in the upstream file (#563). Not a mapping: this is the "
            f"denominator for coverage introspection. Generated by "
            f"scripts/gen_confusables.py - see docs/provenance.md.\n"
        )
        for cp in sources:
            f.write(f"{cp:04X}\n")
    return len(sources)


def write_digit_tr39_overrides(
    entries: list[tuple[int, list[int]]],
    latin: dict[int, str],
    path: Path,
) -> int:
    """Emit the rows where disarm's digit policy diverges from upstream TR39 (#561).

    disarm maps a non-Latin digit to the ASCII digit; TR39 maps several of them to
    *something that is not that digit* — usually a Latin letter (Devanagari zero to ``o``,
    Kannada zero to ``O``, Arabic-Indic one to ``l``), but also punctuation (Arabic-Indic
    zero to ``.``) and, in one case, a two-character sequence (``rn``).
    Both readings are defensible — numeric is right for prose, the letter is right for
    identifier skeletons — and the divergence was previously fixed in the table with no way
    to select the other behaviour.

    This emits the *override set*: only the rows that actually differ, keyed by source
    codepoint with TR39's target as the value. Shipping an override set rather than a
    second full table means the two policies cannot drift apart in the rows they agree on,
    which is all but ~45 of them.

    The generator already computes both sides — it makes this exact choice at generation
    time via ``enforce_digit_target`` (#439) — so the discarded alternative is emitted here
    instead of thrown away. Returns the number of rows written.
    """
    upstream: dict[int, list[int]] = {}
    for source_cp, target_cps in entries:
        upstream.setdefault(source_cp, target_cps)

    rows: list[tuple[int, str]] = []
    for source_cp, ours in sorted(latin.items()):
        # Only rows where OUR target is a single ASCII digit can be digit-policy rows.
        if not (len(ours) == 1 and ours.isascii() and ours.isdigit()):
            continue
        cleaned = strip_combining(upstream.get(source_cp, []))
        theirs = "".join(chr(cp) for cp in cleaned)
        # #587: put the override through the same post-processing every value in the
        # main Latin table gets. This set was written after #341 made ASCII the
        # contract and never joined it, so `digit_policy="tr39"` reintroduced exactly
        # the non-ASCII residue #341 had removed — ٨ came back as `Ʌ` (U+0245) where
        # the main pipeline folds that glyph to `a`. Worse, TR39 puts ٨ ۸ Λ Ꟛ in ONE
        # confusable class, so the un-folded value made the class stop colliding,
        # which is the one thing a skeleton exists to do.
        if len(theirs) == 1 and theirs in ASCII_FOLD:
            theirs = fix_case_mismatch(source_cp, ASCII_FOLD[theirs])
        if not theirs or not theirs.isascii():
            # No clear ASCII representative, so the divergence cannot be expressed
            # under the contract — `ꝰ` (U+A770) is the only such row today. Shipping
            # it raw would put the residue straight back, so drop the row instead and
            # let `tr39` fall back to the numeric reading for that codepoint.
            continue
        if theirs != ours:
            rows.append((source_cp, theirs))

    with open(path, "w", encoding="utf-8") as f:
        f.write(
            f"# Unicode UTS#39 confusables.txt {DATA_UNICODE_VERSION} — digit-policy "
            f"overrides (#561). Rows where disarm folds a digit to the ASCII DIGIT and "
            f"TR39 folds it to something else — mostly a Latin letter, but also "
            f"punctuation ('.') and one two-character sequence ('rn'). The value is "
            f"TR39's target run through ASCII_FOLD, so it is always ASCII (#341/#587); "
            f"a divergence with no ASCII form is dropped and tr39 falls back to the "
            f"numeric reading. Applied only under digit_policy='tr39'. Generated by "
            f"scripts/gen_confusables.py.\n"
        )
        for source_cp, theirs in rows:
            escaped = "".join(
                ch if 0x20 <= ord(ch) < 0x7F else f"\\u{{{ord(ch):04X}}}" for ch in theirs
            )
            f.write(f"{source_cp:04X}\t{escaped}\n")
    return len(rows)


def main() -> None:
    _check_unicode_version()
    parser = argparse.ArgumentParser(
        description="Generate confusable TSV files from TR39 confusables.txt"
    )
    parser.add_argument(
        "--input", type=Path, help="Local confusables.txt (default: bundled data/confusables.txt)"
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Fetch the latest confusables.txt from unicode.org instead of the pinned bundled copy",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DATA_DIR,
        help=f"Output directory for TSV files (default: {DATA_DIR})",
    )
    args = parser.parse_args()

    if args.input:
        text = args.input.read_text(encoding="utf-8")
    elif args.download:
        print("Downloading confusables.txt...", file=sys.stderr)
        with urllib.request.urlopen(CONFUSABLES_URL, timeout=30) as resp:  # noqa: S310
            text = resp.read().decode("utf-8")
    else:
        print(f"Using bundled {BUNDLED_CONFUSABLES}", file=sys.stderr)
        text = BUNDLED_CONFUSABLES.read_text(encoding="utf-8")

    entries = parse_confusables(text)
    print(f"Parsed {len(entries)} total entries", file=sys.stderr)

    # Now that the data is loaded, check this interpreter can actually classify it —
    # sources and targets alike, since `fix_case_mismatch` inspects both.
    referenced = {cp for cp, _ in entries}
    for _, tgt in entries:
        referenced |= set(tgt)
    _check_unicode_version(sorted(referenced))

    supplement = load_supplement(BUNDLED_SUPPLEMENT)
    # #738: the SSIM-admitted rows share the supplement's shape and its position — measured
    # visual evidence, applied before the attested rows so real-attacker evidence wins on an
    # overlap. There is none today; the ordering is stated rather than left to insertion.
    vision = load_supplement(BUNDLED_VISION)
    for script_key in ("latin", "cyrillic"):
        supplement[script_key].update(vision[script_key])
    attested = load_attested(BUNDLED_ATTESTED)
    # #597: merged into one override map. Both are applied with priority over the
    # TR39-derived mappings; the files are separate because their admission criteria and
    # provenance are, not because the pipeline treats them differently.
    for script_key in ("latin", "cyrillic"):
        supplement[script_key].update(attested[script_key])
    # #831: applied after the attested rows, so the LGR's judgement wins on an overlap.
    # There is none today; the ordering is stated rather than left to dict insertion.
    lgr = load_lgr(BUNDLED_LGR)
    supplement["latin"].update(lgr)
    print(
        f"Loaded overrides: {len(supplement['latin'])} latin + "
        f"{len(supplement['cyrillic'])} cyrillic "
        f"(#342/#343 supplement + {len(vision['latin'])} vision rows, #738 + "
        f"{len(attested['latin'])} attested rows, #597 + "
        f"{len(lgr)} ICANN LGR rows, #831)",
        file=sys.stderr,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Built in two passes because #833's image rule needs the finished Latin row set:
    # a box-drawing vertical folds to a letter shape in Latin (#245) and that decision
    # should carry to the Cyrillic table, which is the half #245 left open.
    raw: dict[str, dict[int, str]] = {
        script_name: dict(generate_mappings(entries, script_name, supplement.get(script_name, {})))
        for script_name in SCRIPTS
    }
    latin_rows = frozenset(raw["latin"])

    by_script: dict[str, list[tuple[int, str]]] = {}
    for script_name in SCRIPTS:
        mappings_map = raw[script_name]
        # #833: every confusable-bearing preset normalizes before it folds, so the step
        # sees the NFKC image of a source rather than the source. Give the image the
        # source's target when it has no row of its own, or the row that exists is
        # unreachable from every preset that normalizes.
        image_rows = _nfkc_image_rows(mappings_map, script_name, latin_rows)
        mappings_map.update(image_rows)
        # #723: a target may contain a source, which leaves single-pass callers one step
        # short of the fixed point the iterating ones reach. Resolve it in the data.
        mappings = _resolve_target_chains(list(mappings_map.items()))
        by_script[script_name] = mappings
        out_path = args.output_dir / f"confusables_to_{script_name}.tsv"
        write_tsv(mappings, out_path, script_name)
        print(
            f"  → {script_name}: {len(mappings)} mappings "
            f"(+{len(image_rows)} NFKC-image rows, #833) → {out_path.name}",
            file=sys.stderr,
        )

    # #561: the digit-policy override set — the alternative target the generator
    # discards when it enforces the numeric digit rule. Reuses the Latin mapping the
    # loop above already built rather than running the whole Latin pipeline twice.
    latin_map = dict(by_script["latin"])
    overrides_path = args.output_dir / "confusables_digit_tr39.tsv"
    n_overrides = write_digit_tr39_overrides(entries, latin_map, overrides_path)
    print(
        f"  → digit tr39 overrides: {n_overrides} rows → {overrides_path.name}",
        file=sys.stderr,
    )

    # #563: the coverage denominator, so `unmapped_confusables()` can be answered from
    # inside the library instead of from a paper harness.
    sources_path = args.output_dir / "confusables_upstream_sources.tsv"
    n_sources = write_upstream_sources(entries, sources_path)
    print(
        f"  → upstream sources: {n_sources} codepoints → {sources_path.name}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
