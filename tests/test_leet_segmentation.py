"""#726, #750 and #752 — the two lexicon-gated branches, and what each could not see.

All three are `src/anomalies.rs`, and all three are the same shape: a branch that works
on the input it was designed for and has a blind spot one character wide.

- **#726** — `!` is in `WRAP` *and* in the leet alphabet, so the trim ate the substitution.
- **#750** — `seg_word` knew three separators; Unicode has two whole categories for the job.
- **#752** — one leet substitute inside a segmented word defeated both branches, because
  each catches only its own half.

The three density gates are unchanged, which is the acceptance criterion rather than a
side note: nothing here loosens `seps >= 2`, the `5*seps >= 3*(letters-1)` ratio, or the
single-letter-fragment requirement.
"""

from __future__ import annotations

import pytest

from disarm import inspect_anomalies

LEXICON = ["ignore", "admin", "password", "system", "free", "confirm", "viagra"]


def _kinds(text: str) -> list[str]:
    return inspect_anomalies(text, lexicon=LEXICON).kinds


def _detail(text: str) -> str | None:
    report = inspect_anomalies(text, lexicon=LEXICON)
    return report.findings[0].detail if report.findings else None


# ── #726: the character that is both punctuation and a substitute ────────────


def test_a_leading_leet_substitute_in_wrap_is_no_longer_trimmed_away() -> None:
    """`1gn0r3` was caught and `!gn0r3` was clean — the same word, one character apart."""
    assert _detail("1gn0r3") == "ignore"
    assert _detail("!gn0r3") == "ignore"


def test_the_trim_still_does_its_real_job() -> None:
    """`4dm1n!` decodes on the first pass, so that trailing `!` is punctuation.

    The retry runs second precisely so this stays true.
    """
    assert _detail("4dm1n!") == "admin"
    assert _detail("adm!n") == "admin"
    assert _detail("4dm!n") == "admin"


def test_the_control_case_was_never_broken() -> None:
    """`$` is a substitute that is NOT in `WRAP`, so a leading one always survived."""
    assert _detail("$ystem") == "system"
    assert _detail("p@ssw0rd") == "password"


@pytest.mark.parametrize(
    ("token", "decodes_to"),
    [("gn0r3!", "gnorei"), ("!dm1n", "idmin")],
)
def test_the_rows_that_stay_clean_decode_to_nothing(token: str, decodes_to: str) -> None:
    """#726's table lists these beside `!gn0r3`; only one of the three is a word.

    The trim did eat a substitute in all three, but `!` maps to `i`, so `gn0r3!` is
    `gnorei` and `!dm1n` is `idmin` — neither is `ignore` or `admin`. Clean is the correct
    answer, and `nearest()`'s single-edit rescue declines them too because it requires a
    six-character decode. Asserted so the distinction is recorded rather than read as an
    unfixed defect.
    """
    assert decodes_to not in LEXICON
    assert _kinds(token) == []


# ── #750: the separator set ──────────────────────────────────────────────────

# `canonicalize` rewrites these two to `=`, which was not recognised either — so the fold
# moved the attack from one unrecognised separator to another.
REWRITTEN_BY_THE_FOLD = [0x2E40, 0x30A0]

# The sixteen #750 measured as silent on every path.
PREVIOUSLY_SILENT = [
    0x2014,
    0x2015,
    0x203F,
    0x2040,
    0x2054,
    0x2E17,
    0x2E3A,
    0x2E3B,
    0x2E40,
    0x2E5D,
    0x301C,
    0x3030,
    0x30A0,
    0xFE31,
    0xFE58,
    0x10EAD,
]


@pytest.mark.parametrize("cp", PREVIOUSLY_SILENT, ids=[f"U+{cp:04X}" for cp in PREVIOUSLY_SILENT])
def test_a_previously_silent_joiner_now_reports(cp: int) -> None:
    """The fully-atomized token is the exact shape the branch is documented to catch."""
    assert _detail(chr(cp).join("confirm")) == "confirm"


@pytest.mark.parametrize(
    "cp", REWRITTEN_BY_THE_FOLD, ids=[f"U+{cp:04X}" for cp in REWRITTEN_BY_THE_FOLD]
)
def test_the_ones_canonicalize_rewrites_are_caught_before_the_fold(cp: int) -> None:
    assert _detail(chr(cp).join("confirm")) == "confirm"


def test_the_visually_identical_pair_now_agrees() -> None:
    """`U+2010 HYPHEN` and `U+002D HYPHEN-MINUS` render the same and disagreed."""
    assert _detail("-".join("confirm")) == "confirm"
    assert _detail("‐".join("confirm")) == "confirm"


def test_the_two_that_always_worked_still_work() -> None:
    assert _detail("-".join("confirm")) == "confirm"
    assert _detail("_".join("confirm")) == "confirm"


# ── #752: the composition ────────────────────────────────────────────────────


def test_each_half_was_already_caught() -> None:
    """Neither branch was broken; neither owned the composed form."""
    assert _detail("p4ssw0rd") == "password"
    assert _detail("p.a.s.s.w.o.r.d") == "password"


@pytest.mark.parametrize(
    "token",
    [
        "p.4.s.s.w.o.r.d",
        "p.a.s.s.w.0.r.d",
        "p.4.s.s.w.0.r.d",
        "p.a.5.s.w.o.r.d",
        "p.a.s.s.w.o.r.d",
    ],
)
def test_a_substituted_letter_inside_a_segmented_word_is_caught(token: str) -> None:
    """Every substitutable position in `password` screened clean.

    `seg_word` rebuilt the candidate with `filter(is_alphabetic)`, so `4` and `0` were
    silently *dropped* rather than demangled: `psswrd` and `passwrd` are in no lexicon.
    """
    assert _detail(token) == "password"


def test_every_substitutable_position_is_covered() -> None:
    """Derive the positions rather than trusting the count.

    #752 says seven. Measured, `password` has **four**: `a`, both `s`, and `o` are the
    only letters `leet_sub` has an inverse for — `p`, `w`, `r` and `d` have none. The set
    is derived here so the assertion cannot drift from the demangler's actual alphabet.
    """
    #: The demangler's alphabet, inverted. Only these letters can be substituted.
    subs = {"a": "4", "s": "5", "o": "0", "e": "3", "i": "1", "t": "7", "b": "8", "g": "9"}
    positions = [i for i, ch in enumerate("password") if ch in subs]
    assert positions == [1, 2, 3, 5], positions
    for i in positions:
        letters = list("password")
        letters[i] = subs[letters[i]]
        assert _detail(".".join(letters)) == "password", f"position {i}"


# ── the gates that must not have moved ───────────────────────────────────────


def test_the_density_gate_still_rejects_a_sparse_split() -> None:
    """`seps >= 2` and the 5:3 ratio are unchanged — the acceptance criterion."""
    assert _kinds("pass.word") == []
    assert _kinds("con.firm") == []


def test_a_multi_letter_fragment_still_disqualifies() -> None:
    """`seg_word` is for single-letter splitting; `co.nf.irm` is not that shape."""
    assert _kinds("co.nf.irm") == []


@pytest.mark.parametrize("sep", [".", "-", "_"], ids=["dot", "hyphen", "underscore"])
def test_a_non_word_is_still_clean_however_it_is_split(sep: str) -> None:
    """No lexicon word, no segmentation finding — whatever the separator."""
    assert _kinds(sep.join("qxzvbn")) == []


@pytest.mark.parametrize("sep", ["‐", "⹀"], ids=["U+2010", "U+2E40"])
def test_a_non_ascii_joiner_reports_confusable_when_there_is_no_word(sep: str) -> None:
    """Not segmentation — there is no word — but not clean either (#719).

    `U+2010` folds to `-` and `U+2E40` to `=`, so the fold puts ASCII into the output that
    the input did not carry. `segmentation` wins when a word reassembles, because it is
    the more specific finding; this is what is left when one does not.
    """
    assert _kinds(sep.join("qxzvbn")) == ["confusable"]


def test_an_ordinary_hyphenated_word_is_not_a_finding() -> None:
    assert _kinds("well-known") == []
    assert _kinds("state-of-the-art") == []
