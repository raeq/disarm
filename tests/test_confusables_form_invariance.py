"""#475: the confusables API must be invariant to its input's normal form.

`normalize_confusables` / `is_confusable` map and detect via the per-code-point TR39
table with **no normalization pass**. The bundled table has an aggressive
*precomposed* homoglyph entry (`ї`→`i`, `ç`→`c`) that drops the diacritic, but on the
*decomposed* (NFD) sequence it only maps the base and the combining mark survives —
so a homoglyph folds to clean ASCII in NFC but keeps a mark in NFD, and detection
flips (NFC `True` → NFD `False`). An attacker decomposes the homoglyph to walk past
the recovery / detection.

Scope (determined by sweeping every public text entry point):
  * IN SCOPE — `normalize_confusables` (fold) and `is_confusable` (detect): the
    confusables primitives, which do not normalize.
  * NOT the bug — form-preserving transforms (`fold_case`, `strip_*`, `escape_html`,
    `collapse_whitespace`, `is_normalized`): they correctly preserve composition and
    are not canonicalization primitives.
  * ALREADY ROBUST (no-regression baseline, asserted below) — the NFKC-first presets
    (`canonicalize`, `strip_obfuscation`, the `*_key` presets): they normalize first.
  * SEPARATE finding (tracked elsewhere, not asserted here) — `transliterate` /
    `slugify` have a *phonetic* form-dependence (`ї`→"yi" vs "i"); different mechanism.

These FAIL until the confusables API normalizes (canonically) first.
"""

from __future__ import annotations

import unicodedata

import pytest

import disarm

# Cross-script homoglyphs that the table folds aggressively in precomposed form: the
# 8 "clean" cases (NFC → pure ASCII) plus a couple more. Their NFD splits base+mark.
HOMOGLYPHS = [
    "ї",  # ї CYRILLIC SMALL LETTER YI        -> i
    "ç",  # ç LATIN SMALL LETTER C WITH CEDILLA-> c
    "ί",  # ί GREEK SMALL LETTER IOTA W/ TONOS -> i
    "ϊ",  # ϊ GREEK IOTA WITH DIALYTIKA        -> i
    "ό",  # ό GREEK OMICRON WITH TONOS         -> o
    "Ǿ",  # Ǿ LATIN O WITH STROKE AND ACUTE    -> O
    "إ",  # إ ARABIC ALEF WITH HAMZA BELOW     -> l
]

FORMS = ["NFC", "NFD", "NFKD"]


def _forms(ch: str) -> list[str]:
    return [unicodedata.normalize(f, ch) for f in FORMS]


@pytest.mark.parametrize("ch", HOMOGLYPHS, ids=[f"U+{ord(c):04X}" for c in HOMOGLYPHS])
def test_normalize_confusables_is_form_invariant(ch: str) -> None:
    """The recovered fold must not depend on the input's normal form."""
    outs = {disarm.normalize_confusables(v) for v in _forms(ch)}
    assert len(outs) == 1, f"normalize_confusables not form-invariant on {ch!r}: {outs}"


@pytest.mark.parametrize("ch", HOMOGLYPHS, ids=[f"U+{ord(c):04X}" for c in HOMOGLYPHS])
def test_is_confusable_is_form_invariant(ch: str) -> None:
    """Detection must not be evadable by decomposing the homoglyph."""
    outs = {disarm.is_confusable(v) for v in _forms(ch)}
    assert len(outs) == 1, f"is_confusable not form-invariant on {ch!r}: {outs}"


def test_confusables_divergence_set_is_broad() -> None:
    """Scope breadth: many BMP code points diverge between NFC and NFD today (the
    issue counts ~13,227). Pin that the fix covers a representative sweep, not just
    the curated homoglyphs above."""
    divergent = [
        cp
        for cp in range(0x80, 0x2500)
        if (ch := chr(cp))
        and disarm.normalize_confusables(unicodedata.normalize("NFC", ch))
        != disarm.normalize_confusables(unicodedata.normalize("NFD", ch))
    ]
    # Pre-fix this is a large set; post-fix it must be empty (form-invariant).
    assert divergent == [], f"{len(divergent)} code points still diverge NFC vs NFD"


# ── No-regression baseline: the NFKC-first presets are ALREADY form-invariant. ──

NFKC_PRESETS = [
    ("canonicalize", disarm.canonicalize),
    ("canonicalize_strict", disarm.canonicalize_strict),
    ("strip_obfuscation", disarm.strip_obfuscation),
    ("search_key", disarm.search_key),
    ("sort_key", disarm.sort_key),
    ("catalog_key", disarm.catalog_key),
]


@pytest.mark.parametrize("name,fn", NFKC_PRESETS)
@pytest.mark.parametrize("ch", HOMOGLYPHS, ids=[f"U+{ord(c):04X}" for c in HOMOGLYPHS])
def test_nfkc_presets_stay_form_invariant(name: str, fn: object, ch: str) -> None:
    outs = {fn(v) for v in _forms(ch)}
    assert len(outs) == 1, f"{name} regressed form-invariance on {ch!r}: {outs}"
