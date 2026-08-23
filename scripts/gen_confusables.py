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
MIN_UNICODE_VERSION = "16.0.0"
# Measured cross-script supplement folded with priority over TR39 (#342/#343).
BUNDLED_SUPPLEMENT = Path(__file__).resolve().parent.parent / "data" / "confusables_supplement.tsv"
BUNDLED_ATTESTED = Path(__file__).resolve().parent.parent / "data" / "confusables_attested.tsv"


# ---------------------------------------------------------------------------
# Codepoint classification
# ---------------------------------------------------------------------------


def is_combining_mark(cp: int) -> bool:
    """True if codepoint is a Unicode combining mark (category M*)."""
    return unicodedata.category(chr(cp)).startswith("M")


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
    return any(
        unicodedata.category(ch).startswith("M") for ch in unicodedata.normalize("NFD", chr(cp))
    )


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
}


# ---------------------------------------------------------------------------
# Target script definitions
# ---------------------------------------------------------------------------

SCRIPTS = {
    "latin": {
        "is_target": is_latin,
        "is_target_or_common": is_latin_or_common,
    },
    "cyrillic": {
        "is_target": is_cyrillic,
        "is_target_or_common": lambda cp: is_cyrillic(cp) or is_combining_mark(cp),
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


def fix_case_mismatch(source_cp: int, target_str: str) -> str:
    """Ensure case consistency between source and target.

    If source is uppercase and target is lowercase (or vice versa),
    adjust the target to match. Special case: the {I, l, 1} class
    where uppercase should map to I, not L.
    """
    if len(target_str) != 1 or not target_str.isalpha():
        return target_str
    source_cat = unicodedata.category(chr(source_cp))
    target_cat = unicodedata.category(target_str)
    if source_cat == "Lu" and target_cat == "Ll":
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
    if unicodedata.category(chr(source_cp)) != "Nd":
        return target_str
    if len(target_str) == 1 and target_str.isascii() and target_str.isdigit():
        return target_str
    d = unicodedata.digit(chr(source_cp), None)
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
        if not all(is_target_or_common(cp) for cp in cleaned_cps):
            continue
        target_str = "".join(chr(cp) for cp in cleaned_cps)
        if not target_str.strip():
            continue
        # #593: ASCII-fold before reconciling case, for the same reason as
        # `filter_latin_homoglyphs`. `fix_case_mismatch` uppercases, and `ß`.upper() is
        # the two-character `SS`, which then escapes the `ASCII_FOLD` pass in
        # `generate_mappings` because that only fires on a single character. That is how
        # Cherokee YE (U+13F0), a B-shape, came out as `SS` in a table about *visual*
        # confusability. Blast radius measured: this row and no other.
        target_str = fix_case_mismatch(source_cp, ASCII_FOLD.get(target_str, target_str))
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
                cat = unicodedata.category(chr(m))
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

            source_cat = unicodedata.category(chr(m))

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
            digit = unicodedata.normalize("NFKC", chr(cp))
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


def _check_unicode_version() -> None:
    """Refuse to run under a Unicode table too old to classify the data's digits (#439)."""
    cur = unicodedata.unidata_version
    as_tuple = lambda v: tuple(int(p) for p in v.split("."))  # noqa: E731
    if as_tuple(cur) < as_tuple(MIN_UNICODE_VERSION):
        sys.exit(
            f"gen_confusables requires unicodedata >= {MIN_UNICODE_VERSION}, but this Python "
            f"ships {cur}. Under an older table, digits assigned in newer Unicode (e.g. the "
            f"outlined digits U+1CCF0/U+1CCF1) are not recognised and fold to look-alike "
            f"letters (#439). Run under a newer Python."
        )
    if cur != DATA_UNICODE_VERSION:
        print(
            f"warning: confusables.txt is Unicode {DATA_UNICODE_VERSION} but this Python's "
            f"unicodedata is {cur}; characters assigned only in {DATA_UNICODE_VERSION} may be "
            f"misclassified. Regenerate under a matching Python when one is available.",
            file=sys.stderr,
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

    supplement = load_supplement(BUNDLED_SUPPLEMENT)
    attested = load_attested(BUNDLED_ATTESTED)
    # #597: merged into one override map. Both are applied with priority over the
    # TR39-derived mappings; the files are separate because their admission criteria and
    # provenance are, not because the pipeline treats them differently.
    for script_key in ("latin", "cyrillic"):
        supplement[script_key].update(attested[script_key])
    print(
        f"Loaded overrides: {len(supplement['latin'])} latin + "
        f"{len(supplement['cyrillic'])} cyrillic "
        f"(#342/#343 supplement + {len(attested['latin'])} attested rows, #597)",
        file=sys.stderr,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    by_script: dict[str, list[tuple[int, str]]] = {}
    for script_name in SCRIPTS:
        mappings = generate_mappings(entries, script_name, supplement.get(script_name, {}))
        by_script[script_name] = mappings
        out_path = args.output_dir / f"confusables_to_{script_name}.tsv"
        write_tsv(mappings, out_path, script_name)
        print(
            f"  → {script_name}: {len(mappings)} mappings → {out_path.name}",
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
