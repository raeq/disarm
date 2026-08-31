"""#719, #722 and #737 — the second ASCII-producing step, and the exemption calibrated
on one block.

`canonicalize` has two steps that put ASCII into its output the input did not contain: the
leading NFKC, and the confusable fold. #633 wired the first in as `compat_fold`. The
second is the largest body of data disarm ships, and the aggregate detector never
consulted it — so `is_confusable("pɑypal")` was `True`, `canonicalize` returned `paypal`,
and `has_anomalies` said `False`.

All three issues extend #633's ASCII-letter-in-token gate and rest on the same
false-positive argument, which is why they land together (R7 in #762).
"""

from __future__ import annotations

import unicodedata

import pytest

from disarm import (
    canonicalize,
    find_confusables,
    has_anomalies,
    inspect_anomalies,
    is_confusable,
    normalize_confusables,
)


def _kinds(text: str) -> list[str]:
    return inspect_anomalies(text).kinds


def _detail(text: str) -> str | None:
    report = inspect_anomalies(text)
    return report.findings[0].detail if report.findings else None


# ── #737: the letters ────────────────────────────────────────────────────────

# Every row from the issue's table.
SUBSTITUTED = [
    ("pɑypal", "ɑ", "U+0251", "paypal"),
    ("þaypal", "þ", "U+00FE", "paypal"),
    ("gıthub", "ı", "U+0131", "github"),
    ("ʀeddit", "ʀ", "U+0280", "reddit"),
]


@pytest.mark.parametrize(
    ("text", "ch", "cp", "folds_to"), SUBSTITUTED, ids=[r[0] for r in SUBSTITUTED]
)
def test_a_substituted_latin_letter_is_reported(text: str, ch: str, cp: str, folds_to: str) -> None:
    """Single-script, so `mixed_script` cannot see it; no decomposition, so neither can
    `compat_fold`."""
    assert is_confusable(text)
    assert canonicalize(text) == folds_to
    assert _kinds(text) == ["confusable"]


@pytest.mark.parametrize(("text", "ch", "cp", "_f"), SUBSTITUTED, ids=[r[0] for r in SUBSTITUTED])
def test_the_detail_names_the_impersonated_letter(text: str, ch: str, cp: str, _f: str) -> None:
    """#737 §2: the way `mixed_script` names the two scripts."""
    detail = _detail(text)
    assert detail is not None
    assert detail.startswith(f"{ch} ({cp}) folds to ")


def test_the_two_rows_that_were_already_caught_are_unchanged() -> None:
    """The more specific kind still wins where one applies."""
    assert _kinds("ſteve") == ["compat_fold"]  # NFKC handles the long s
    assert _kinds("pаypal") == ["mixed_script"]  # Cyrillic а — two scripts


# ── #719: the punctuation ────────────────────────────────────────────────────

# The rows from the issue's table, with what only the fold produces.
FOLD_ONLY = [
    (0x2044, "FRACTION SLASH", "/"),
    (0x2215, "DIVISION SLASH", "/"),
    (0x2236, "RATIO", ":"),
    (0xA789, "MODIFIER LETTER COLON", ":"),
    (0x2250, "APPROACHES THE LIMIT", "="),
    (0x2216, "SET MINUS", "\\"),
]


@pytest.mark.parametrize(
    ("cp", "name", "produces"), FOLD_ONLY, ids=[f"U+{r[0]:04X}" for r in FOLD_ONLY]
)
def test_a_delimiter_the_fold_alone_produces_is_reported(cp: int, name: str, produces: str) -> None:
    text = f"ord{chr(cp)}end"
    assert produces not in text, "the input must not already carry the delimiter"
    assert produces in canonicalize(text), name
    assert _kinds(text) == ["confusable"], name


@pytest.mark.parametrize(("cp", "name", "_p"), FOLD_ONLY, ids=[f"U+{r[0]:04X}" for r in FOLD_ONLY])
def test_nfkc_alone_does_not_produce_it(cp: int, name: str, _p: str) -> None:
    """This is what makes it the fold's, not `compat_fold`'s."""
    assert unicodedata.normalize("NFKC", chr(cp)) == chr(cp), name


def test_the_composed_case_the_issue_calls_subtle() -> None:
    """`U+00BD` NFKC-decomposes to `1⁄2`, whose middle character is not ASCII.

    So the `compat_fold` gate is false, and the `/` appears only when the fold reaches
    that `U+2044` one step later. Neither step alone sees it; the composition does.
    """
    assert unicodedata.normalize("NFKC", "½") == "1⁄2"
    assert not unicodedata.normalize("NFKC", "½").isascii()
    assert canonicalize("ord½end") == "ord1/2end"
    assert _kinds("ord½end") == ["confusable"]


def test_the_contrast_row_still_reports_compat_fold() -> None:
    """`U+2A74` decomposes under NFKC, so #633's rule sees it — one code point, three
    delimiters, correctly reported all along."""
    assert _kinds("ord⩴end") == ["compat_fold"]


# ── #719 §3: the census, frozen ──────────────────────────────────────────────


def test_the_fold_only_ascii_census_is_frozen() -> None:
    """The split is derived from the shipped confusables table, so it moves when the
    table moves — which is exactly the data-change event #644/#645 treat as one.

    Recomputed here rather than pinned as a literal list, so the assertion is on the
    *shape* of the split and a table refresh reports a number rather than a diff.
    """
    fold_only = 0
    for cp in range(0x110000):
        if 0xD800 <= cp < 0xE000:
            continue
        ch = chr(cp)
        if ch.isascii():
            continue
        after_nfkc = unicodedata.normalize("NFKC", ch)
        folded = normalize_confusables(after_nfkc)

        # ASCII *punctuation*, which is what #719 counts: a letter folding to a letter is
        # #737's half and is not structure a downstream parser will act on.
        def punct(text: str) -> set[str]:
            return {c for c in text if c.isascii() and not c.isalnum() and not c.isspace()}

        if punct(folded) - punct(after_nfkc):
            fold_only += 1
    # The issue measured 232 against confusables 17.0.0. Asserted as a band rather than an
    # exact number: the class moves when the table moves, and an exact pin would fail on
    # every refresh without telling anyone anything — but it must stay large and non-empty.
    assert 150 <= fold_only <= 400, fold_only


# ── #722: the whole-token exemption, per block ───────────────────────────────

WHOLE_TOKEN_FOLDS_TO_PAYPAL = [
    ("𝐩𝐚𝐲𝐩𝐚𝐥", "Mathematical Alphanumeric — bold"),
    ("𝑝𝑎𝑦𝑝𝑎𝑙", "Mathematical Alphanumeric — italic"),
    ("𝚙𝚊𝚢𝚙𝚊𝚕", "Mathematical Alphanumeric — monospace"),
    ("𝕡𝕒𝕪𝕡𝕒𝕝", "Mathematical Alphanumeric — double-struck"),
    ("ⓟⓐⓨⓟⓐⓛ", "Enclosed Alphanumerics — circled"),
]


@pytest.mark.parametrize(
    ("text", "block"), WHOLE_TOKEN_FOLDS_TO_PAYPAL, ids=[r[1] for r in WHOLE_TOKEN_FOLDS_TO_PAYPAL]
)
def test_a_block_with_no_ordinary_whole_token_use_now_fires(text: str, block: str) -> None:
    """652 Mathematical Alphanumeric code points spell a word that folds to plain ASCII.

    A formula variable is not a word, and `ⓟⓐⓨⓟⓐⓛ` is not prose — so the `ＮＨＫ`
    argument, which is sound, does not reach these blocks.
    """
    assert canonicalize(text) == "paypal", block
    assert _kinds(text) == ["compat_fold"], block
    assert _detail(text) == "paypal", block


SPARED = [
    ("ｐａｙｐａｌ", "Halfwidth and Fullwidth — the #633 case itself"),
    ("ＮＨＫ", "Halfwidth and Fullwidth — a real broadcaster"),
    ("Ｑ＆Ａ", "Halfwidth and Fullwidth"),
    ("㎏", "CJK Compatibility — an ordinary unit"),
    ("㎞", "CJK Compatibility"),
    ("№", "Letterlike Symbols"),
]


@pytest.mark.parametrize(("text", "why"), SPARED, ids=[r[1] for r in SPARED])
def test_the_blocks_where_the_nhk_argument_holds_stay_spared(text: str, why: str) -> None:
    """#722 §3: the fullwidth half of the original exemption stays true."""
    assert not has_anomalies(text), why


def test_the_mixed_case_was_never_exempt() -> None:
    """It fires because it is mixed — nobody writes half a word in fullwidth."""
    assert _kinds("ａdmin") == ["compat_fold"]
    assert _detail("ａdmin") == "admin"


# ── the false-positive argument that gates all of it ─────────────────────────

MUST_STAY_CLEAN = [
    ("Привет", "every Cyrillic letter folds to Latin — this is the #545 over-flagging"),
    ("Ελλάδα", "so does Greek"),
    ("café", "the fold leaves accented Latin alone"),
    ("naïve", "likewise"),
    ("résumé", "likewise"),
    ("straße", "likewise"),
    ("日本語", "no Latin lookalike"),
    ("µF", "the micro sign IS how a microfarad is written"),
    ("kΩ", "and a kilohm"),
    ("IT-специалист", "two words with a boundary between them (#702)"),
    ("Сбербанк-Online", "likewise"),
    ("https://пример.рф/path", "likewise"),
]


@pytest.mark.parametrize(("text", "why"), MUST_STAY_CLEAN, ids=[r[0] for r in MUST_STAY_CLEAN])
def test_the_gate_holds(text: str, why: str) -> None:
    assert not has_anomalies(text), why


# ── #737 §3: the locator ─────────────────────────────────────────────────────


def test_the_locator_reports_character_offset_and_target() -> None:
    """`is_confusable` returns a bool and `normalize_confusables` returns the string;
    neither says *where*."""
    assert find_confusables("pɑypal") == [("ɑ", 1, "a")]


def test_the_locator_is_empty_when_nothing_folds() -> None:
    assert find_confusables("paypal") == []
    assert find_confusables("café") == []


def test_the_offset_is_anchored_in_the_callers_string() -> None:
    """Not in the composed intermediate — the same contract the sibling gives."""
    text = "aaaɑ"
    ((_ch, offset, _target),) = find_confusables(text)
    assert text[offset:].startswith("ɑ")


def test_the_two_locators_read_the_same_table_from_opposite_sides() -> None:
    """`find_unmapped_confusables` answers exposure; this one answers evidence."""
    from disarm import find_unmapped_confusables

    assert find_unmapped_confusables("pɑypal") == []
    assert [ch for ch, _offset, _target in find_confusables("pɑypal")] == ["ɑ"]
