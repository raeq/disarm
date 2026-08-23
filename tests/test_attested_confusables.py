"""Coverage gate for the BitCore-attested confusable additions (#597).

TR39 lists visually confusable pairs. Miss-mining the **BitCore** subset of the
BitAbuse corpus (Lee et al., NAACL Findings 2025) with ``benchmarks/adversarial_eval``
surfaced codepoints that real attackers substitute for basic-Latin letters but that
TR39 never lists as sources, so ``normalize_confusables`` left them unfolded.

These rows come from ``data/confusables_attested.tsv``, a channel separate from
``confusables_supplement.tsv``: that file declares itself *cross-script* and pins its
provenance to one measured dataset at a stated threshold, and 18 of these sources are
Latin folding to Latin.

Per the #39/#40 guardrail the corpora are **measuring instruments, never optimization
targets** — every row here is justified by real attestation plus optical or positional
evidence, never by a benchmark score, and the synthetic BitViper tail is excluded by
construction.
"""

from __future__ import annotations

import unicodedata

import pytest

from disarm import normalize_confusables

#: (source, target, tier). Tier 1 is optical; Tier 2a is positional — an attacker
#: reaching for an Armenian/Georgian/runic glyph by position rather than shape — and
#: Tier 2b is convention. Including 2a widens the table's contract from "visual
#: confusable" to "observed attacker substitution"; see the file header and
#: THREAT_MODEL.md.
ATTESTED: list[tuple[str, str, str]] = [
    # ── Tier 1 — optical shape-twins ────────────────────────────────────────
    ("ɴ", "n", "1"),  # ɴ LATIN LETTER SMALL CAPITAL N
    ("ʍ", "m", "1"),  # ʍ LATIN SMALL LETTER TURNED W
    ("ɾ", "r", "1"),  # ɾ LATIN SMALL LETTER R WITH FISHHOOK
    ("ҥ", "h", "1"),  # ҥ CYRILLIC SMALL LIGATURE EN GHE
    ("ĸ", "k", "1"),  # ĸ LATIN SMALL LETTER KRA
    ("ʀ", "r", "1"),  # ʀ LATIN LETTER SMALL CAPITAL R
    ("Ƿ", "p", "1"),  # Ƿ LATIN CAPITAL LETTER WYNN
    ("ʜ", "h", "1"),  # ʜ LATIN LETTER SMALL CAPITAL H
    ("ʟ", "l", "1"),  # ʟ LATIN LETTER SMALL CAPITAL L
    ("μ", "u", "1"),  # μ GREEK SMALL LETTER MU
    ("ɢ", "g", "1"),  # ɢ LATIN LETTER SMALL CAPITAL G
    ("ҡ", "k", "1"),  # ҡ CYRILLIC SMALL LETTER BASHKIR KA
    ("ʙ", "b", "1"),  # ʙ LATIN LETTER SMALL CAPITAL B
    ("ƅ", "b", "1"),  # ƅ LATIN SMALL LETTER TONE SIX
    ("ҳ", "x", "1"),  # ҳ CYRILLIC SMALL LETTER HA WITH DESCENDER
    ("ҏ", "p", "1"),  # ҏ CYRILLIC SMALL LETTER ER WITH TICK
    ("ʝ", "j", "1"),  # ʝ LATIN SMALL LETTER J WITH CROSSED-TAIL
    ("ʌ", "a", "1"),  # ʌ LATIN SMALL LETTER TURNED V
    ("Ʌ", "a", "1"),  # Ʌ LATIN CAPITAL LETTER TURNED V
    ("ᴇ", "e", "1"),  # ᴇ LATIN LETTER SMALL CAPITAL E
    ("ɺ", "i", "1"),  # ɺ LATIN SMALL LETTER TURNED R WITH LONG LEG
    ("ʄ", "f", "1"),  # ʄ LATIN SMALL LETTER DOTLESS J WITH STROKE AND HOOK
    # ── paired with μ so the fold is not normalization-form dependent ───────
    ("µ", "u", "1"),  # µ MICRO SIGN — NFKC maps it to μ
    # ── Tier 2a — exotic-script positional ──────────────────────────────────
    ("ժ", "d", "2a"),  # ժ ARMENIAN SMALL LETTER ZHE
    ("ᚱ", "r", "2a"),  # ᚱ RUNIC LETTER RAIDO RAD REID R
    ("Ա", "u", "2a"),  # Ա ARMENIAN CAPITAL LETTER AYB
    ("Ⴝ", "s", "2a"),  # Ⴝ GEORGIAN CAPITAL LETTER CHAR
    ("Ⴍ", "q", "2a"),  # Ⴍ GEORGIAN CAPITAL LETTER ON
    ("Ⴓ", "q", "2a"),  # Ⴓ GEORGIAN CAPITAL LETTER UN
    ("ᛒ", "b", "2a"),  # ᛒ RUNIC LETTER BERKANAN BEORC BJARKAN B
    # ── Tier 2b — convention ────────────────────────────────────────────────
    ("щ", "w", "2b"),  # щ CYRILLIC SMALL LETTER SHCHA
    # U+00DF ß is deliberately absent — see the header of
    # data/confusables_attested.tsv. Folding it breaks German.
]


@pytest.mark.parametrize(("source", "target", "tier"), ATTESTED, ids=lambda v: v)
def test_attested_source_folds_to_its_target(source: str, target: str, tier: str) -> None:
    got = normalize_confusables(source, target_script="latin")
    assert got == target, (
        f"U+{ord(source):04X} ({unicodedata.name(source, '?')}, tier {tier}) folds to "
        f"{got!r}, expected {target!r}"
    )


def test_every_attested_fold_is_a_fixed_point() -> None:
    """The output must not itself fold further — #586's convergence, checked here."""
    for source, target, _ in ATTESTED:
        once = normalize_confusables(source, target_script="latin")
        assert normalize_confusables(once, target_script="latin") == once, (
            f"U+{ord(source):04X} folds to {once!r}, which folds again"
        )
        assert target.isascii()


def test_micro_sign_and_mu_agree() -> None:
    """µ U+00B5 and μ U+03BC must fold alike, or the result depends on the input's
    normalization form: NFKC maps µ to μ, so an NFKC pass would change the answer."""
    assert normalize_confusables("µ") == normalize_confusables("μ")


def test_the_cyrillic_target_is_untouched() -> None:
    """Seven of these sources already fold under ``target_script="cyrillic"``. The
    attested file sets the Latin column only; those mappings must survive."""
    for source, expected in [
        ("ʍ", "м"),  # U+028D → U+043C
        ("ĸ", "к"),  # U+0138 → U+043A
        ("ʜ", "н"),  # U+029C → U+043D
        ("ɢ", "ԍ"),  # U+0262 → U+050D CYRILLIC SMALL LETTER KOMI SJE
        ("ʙ", "в"),  # U+0299 → U+0432
        ("ƅ", "ь"),  # U+0185 → U+044C
        ("Ʌ", "Л"),  # U+0245 → U+041B
    ]:
        assert normalize_confusables(source, target_script="cyrillic") == expected
