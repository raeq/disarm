"""#700 and #643 — the detector could not see carriers the strip functions already remove.

Two independent gates kept the ASCII-smuggling channels invisible to `inspect_anomalies`:

1. **The carriers were not in the table.** `INVISIBLE` was eight characters. The Tags
   block, both variation-selector ranges, `U+2064` and `U+180E` were absent, while
   `src/invisibles.rs` already had a predicate for every one and `strip_*` already acted
   on them. The detector was the only place that did not know.
2. **A listed character still needed a letter beside it.** The neighbour rule reads the
   chars of the same whitespace token, so a run standing between two spaces could not
   fire even for a character that *was* listed — and a standalone run is the shape a
   pasted payload has.

Fixing either alone leaves the other open, which is why both are here.
"""

from __future__ import annotations

import unicodedata

import pytest

from disarm import has_anomalies, inspect_anomalies

TAGS = "".join(chr(0xE0000 + ord(c)) for c in "tracked-by:acct-99213")
VS = "".join(chr(0xE0100 + i) for i in (7, 8))
# A UNIFORM run, so `U+200B ×16` says exactly what it means. The bit-encoded variant —
# ZWSP for 0, ZWNJ for 1 — is the realistic payload shape and is covered separately by
# `test_a_mixed_carrier_run_reports_the_longest_same_class_stretch`, because there the
# reported code point is the start of the longest *same-class* stretch rather than the
# whole run.
ZW_RUN = "\u200b" * 16
ZW_BITS = "".join(
    chr(0x200B if bit == "0" else 0x200C)
    for bit in format(ord("h"), "08b") + format(ord("i"), "08b")
)

# Every row from #700's table, with what the matching strip function does to it.
SMUGGLING = [
    ("tags, inline", "Hello world" + TAGS),
    ("tags, own token", "Hello " + TAGS + " world"),
    ("variation selectors", "Hello " + VS + " world"),
    ("zero-width, inline", "Hello" + ZW_RUN + "world"),
    ("zero-width, own token", "Hello " + ZW_RUN + " world"),
]


@pytest.mark.parametrize(("label", "text"), SMUGGLING, ids=[r[0] for r in SMUGGLING])
def test_a_smuggling_carrier_is_reported(label: str, text: str) -> None:
    report = inspect_anomalies(text)
    assert report.anomalous, label
    # `invisible` stays, whatever else fires. #701 added `smuggled` for runs that decode
    # to readable text, and it leads the list when it does — but by ORDER, not by
    # suppression, so this assertion is the one that guards the caller who already
    # matches on `invisible`.
    assert "invisible" in report.kinds, label
    if "smuggled" in report.kinds:
        assert report.kinds[0] == "smuggled", f"{label}: a decode must outrank"


# ── #643: the fillers ────────────────────────────────────────────────────────

# `Lo`/`So`, not `Cf`, so no format-character predicate covered them. These are the
# standard characters behind invisible usernames on Discord, Twitter and similar.
FILLERS = [
    ("ㅤ", "HANGUL FILLER"),
    ("ᅟ", "HANGUL CHOSEONG FILLER"),
    ("ᅠ", "HANGUL JUNGSEONG FILLER"),
    ("ﾠ", "HALFWIDTH HANGUL FILLER"),
    ("⠀", "BRAILLE PATTERN BLANK"),
]


@pytest.mark.parametrize(("ch", "name"), FILLERS, ids=[f"U+{ord(r[0]):04X}" for r in FILLERS])
def test_a_filler_is_reported_the_way_zwsp_already_was(ch: str, name: str) -> None:
    """`ad\\u3164min` renders as `admin`; `ad\\u200bmin` was reported and this was not."""
    assert has_anomalies(f"ad{ch}min"), name
    assert inspect_anomalies(f"ad{ch}min").kinds == ["invisible"], name
    assert has_anomalies("ad\u200bmin")  # the control case, unchanged


def test_u180e_is_no_longer_reported_as_a_script_it_is_not() -> None:
    """`U+180E` sits in the Mongolian block, so the detector named a script nobody can see.

    Not in either issue: it fired as `mixed_script` rather than `invisible`, which is the
    same defect #605 fixed in `is_suspicious_hostname` by stripping invisibles *before*
    script analysis. The detector never got that fix.
    """
    assert inspect_anomalies("ad\u180emin").kinds == ["invisible"]


# ── #700 §2: the run rule, and #700 §4: the run is what gets reported ─────────


@pytest.mark.parametrize(
    ("ch", "below", "at"),
    [
        ("\U000e0074", 0, 1),  # a tag character: one is not ordinary anything
        ("︇", 1, 2),  # a variation selector: one after a base is presentation
        ("\u200b", 7, 8),  # zero-width: well above orthography, below two smuggled letters
    ],
    ids=["tag", "variation-selector", "zero-width"],
)
def test_the_run_threshold_is_where_the_docs_say(ch: str, below: int, at: int) -> None:
    """Standalone runs, with no letter in the token to trip the neighbour rule."""
    if below:
        assert not has_anomalies(f"Hello {ch * below} world"), f"{below} should be below"
    assert has_anomalies(f"Hello {ch * at} world"), f"{at} should fire"


def test_the_finding_names_the_run_not_one_character_of_it() -> None:
    """#700 §4: a detail naming `U+200B` when sixteen are in sequence understates it."""
    report = inspect_anomalies("Hello " + ZW_RUN + " world")
    assert report.findings[0].detail == f"U+200B ×{len(ZW_RUN)}"


def test_a_mixed_carrier_run_reports_the_longest_same_class_stretch() -> None:
    """A bit-encoded payload alternates ZWSP and ZWNJ, and both are the same class.

    The run counter groups by *class*, not by code point, so the whole alternating
    stretch is one run and the reported code point is the one that starts it. Asserted
    rather than left implied: `U+200B ×16` on an alternating input would read as sixteen
    consecutive ZWSP, which is not what the input was.
    """
    report = inspect_anomalies("Hello " + ZW_BITS + " world")
    # By kind, not by position: `ZW_BITS` spells "hi", so since #701 a `smuggled` finding
    # leads the list. This assertion is about what the `invisible` finding says.
    invisible = next(f for f in report.findings if f.kind == "invisible")
    assert invisible.detail == f"U+{ord(ZW_BITS[0]):04X} \u00d7{len(ZW_BITS)}"
    assert len(set(ZW_BITS)) == 2, "the point of this case is that the run is not uniform"


@pytest.mark.parametrize("ch", ["\u00ad", "͏"], ids=["soft-hyphen", "CGJ"])
def test_a_run_only_carrier_is_spared_singly_and_caught_in_bulk(ch: str) -> None:
    """Both have a legitimate use *between letters*, which is where the neighbour rule fires.

    So they are carriers for the run rule only: one is hyphenation or a normalization
    boundary, nine in a row is neither.
    """
    assert not has_anomalies(f"ad{ch}min")
    assert has_anomalies(f"ad{ch * 9}min")


# ── #700 §3: the exemptions that distinguish this from "flag every invisible" ─

MUST_STAY_CLEAN = [
    ("emoji ZWJ sequence", "family \U0001f468\u200d\U0001f469\u200d\U0001f467 here"),
    ("Persian ZWNJ", "می\u200cروم"),
    ("CJK plus Latin", "これはCD-ROMです"),
    (
        "Scotland flag",
        "flag \U0001f3f4\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f here",
    ),
    ("England flag", "\U0001f3f4\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f"),
    ("Wales flag", "\U0001f3f4\U000e0067\U000e0062\U000e0077\U000e006c\U000e0073\U000e007f"),
    ("emoji presentation VS16", "check ✔️ here"),
    ("plain text", "the quick brown fox"),
]


@pytest.mark.parametrize(("label", "text"), MUST_STAY_CLEAN, ids=[r[0] for r in MUST_STAY_CLEAN])
def test_the_exemptions_hold(label: str, text: str) -> None:
    assert not has_anomalies(text), label


def test_a_flag_base_with_the_wrong_tail_is_not_a_flag() -> None:
    """The allowlist is the three RGI payloads, not the region-subtag *shape*.

    `crate::invisibles` already drew that line for the stripper; the detector reuses it
    rather than restating it, which is the drift #700 §1 is about.
    """
    fake = "\U0001f3f4" + "".join(chr(0xE0000 + ord(c)) for c in "usca") + "\U000e007f"
    assert has_anomalies(f"flag {fake} here")


# ── #643 §2/§3: the key-builder decision, recorded rather than left arbitrary ─


def test_the_collision_split_follows_normalization() -> None:
    """#643 calls the split arbitrary. Measured, it follows what normalization does.

    The four Hangul fillers collide with `admin` because NFKC or `transliterate` *deletes*
    them — they carry no width. `U+2800` and `U+1680` resolve to a **space**, so
    `ad<X>min` becomes `ad min`, which is genuinely different text from `admin`. That is
    the same answer an ordinary space gets, and colliding it would mean colliding every
    space.

    Asserted as a negative so the decision is recorded rather than rediscovered (§3).
    """
    from disarm import search_key

    for ch in ("ㅤ", "ᅟ", "ᅠ", "ﾠ"):
        assert search_key(f"ad{ch}min") == search_key("admin"), f"U+{ord(ch):04X}"
    for ch in ("⠀", " "):
        assert search_key(f"ad{ch}min") == "ad min", f"U+{ord(ch):04X}"
        assert search_key(f"ad{ch}min") != search_key("admin"), f"U+{ord(ch):04X}"


def test_ogham_space_is_a_known_negative_for_detection() -> None:
    """`U+1680` is `Zs` — a token separator everywhere in this library.

    The neighbour rule reads the chars of one whitespace token, so a separator can never
    be inside one. It also renders visibly in most fonts, which is why #643 calls it the
    weakest of the set. Recorded rather than left to be rediscovered.
    """
    assert unicodedata.category(" ") == "Zs"
    assert " ".isspace()
    assert not has_anomalies("ad min")


# ── #643 adjacent: the comment and the check had drifted ─────────────────────


def test_a_latin_majority_embedding_is_flagged() -> None:
    """`bidi_spares_marks_and_embeddings` documented a condition it did not implement.

    Its comment read "an LRE..PDF embedding around RTL text (*no Latin majority*) is
    benign", and a Latin-majority embedding was spared identically — the Trojan Source
    construction with the older embedding operators in place of the isolates.
    """
    assert has_anomalies("\u202bif (isAdmin) { grant(); }\u202c")


def test_the_embedding_carve_out_still_spares_real_rtl() -> None:
    """The half of that sentence which was right stays right."""
    assert not has_anomalies("\u202bمرحبا\u202c")
    assert not has_anomalies("hello\u200fworld")  # a bare directional mark carries no scope
