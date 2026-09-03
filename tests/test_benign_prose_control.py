"""A negative control: prose that is out of copyright must not trip any detector (#957).

`is_confusable` returned `True` for any text containing `"`, `` ` `` or `|`, because all
three are TR39 confusable *sources* — the table folds them to `''`, `'` and `l`. That is
correct for the fold and deliberate (#725), and it made the detector fire on 588 of the
1,342 pure-ASCII lines of this repository's own prose. A screen built on it said *yes* to
every quoted sentence and every JSON document.

This file is the control that would have caught it. The passages are public-domain English
prose — the plainest possible input — and no detector may fire on any of them.

**Both halves are asserted.** The fold still rewrites `"`, `` ` `` and `|`, because #725's
contract for the transforming surfaces is unchanged; only the *detectors* stop counting
them. A test that checked one without the other would pass if the rows were deleted, which
is the fix this issue did not want.
"""

from __future__ import annotations

import pytest

import disarm

#: Out of copyright by any reckoning, and chosen for punctuation rather than for prose:
#: between them these carry the straight quote, the apostrophe, the semicolon and the
#: double-dash that ordinary writing is full of.
PASSAGES = {
    "Austen, Pride and Prejudice (1813)": (
        '"My dear Mr. Bennet," said his lady to him one day, '
        '"have you heard that Netherfield Park is let at last?"'
    ),
    "Melville, Moby-Dick (1851)": (
        "Call me Ishmael. Some years ago--never mind how long precisely--having little "
        "or no money in my purse, and nothing particular to interest me on shore, I "
        "thought I would sail about a little and see the watery part of the world."
    ),
    "Carroll, Alice's Adventures in Wonderland (1865)": (
        '"and what is the use of a book," thought Alice, "without pictures or conversations?"'
    ),
    "Dickens, A Tale of Two Cities (1859)": (
        "It was the best of times, it was the worst of times; it was the age of wisdom, "
        "it was the age of foolishness."
    ),
}

#: The other two characters do not occur in Victorian prose, and they are exactly where a
#: technical writer lives — a shell pipeline and a Markdown table. Same control, same rule.
TECHNICAL = {
    "a shell pipeline": "grep -c '<loc>' sitemap.xml | wc -l",
    "a Markdown table row": "| `strip_zalgo` | `int \\| None` | `None` | cap combining marks |",
    "a JSON document": '{"user": "alice", "role": "admin", "note": "he said \\"hi\\""}',
}

DETECTORS = {
    "has_anomalies": disarm.has_anomalies,
    "is_confusable": disarm.is_confusable,
    "is_mixed_script": disarm.is_mixed_script,
    "is_zalgo": disarm.is_zalgo,
    "has_bidi_conflict": disarm.has_bidi_conflict,
    "has_bidi_control": disarm.has_bidi_control,
}

ALL_TEXT = {**PASSAGES, **TECHNICAL}


def test_the_control_is_not_vacuous() -> None:
    """A corpus carrying none of the three characters would prove nothing."""
    present = {c for text in ALL_TEXT.values() for c in text if c in '"`|'}
    assert present == {'"', "`", "|"}, present


@pytest.mark.parametrize(
    "source", sorted(ALL_TEXT), ids=lambda s: s.split(",")[0].replace(" ", "_")
)
@pytest.mark.parametrize("detector", sorted(DETECTORS))
def test_no_detector_fires(detector: str, source: str) -> None:
    assert DETECTORS[detector](ALL_TEXT[source]) is False, (detector, source)


@pytest.mark.parametrize(
    "source", sorted(ALL_TEXT), ids=lambda s: s.split(",")[0].replace(" ", "_")
)
def test_inspect_anomalies_reports_nothing(source: str) -> None:
    report = disarm.inspect_anomalies(ALL_TEXT[source])
    assert not report.anomalous
    assert not report.findings
    assert not report.kinds


@pytest.mark.parametrize("char", ['"', "`", "|"])
def test_the_fold_still_rewrites_what_the_detector_now_ignores(char: str) -> None:
    """Both halves. #725 keeps these rows in the fold; #957 stops them being detections.

    Asserting only the detector half would pass if the rows had been deleted from the
    table, which is the fix #957 explicitly did not ask for.
    """
    assert disarm.normalize_confusables(char) != char
    assert disarm.is_confusable(char) is False
    assert disarm.find_confusables(char) == []


def test_every_printable_ascii_character_is_clean() -> None:
    """The rule, swept: U+0021-U+007E is never a detection, whatever the table gains."""
    firing = [chr(c) for c in range(0x21, 0x7F) if disarm.is_confusable(chr(c))]
    assert firing == []
    located = [chr(c) for c in range(0x21, 0x7F) if disarm.find_confusables(chr(c))]
    assert located == []


def test_a_homoglyph_in_prose_is_still_detected() -> None:
    """The control must not be a way of turning the detector off."""
    spoofed = PASSAGES["Dickens, A Tale of Two Cities (1859)"].replace("times", "timesа", 1)
    assert disarm.is_confusable(spoofed)
    assert len(disarm.find_confusables(spoofed)) == 1
