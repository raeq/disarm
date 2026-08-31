"""#724 and #741 — two classes the detector spared on grounds that do not hold.

- **#724** measured the *count* of combining marks and never the category. One enclosing
  mark per base is below every threshold disarm has, so a string where every letter
  carries a `COMBINING ENCLOSING CIRCLE` was clean at every surface — while
  `strip_obfuscation` removed it.
- **#741** spared bare directional marks on false-positive grounds. Measured against
  UAX #9 with `unicode-bidi`, two of them still reorder rendered text inside pure-Latin
  prose.

Invisible characters are written as escapes, per #802.
"""

from __future__ import annotations

import unicodedata

import pytest

from disarm import canonicalize, has_anomalies, inspect_anomalies, is_zalgo, strip_obfuscation


def _kinds(text: str) -> list[str]:
    return inspect_anomalies(text).kinds


# ── #741: the marks that reorder ─────────────────────────────────────────────

RLM = "\u200f"
ALM = "\u061c"
LRM = "\u200e"

# Every row from the issue's table, with what python-bidi renders it as.
REORDERS = [
    (f"Transfer {RLM}100 200 300 to Bob", "Transfer 300 200 100 to Bob", "RLM"),
    (f"invoice {RLM}2024 07 15", "invoice 15 07 2024", "RLM"),
    (f"acct {ALM}4321-9876", "acct 9876-4321", "ALM"),
]


@pytest.mark.parametrize(
    ("text", "renders_as", "mark"), REORDERS, ids=[r[2] + ":" + r[0][:14] for r in REORDERS]
)
def test_a_mark_that_reorders_is_reported(text: str, renders_as: str, mark: str) -> None:
    """Boucher et al., *Bad Characters* Table I, reached with a spared control."""
    assert _kinds(text) == ["bidi"], mark
    # `canonicalize` already removed it; the gap was that nothing *said* so.
    assert canonicalize(text) == text.replace(RLM, "").replace(ALM, "")


def test_the_override_row_still_fires_as_it_always_did() -> None:
    """The contrast row from the issue: the same attack with an override."""
    assert _kinds("Transfer \u202e003 002 001\u202c to Bob") == ["bidi"]


def test_lrm_stays_spared_because_it_does_not_reorder() -> None:
    """The issue checked the rest of the family before filing.

    LRE, LRO, LRI, FSI and LRM produced no reordering over the carriers tried, so the
    finding is `RLM` and `ALM` — not "the spared set is wrong".
    """
    assert _kinds(f"Transfer {LRM}100 200 300 to Bob") == []


@pytest.mark.parametrize(
    ("text", "why"),
    [
        (f"שלום {RLM}עולם", "RTL prose"),
        (f"#hashtag{RLM}", "a hashtag"),
        (f"Transfer {RLM}one two three", "a mark before words, not a number run"),
        (f"{RLM}مرحبا", "Arabic with a leading mark"),
    ],
    ids=["rtl-prose", "hashtag", "before-words", "arabic"],
)
def test_the_narrow_predicate_does_not_fire_on_the_spared_cases(text: str, why: str) -> None:
    """#741 §2: a mark immediately before a run of European numbers, and only that.

    The carrier is always a number run — an account number, an amount, a date. Each group
    keeps its internal digits and the groups swap places, which is what makes the
    rendering stay plausible. Adding the mark to the general list instead would fire on
    every row here.
    """
    assert not has_anomalies(text), why


# ── #724: the category, not the count ────────────────────────────────────────

CIRCLE = "\u20dd"


@pytest.mark.parametrize("per_base", [1, 2, 3, 4], ids=lambda n: f"{n}-marks")
def test_an_encircled_word_is_reported_at_every_count(per_base: int) -> None:
    """One per base was below every threshold; four was above the zalgo one.

    The class is now reported at all four, and as `enclosing_mark` rather than `zalgo` —
    a different fact deserves a different finding.
    """
    text = "".join(ch + CIRCLE * per_base for ch in "Ignore")
    assert _kinds(text) == ["enclosing_mark"], per_base


def test_the_count_based_rule_never_saw_the_single_mark_case() -> None:
    """`is_zalgo` fires above three, so one per base could not register."""
    one = "".join(ch + CIRCLE for ch in "Ignore")
    assert not is_zalgo(one)
    assert _kinds(one) == ["enclosing_mark"]


def test_strip_obfuscation_already_removed_it() -> None:
    """The asymmetry is what made this a reporting gap rather than a stripping one."""
    text = "".join(ch + CIRCLE for ch in "Ignore")
    assert strip_obfuscation(text) == "Ignore"


def test_the_finding_names_the_mark_and_the_count() -> None:
    text = "".join(ch + CIRCLE for ch in "Ignore")
    assert inspect_anomalies(text).findings[0].detail == "U+20DD ×6"


# ── #724 §2: the exemptions ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("1\ufe0f\u20e3", "a keycap: the variation selector makes it RGI"),
        ("2\ufe0f\u20e30\ufe0f\u20e32\ufe0f\u20e34\ufe0f\u20e3", "a keycap year"),
        ("#\ufe0f\u20e3", "a keycap hash"),
    ],
    ids=["keycap-1", "keycap-2024", "keycap-hash"],
)
def test_a_keycap_sequence_is_exempt(text: str, why: str) -> None:
    assert not has_anomalies(text), why


def test_a_bare_keycap_mark_is_not_a_keycap() -> None:
    """`U+20E3` with no `U+FE0F` before it is not an RGI sequence.

    The same distinction `crate::invisibles` draws for a subdivision flag: the shape is
    not enough, the sequence has to be well-formed.
    """
    assert _kinds("1\u20e32\u20e3") == ["enclosing_mark"]


def test_cyrillic_enclosing_marks_on_a_cyrillic_base_are_exempt() -> None:
    """`U+0488` and its relatives are historic Cyrillic notation, not a disguise."""
    assert not has_anomalies("а\u0488б\u0489")


@pytest.mark.parametrize(
    ("text", "block"),
    [
        ("\u0430\u0301\u0488\u0431\u0301\u0489", "an intervening acute before the mark"),
        ("\u0501\u0488\u0503\u0489", "Cyrillic Supplement"),
        ("\u2de0\u0488\u2de1\u0489", "Cyrillic Extended-A"),
        ("\ua640\u0488\ua641\u0489", "Cyrillic Extended-B"),
    ],
    ids=["acute-between", "supplement", "ext-a", "ext-b"],
)
def test_the_base_walk_finds_the_real_base(text: str, block: str) -> None:
    """Two holes the first draft had, both reported by review on #817.

    It skipped only prior *enclosing* marks, so an intervening `U+0301` was read as the
    base; and it checked a hand-written Cyrillic range that missed Supplement and
    Extended-C. The script now comes from `detect_char_script`, the one resolver —
    restating a range the library already resolves is the failure #774 was about.
    """
    assert not has_anomalies(text), block


def test_cyrillic_extended_c_is_a_known_negative() -> None:
    """`U+1C80` is Cyrillic and `detect_scripts` does not say so, so this still fires.

    The block table in `src/scripts.rs` covers Cyrillic, Supplement, Extended-A and
    Extended-B and omits Extended-C (`U+1C80`-`U+1C8F`, 11 assigned) and Extended-D
    (`U+1E030`-`U+1E08F`, 63). Teaching it those two changes `detect_scripts` for 74 code
    points, which reaches `mixed_script`, `bidi_mixed` and `is_suspicious_hostname` — the
    same class of change as #774, and its own issue rather than a drive-by here.

    Asserted so it is a recorded limit rather than a surprise, and so closing the gap
    fails this test loudly.
    """
    from disarm import detect_scripts

    assert detect_scripts("\u1c80") == []
    # Two marks, since one is never a finding — see the test above.
    assert _kinds("\u1c80\u0488\u1c81\u0489") == ["enclosing_mark"]


def test_the_same_marks_on_a_latin_base_are_not() -> None:
    """On Latin they are exactly the disguise the rule exists for."""
    assert _kinds("a\u0488b\u0489") == ["enclosing_mark"]


def test_a_single_enclosing_mark_is_not_a_finding() -> None:
    """Two are required: encircling one character is something someone may have typed;
    encircling every letter of a word is not something any orthography does."""
    assert not has_anomalies("a\u20dd")


@pytest.mark.parametrize(
    "text",
    ["café", "Việt", "naïve", "مرحبا", "straße"],
)
def test_ordinary_accents_are_untouched(text: str) -> None:
    """#429's decision stands: `strip_zalgo` keeps two marks because `ệ` needs them."""
    assert not has_anomalies(text)


def test_no_enclosing_mark_is_an_accent() -> None:
    """The premise the rule rests on, asserted rather than assumed."""
    from disarm import strip_accents

    for cp in range(0x110000):
        if unicodedata.category(chr(cp)) != "Me":
            continue
        # An accent is a mark `strip_accents` removes from a base to leave the letter.
        # An enclosing mark has no such reading — it encircles rather than modifies.
        # `strip_accents` is NFD -> drop marks -> NFC, so it removes them like any
        # other mark. The point is the reverse: no `Me` mark *modifies* its base the way
        # an accent does, so preserving one preserves a disguise rather than a letter.
        assert strip_accents("a" + chr(cp)) == "a"


# ── #724 §3: the decision, recorded ──────────────────────────────────────────


def test_canonicalize_still_preserves_enclosing_marks() -> None:
    """Decided and written down rather than left implied.

    Stripping `Me` in `canonicalize` would not weaken #429 — no enclosing mark is an
    accent — but it moves output for 13 code points, which is a breaking change and a
    decision of its own. Until then: screen with `inspect_anomalies`, clean with
    `strip_obfuscation`, and do not read a clean `canonicalize` as a claim that the text
    carries no enclosing mark.
    """
    text = "".join(ch + CIRCLE for ch in "Ignore")
    assert canonicalize(text) != "Ignore"
    assert CIRCLE in canonicalize(text)
    assert strip_obfuscation(text) == "Ignore"
    assert _kinds(text) == ["enclosing_mark"]
