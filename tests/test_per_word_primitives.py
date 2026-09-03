"""#901 — bilingual text is indistinguishable from a spoof at the primitive layer.

`is_mixed_script` and `has_bidi_conflict` answer a question about the whole string, and
both docstrings were accurate about that. The trouble is what a caller does with them:
they look like standalone detectors, so callers compose them, and

    is_mixed_script(x) or has_bidi_conflict(x) or find_confusables(x)

rejects every bilingual user. Measured, that rule rejected **all six** rows of the issue's
table — the two spoofs and the four ordinary bilingual strings alike.

`has_anomalies` already tells them apart. `per_word=True` is that distinction exposed on
its own, so a caller can build a bilingual-safe rule from parts.

`find_confusables`, the third primitive, got its half in #900 as `allowed_scripts`.
"""

from __future__ import annotations

import pytest

import disarm

#: (text, is a spoof, gloss) — the issue's table, plus the compound shapes that decided
#: the word-vs-token question.
ROWS = [
    ("hellо", True, "one word, one Cyrillic о"),
    ("שלוםworld", True, "Hebrew + Latin, glued into one token"),
    ("hello мир", False, "two words, two scripts"),
    ("שלום world", False, "Hebrew + Latin, two words"),
    ("مرحبا hello", False, "Arabic + Latin, two words"),
    ("東京 hello", False, "Han + Latin, two words"),
    ("IT-специалист", False, "hyphenated bilingual compound"),
    ("email:почта", False, "colon-joined"),
    ("user@почта.рф", False, "an address"),
    ("Tokyo/東京", False, "slash-joined"),
    ("ru_текст", False, "underscore-joined"),
]

SPOOFS = [t for t, is_spoof, _ in ROWS if is_spoof]
BILINGUAL = [t for t, is_spoof, _ in ROWS if not is_spoof]


@pytest.mark.parametrize(("text", "is_spoof", "gloss"), ROWS)
def test_per_word_separates_a_spoof_from_a_sentence(text: str, is_spoof: bool, gloss: str) -> None:
    mixed = disarm.is_mixed_script(text, per_word=True)
    bidi = disarm.has_bidi_conflict(text, per_word=True)
    assert (mixed or bidi) is is_spoof, f"{text!r} ({gloss})"


@pytest.mark.parametrize("text", BILINGUAL)
def test_the_string_level_form_still_fires_on_bilingual_text(text: str) -> None:
    """The premise. These are the rows the per-word form exists to spare, so if the
    string-level answer ever changes, the parameter has stopped being needed."""
    assert disarm.is_mixed_script(text) or disarm.has_bidi_conflict(text), text


@pytest.mark.parametrize(("text", "is_spoof", "gloss"), ROWS)
def test_per_word_agrees_with_the_detector(text: str, is_spoof: bool, gloss: str) -> None:
    """`has_anomalies` gets all of these right, and the point of `per_word` is to be the
    same distinction. Where they disagree, one of them is wrong."""
    composed = disarm.is_mixed_script(text, per_word=True) or disarm.has_bidi_conflict(
        text, per_word=True
    )
    assert composed == disarm.has_anomalies(text), f"{text!r} ({gloss})"


def test_the_naive_rule_rejects_everything_which_is_why_this_exists() -> None:
    """The failure the issue reports, pinned so the fix is not mistaken for cosmetics."""
    rejected = [
        text
        for text, _, _ in ROWS
        if disarm.is_mixed_script(text)
        or disarm.has_bidi_conflict(text)
        or disarm.find_confusables(text)
    ]
    assert set(rejected) >= set(BILINGUAL), "the naive rule should reject bilingual text"


def test_the_bilingual_safe_rule_built_from_parts() -> None:
    """What #901 asked for: the same composition, rejecting only the spoofs.

    `find_confusables` needs #900's `allowed_scripts` for its half — without it the
    Hebrew and Arabic words fire on their own.
    """
    allowed = ["Latin", "Cyrillic", "Hebrew", "Arabic", "Han"]
    rejected = [
        text
        for text, _, _ in ROWS
        if disarm.is_mixed_script(text, per_word=True)
        or disarm.has_bidi_conflict(text, per_word=True)
        or disarm.find_confusables(text, allowed_scripts=allowed)
    ]
    assert rejected == SPOOFS, rejected


class TestWordsNotWhitespaceTokens:
    """#901 proposed splitting on whitespace. Measured, that re-creates the bug."""

    #: The non-spoof rows that are a single whitespace token — which is exactly the
    #: class this section is about. Derived from ROWS rather than re-typed beside it:
    #: the hand-written copy drifted on its first outing, carrying simplified `东` where
    #: ROWS carries traditional `東`, so the test covered a string the table never
    #: measured (caught in review on #942).
    JOINED = [t for t, is_spoof, _ in ROWS if not is_spoof and len(t.split()) == 1]

    @pytest.mark.parametrize("text", JOINED)
    def test_a_joined_compound_is_one_whitespace_token_and_several_words(self, text: str) -> None:
        assert len(text.split()) == 1, "one whitespace token"
        assert disarm.is_mixed_script(text), "which does mix scripts as a whole"
        assert not disarm.is_mixed_script(text, per_word=True), "but is ordinary per word"

    @pytest.mark.parametrize("text", JOINED)
    def test_and_the_detector_agrees_it_is_ordinary(self, text: str) -> None:
        """Which is what makes the whitespace split wrong rather than merely stricter."""
        assert disarm.has_anomalies(text) is False, text


def test_the_default_is_unchanged() -> None:
    """Additive: no argument, no behaviour change."""
    for text, _, _ in ROWS:
        assert disarm.is_mixed_script(text) == disarm.is_mixed_script(text, per_word=False)
        assert disarm.has_bidi_conflict(text) == disarm.has_bidi_conflict(text, per_word=False)
    assert disarm.is_mixed_script("hello world") is False
    assert disarm.has_bidi_conflict("varonis.com") is False


def test_the_bidi_swap_example_still_fires_per_word() -> None:
    """`has_bidi_conflict`'s own example is a Latin label inside an RTL domain, and it is
    one word — so the per-word form must not spare it."""
    assert disarm.has_bidi_conflict("varonis.com.ו.קום", per_word=True)


def test_the_joined_vectors_come_from_the_table() -> None:
    """A vector list beside its source is a list that drifts from it.

    Asserts the derivation actually selects the joined compounds and nothing else, so a
    row added to ROWS cannot silently fall out of the class it belongs to.
    """
    assert set(TestWordsNotWhitespaceTokens.JOINED) == {
        "IT-специалист",
        "email:почта",
        "user@почта.рф",
        "Tokyo/東京",
        "ru_текст",
    }
    for text in TestWordsNotWhitespaceTokens.JOINED:
        assert text in [t for t, _, _ in ROWS]
