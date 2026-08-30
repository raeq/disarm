"""Coverage gate against the official Unicode UTS#39 confusables.

disarm's confusable table is generated from the pinned ``data/confusables.txt``.
This test asserts that every single-codepoint confusable whose official prototype
is a single basic Latin letter (A-Z / a-z) is actually neutralized by
``normalize_confusables(..., target_script="latin")``.

It guards against regressions and Unicode-version drift (see THREAT_MODEL.md:
"Unicode-version skew"). It does NOT assert coverage of confusables outside the
bundled data — those are documented out-of-scope.
"""

from __future__ import annotations

import pathlib
import re
import unicodedata

import pytest

from disarm import normalize_confusables

CONFUSABLES = pathlib.Path(__file__).resolve().parent.parent / "data" / "confusables.txt"
GENERATED = pathlib.Path(__file__).resolve().parent.parent / "src" / "tables" / "data"
_ASCII_LETTERS = set(range(0x41, 0x5B)) | set(range(0x61, 0x7B))


def _latin_letter_confusables() -> list[str]:
    """Source chars whose official prototype is a single basic ASCII letter."""
    # Fail hard, never skip: the pinned source is committed and required for the
    # gate to mean anything. Its absence is itself a regression to surface.
    assert CONFUSABLES.exists(), (
        f"pinned confusables source missing: {CONFUSABLES} — the coverage gate "
        f"cannot run without it"
    )
    out: list[str] = []
    for raw in CONFUSABLES.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 2:
            continue
        try:
            src = [int(x, 16) for x in parts[0].split()]
            tgt = [int(x, 16) for x in parts[1].split()]
        except ValueError:
            continue
        if len(src) == 1 and src[0] >= 0x80 and len(tgt) == 1 and tgt[0] in _ASCII_LETTERS:
            out.append(chr(src[0]))
    return out


def test_latin_letter_confusable_coverage() -> None:
    chars = _latin_letter_confusables()
    assert chars, "no Latin-letter confusables parsed — data file malformed?"
    misses = [c for c in chars if c in normalize_confusables(c, target_script="latin")]
    assert not misses, (
        f"{len(misses)} of {len(chars)} single-letter Latin confusables are not "
        f"neutralized: {[f'U+{ord(c):04X}' for c in misses]}"
    )


def test_no_digit_source_folds_to_a_letter() -> None:
    """#439: a digit-category (``Nd``) source must never fold to a non-digit.

    A digit spoof (Arabic-Indic ٠, Devanagari ०, the outlined digits 𜳰/𜳱, …) must
    canonicalize to its plain ASCII digit, not a look-alike letter (𜳰→O / ٠→o was
    the bug). Checks the generated maps directly. Best-effort per the running
    Unicode version — a source assigned only in a newer Unicode is unknown to an
    older ``unicodedata`` and simply isn't classified as ``Nd`` here; the
    generator's own version guard ensures the committed maps were built correctly.
    """
    offenders: list[str] = []
    for name in ("confusables_to_latin.tsv", "confusables_to_cyrillic.tsv"):
        for raw in (GENERATED / name).read_text(encoding="utf-8").splitlines():
            if "\t" not in raw or raw.startswith("#"):
                continue
            src, tgt = raw.split("\t", 1)
            try:
                ch = chr(int(src, 16))
            except ValueError:
                continue
            if unicodedata.category(ch) != "Nd":
                continue
            if not (len(tgt) == 1 and tgt.isascii() and tgt.isdigit()):
                offenders.append(f"{src}({unicodedata.name(ch, '?')})→{tgt!r}")
    assert not offenders, f"digit sources folding to a non-digit: {offenders}"


# ── Case consistency inside an uppercase block (#734) ─────────────────────────

#: Blocks whose members are uppercase letters *by definition*, so their folded targets
#: have no business disagreeing about case with each other.
#:
#: Scoped to blocks rather than applied globally, because "an uppercase source folds to
#: an uppercase target" is **not** true in general and a global rule would be wrong twice
#: over. `U+026A LATIN LETTER SMALL CAPITAL I` is category `Ll` and correctly keeps `i`.
#: `U+042B CYRILLIC CAPITAL LETTER YERU` correctly folds to `bl`, because that is what it
#: looks like — TR39 is a *visual* mapping, and `BL` does not resemble `Ы`. Neither is a
#: defect, and both would fail a global assertion.
#:
#: What is a defect is one member of a uniform block disagreeing with the other 25.
#: Before #734 the outlined alphabet read `…GHlJK…` and `Ⅷ` folded to `Vlll`.
UPPERCASE_BLOCKS = {
    "outlined capitals": (0x1CCD6, 0x1CCEF),
    "roman numerals": (0x2160, 0x216F),
    "fullwidth capitals": (0xFF21, 0xFF3A),
    "mathematical bold capitals": (0x1D400, 0x1D419),
}


def _generated_rows(tsv_name: str) -> dict[int, str]:
    """Source codepoint -> folded target, with `\\u{...}` escapes resolved."""
    text = (GENERATED / tsv_name).read_text(encoding="utf-8")
    unescape = lambda s: re.sub(  # noqa: E731
        r"\\u\{([0-9A-Fa-f]+)\}", lambda m: chr(int(m.group(1), 16)), s
    )
    out: dict[int, str] = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            out[int(parts[0], 16)] = unescape(parts[1])
    return out


@pytest.mark.parametrize("block", sorted(UPPERCASE_BLOCKS))
def test_uppercase_block_folds_to_one_case(block: str) -> None:
    """Every ASCII-letter target in an uppercase block agrees on case.

    Reads only the generated table — no `unicodedata` — so it is unaffected by which
    Unicode version the running interpreter ships. That matters here specifically:
    `U+1CCDE` was assigned in Unicode 16.0, and CI's Python reports it as unassigned,
    so a check written against `unicodedata` would silently skip the character this
    guard exists for.
    """
    low, high = UPPERCASE_BLOCKS[block]
    targets = {
        cp: t
        for cp, t in _generated_rows("confusables_to_latin.tsv").items()
        if low <= cp <= high and t.isascii() and t.isalpha()
    }
    if len(targets) < 2:
        pytest.skip(f"{block}: fewer than two folded rows in the bundled table")

    odd = {cp: t for cp, t in targets.items() if not t.isupper()}
    assert not odd, (
        f"{block}: {len(targets) - len(odd)} of {len(targets)} rows fold to uppercase, "
        f"but {len(odd)} do not: "
        + ", ".join(f"U+{cp:04X}->{t!r}" for cp, t in sorted(odd.items())[:8])
        + ". A block of uppercase letters folding to two different cases is the #734 "
        "defect: TR39's lowercase `l` prototype reaching a source that "
        "`fix_case_mismatch` did not reconcile."
    )


# ── The UCD backfill must not drift from the UCD (#439, #734) ─────────────────

BACKFILL = pathlib.Path(__file__).resolve().parent.parent / "data" / "ucd_backfill.tsv"
DATA_UNICODE_VERSION = "17.0.0"


def _decode_field(field: str, cp: int) -> str:
    """A backfill decomposition field: `-` means "decomposes to itself"."""
    if field == "-":
        return chr(cp)
    return "".join(chr(int(x, 16)) for x in field.split())


def _backfill_rows() -> list[tuple[int, str, int | None, str, str]]:
    assert BACKFILL.is_file(), (
        f"{BACKFILL} is missing. The generator needs it to classify code points this "
        f"interpreter's UCD does not know; regenerate with "
        f"`uv run --python 3.15 python scripts/gen_ucd_backfill.py`."
    )
    rows = []
    for line in BACKFILL.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        cp_s, cat, dig, nfkc, nfd, *_ = line.split("\t")
        cp = int(cp_s, 16)
        rows.append(
            (
                cp,
                cat,
                None if dig == "-" else int(dig),
                _decode_field(nfkc, cp),
                _decode_field(nfd, cp),
            )
        )
    return rows


def test_backfill_is_not_empty() -> None:
    """A backfill that parses to nothing would disable the generator's completeness gate
    silently — the gate only fails on code points it cannot describe, so an empty file
    reads as 'nothing to describe' rather than as a defect."""
    assert len(_backfill_rows()) > 50, (
        f"{BACKFILL.name} holds {len(_backfill_rows())} rows; expected the ~99 code points "
        f"assigned after the baseline UCD. Regenerate with scripts/gen_ucd_backfill.py."
    )


def test_backfill_covers_every_codepoint_this_interpreter_cannot_classify() -> None:
    """The backfill must describe every referenced code point this Python reads as `Cn`.

    This is the assertion with teeth on the baseline. The value check below can verify
    nothing on an interpreter older than the data — every row is `Cn` there, so it skips
    all 99 and would otherwise read as a pass. Completeness is checkable everywhere, and
    it is the property the generator actually depends on: a referenced code point that is
    `Cn` and unlisted means the digit guard (#439) and the case reconciliation (#734)
    cannot fire, and the maps come out wrong without complaint.
    """
    text = CONFUSABLES.read_text(encoding="utf-8")
    referenced = {int(m.group(1), 16) for m in re.finditer(r"^([0-9A-F]{4,6})\s*;", text, re.M)}
    for m in re.finditer(r"^[0-9A-F]{4,6}\s*;\s*([0-9A-F ]+);", text, re.M):
        referenced |= {int(x, 16) for x in m.group(1).split()}

    listed = {cp for cp, *_ in _backfill_rows()}
    blind = {cp for cp in referenced if unicodedata.category(chr(cp)) == "Cn"} - listed
    assert not blind, (
        f"{len(blind)} code point(s) in confusables.txt are unassigned under UCD "
        f"{unicodedata.unidata_version} and absent from {BACKFILL.name}: "
        + ", ".join(f"U+{cp:04X}" for cp in sorted(blind)[:10])
        + ". Regenerate it with scripts/gen_ucd_backfill.py under a UCD "
        f"{DATA_UNICODE_VERSION} interpreter."
    )


def test_backfill_agrees_with_this_interpreter() -> None:
    """Where this Python knows a code point, the backfill must say the same thing.

    The backfill exists so an interpreter older than the data still classifies it
    correctly. That only holds while the file is *right*, and the file is hand-generated
    from one interpreter, so it can rot. Any Python whose UCD reaches the data version can
    check every row; older ones can only check the rows they happen to know, which is
    still worth doing and is what the `Cn` skip below leaves out.
    """
    rows = _backfill_rows()
    comparable = [r for r in rows if unicodedata.category(chr(r[0])) != "Cn"]
    if not comparable:
        pytest.skip(
            f"UCD {unicodedata.unidata_version} knows none of the {len(rows)} backfilled "
            f"code points, so this check can verify nothing here. Completeness is covered "
            f"by the test above; values are verified under a UCD "
            f"{DATA_UNICODE_VERSION} interpreter."
        )

    mismatches = []
    for cp, cat, dig, nfkc, nfd in comparable:
        ch = chr(cp)
        actual = (
            unicodedata.category(ch),
            unicodedata.digit(ch, None),
            unicodedata.normalize("NFKC", ch),
            unicodedata.normalize("NFD", ch),
        )
        if actual != (cat, dig, nfkc, nfd):
            mismatches.append((cp, (cat, dig, nfkc, nfd), actual))

    assert not mismatches, (
        f"{BACKFILL.name} disagrees with unicodedata {unicodedata.unidata_version} on "
        f"{len(mismatches)} code point(s): "
        + "; ".join(f"U+{cp:04X} file={f!r} ucd={a!r}" for cp, f, a in mismatches[:5])
        + ". The interpreter is authoritative — regenerate with "
        "scripts/gen_ucd_backfill.py under a UCD "
        f"{DATA_UNICODE_VERSION} interpreter."
    )
