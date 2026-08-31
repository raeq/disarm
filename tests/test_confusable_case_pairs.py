"""#801 — a confusable mapping on a cased letter implies one on its case pair.

The bundled fold carried `Т` (U+0422 CYRILLIC CAPITAL TE) → `T` and nothing for `т`
(U+0442), the lowercase it case-folds to. That asymmetry was invisible while hostname
analysis ran on whatever spelling arrived; #797 made the analysis run on the form the name
actually resolves to, and UTS #46 case-folds every label — so both spellings converged onto
the *unmapped* one and `Т.com` stopped being flagged. DNS lowercases, so the unmapped side
is the side that resolves.

The generator now folds the TR39 prototype through `ASCII_FOLD` *before* the script gate.
Membership in that map is itself the claim that the prototype is a Latin letter with an
ASCII representative, so gating it on a list of block ranges rejected rows the map already
answered for: `ᴛ` U+1D1B sits in Phonetic Extensions, which no range on that list covers.

This gate is the assertion, and it is **derived from the table** rather than from a list of
code points: every cased source in `confusables_to_latin.tsv` must have its case pair
mapped too, unless the pair falls in a stated exemption class. A table refresh that reopens
the asymmetry fails here instead of widening it — the shape #774 and #614 both use.
"""

from __future__ import annotations

import pathlib
import unicodedata

import pytest

import disarm

ROOT = pathlib.Path(__file__).resolve().parent.parent
TABLE = ROOT / "src" / "tables" / "data" / "confusables_to_latin.tsv"
UPSTREAM = ROOT / "data" / "confusables.txt"


def _table() -> dict[int, str]:
    out: dict[int, str] = {}
    for line in TABLE.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        source, target = line.split("\t")[:2]
        out[int(source, 16)] = target
    return out


def _prototypes() -> dict[int, str]:
    """Each upstream source's TR39 prototype, as a string."""
    out: dict[int, str] = {}
    for line in UPSTREAM.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or ";" not in line:
            continue
        head, target = line.split(";")[0].strip(), line.split(";")[1]
        try:
            source = int(head, 16)
        except ValueError:
            continue
        out[source] = "".join(chr(int(part, 16)) for part in target.split())
    return out


MAPPED = _table()
PROTOTYPES = _prototypes()


def _pair(cp: int) -> int | None:
    """The single code point `cp` case-folds to, or None if there is no simple pair."""
    folded = disarm.fold_case(chr(cp))
    if len(folded) != 1 or folded == chr(cp):
        return None
    return ord(folded)


def _exempt(pair: int) -> str | None:
    """Why the pair is allowed to stay unmapped, or None if it is not.

    One class, stated rather than enumerated: **the pair's own upstream prototype is not
    a Latin letter.** `confusables_to_latin.tsv` maps onto Latin, so a Greek `χ` or
    Cyrillic `л` prototype would need a cross-script decision — `χ` → `x` is a
    transliteration judgment, which belongs in the transliteration tables and not in a
    homoglyph fold. A pair with no upstream row at all is exempt for the stronger reason
    that upstream offers no evidence the lowercase is confusable with anything.
    """
    prototype = PROTOTYPES.get(pair)
    if prototype is None:
        return "no upstream row for the pair"
    letters = [ch for ch in prototype if not unicodedata.category(ch).startswith("M")]
    if any(not unicodedata.name(ch, "").startswith("LATIN") for ch in letters):
        return "upstream prototype is not a Latin letter"
    return None


def _asymmetric() -> list[tuple[int, int]]:
    out = []
    for source in MAPPED:
        pair = _pair(source)
        if pair is not None and pair not in MAPPED and _exempt(pair) is None:
            out.append((source, pair))
    return sorted(out)


def test_the_table_and_upstream_both_loaded() -> None:
    """A gate over an empty table passes for the wrong reason."""
    assert len(MAPPED) > 2000, len(MAPPED)
    assert len(PROTOTYPES) > 6000, len(PROTOTYPES)


def test_no_cased_mapping_lacks_its_case_pair() -> None:
    """The assertion. Every exemption must be one of the stated classes."""
    gaps = _asymmetric()
    assert not gaps, [
        f"U+{s:04X} {chr(s)} -> {MAPPED[s]!r} but U+{p:04X} {chr(p)} is unmapped" for s, p in gaps
    ]


def test_the_exempt_pairs_are_exempt_for_a_stated_reason() -> None:
    """The exemption list is derived, so it has to hold for a reason each time.

    Seven pairs are exempt today: five with a Greek prototype (`χ` twice, `λ` twice,
    `Γ` once), one Cyrillic (`л`), one the PARTIAL DIFFERENTIAL. Note the last runs the
    other way — `\uab81` ꮁ, a Cherokee *lowercase*, is mapped and its capital
    `\u13b1` Ꮁ is not, because that capital's prototype is Greek gamma. If the count
    moves, the reason class moved with it and wants reading.
    """
    exempt = {}
    for source in MAPPED:
        pair = _pair(source)
        if pair is None or pair in MAPPED:
            continue
        reason = _exempt(pair)
        if reason == "upstream prototype is not a Latin letter":
            exempt[pair] = reason
    assert len(exempt) == 7, sorted(f"U+{cp:04X} {chr(cp)}" for cp in exempt)


@pytest.mark.parametrize(
    ("upper", "lower", "target"),
    [
        ("Т", "т", "T"),  # CYRILLIC TE — the pair in #801's title
        ("Н", "н", "H"),  # CYRILLIC EN
        ("М", "м", "M"),  # CYRILLIC EM — needed the ʍ prototype
        ("З", "з", "3"),  # CYRILLIC ZE — needed the ɜ prototype
        ("Ҭ", "ҭ", "T"),  # CYRILLIC TE WITH DESCENDER
        ("Ⲏ", "ⲏ", "H"),  # COPTIC HATE
    ],
    ids=["te", "en", "em", "ze", "te-descender", "coptic-hate"],
)
def test_both_spellings_fold_and_both_screen(upper: str, lower: str, target: str) -> None:
    """The behaviour, not just the table: the capital and the lowercase agree.

    Before this change the capital folded and the lowercase did not, so a case fold —
    which UTS #46 applies to every hostname label — converged both onto the unmapped
    spelling and the hostname screened clean.
    """
    assert disarm.normalize_confusables(upper) == target
    assert disarm.normalize_confusables(lower) == target.lower()
    assert disarm.is_suspicious_hostname(f"{upper}.com")[0]
    assert disarm.is_suspicious_hostname(f"{lower}.com")[0]


def test_the_cherokee_rows_this_also_closed() -> None:
    """#715's ask, landed here rather than separately — worth saying out loud.

    #715 asks whether 16 dropped Cherokee sources should be folded now that a published
    CVE routes traffic into them. It names `U+AB70` specifically. The prototype fix
    reaches them by the same mechanism, so the answer is yes and it is already done.
    """
    for source, target in (("ꭰ", "d"), ("ꭱ", "r"), ("ꭲ", "t"), ("ᏼ", "b")):
        assert disarm.normalize_confusables(source) == target, source
