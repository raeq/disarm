"""#900 — `find_confusables` asks a question about Latin, not about the text.

With the default `target_script="latin"` it answers "could this character imitate a Latin
letter", one character at a time, with no reference to the string around it. The docstring
was accurate and the function was the one callers reached for as a spoof detector, so a
service whose users write Russian, Greek, Hebrew or Arabic flagged every native-script
name:

    find_confusables("Москва")  ->  six findings out of six letters

A caller who gates registration on `bool(find_confusables(name))` has built a registry
that rejects its own users' language. The benchmark could not see it: all 140 rows of
`confusable-bench.v1` target English brands and all 20 benign rows are Latin, so no row
exists on which a legitimate non-Latin word is the right answer.

`allowed_scripts` is how the caller says what legitimate input looks like.

The obvious fix — "no Latin in the string, nothing to imitate, return empty" — costs
recall, because a whole-script substitution like `аррӏе` contains no Latin either. This
one does not, and the reason is structural rather than careful: **`Common` and
`Inherited` are never allowed, whatever the caller passes.**
"""

from __future__ import annotations

import pytest

import disarm

#: Native words in a script that is not Latin. Every one is ordinary text.
NATIVE_WORDS = {
    "Cyrillic": "Москва",
    "Greek": "Ελλάδα",
    "Hebrew": "שלום",
    "Arabic": "مرحبا",
}


@pytest.mark.parametrize(("script", "word"), NATIVE_WORDS.items())
def test_a_native_word_is_reported_without_the_declaration(script: str, word: str) -> None:
    """The premise. If this stops being true the parameter has stopped being needed."""
    assert disarm.find_confusables(word), f"{script}: {word} no longer demonstrates #900"


@pytest.mark.parametrize(("script", "word"), NATIVE_WORDS.items())
def test_and_silent_with_it(script: str, word: str) -> None:
    assert disarm.find_confusables(word, allowed_scripts=[script]) == []


def test_moscow_is_six_findings_out_of_six_letters() -> None:
    """The number the issue leads with, pinned."""
    assert len(disarm.find_confusables("Москва")) == 6
    assert disarm.find_confusables("Москва", allowed_scripts=["Cyrillic"]) == []


class TestItDoesNotCostRecall:
    """The reason the obvious fix was rejected, asserted rather than argued."""

    def test_a_whole_script_substitution_is_still_caught(self) -> None:
        """`аррӏе` is five Cyrillic letters and an attack on a Latin registry.

        A "no Latin in the string, nothing to imitate" rule would return empty here,
        which is why the issue rejected it. Declaring Latin does not exempt Cyrillic.
        """
        found = disarm.find_confusables("аррӏе", allowed_scripts=["Latin"])
        assert len(found) == 5, found

    @pytest.mark.parametrize(
        ("ch", "name"),
        [
            ("ℐ", "SCRIPT CAPITAL I"),
            ("Ⅰ", "ROMAN NUMERAL ONE"),
            ("\U0001d408", "MATH BOLD CAPITAL I"),
        ],
    )
    def test_a_scriptless_spoof_cannot_be_declared_away(self, ch: str, name: str) -> None:
        """The structural guarantee: these belong to no script, so no list exempts them.

        Both halves. The first assertion is the mechanism — if one of these ever gains a
        script, the second could start failing silently and the exemption would have
        widened without anyone choosing it.
        """
        assert disarm.detect_scripts(ch) == [], f"{name} now has a script"
        every_script = [s.value for s in disarm.Script]
        assert disarm.find_confusables(ch, allowed_scripts=every_script), (
            f"{name} was suppressed by an allowed-script declaration"
        )

    def test_a_homoglyph_inside_an_allowed_word_is_still_caught(self) -> None:
        """The mixed case — declaring Latin does not forgive a Cyrillic `о` in `hello`."""
        assert disarm.find_confusables("hellо", allowed_scripts=["Latin"]) == [("о", 4, "o")]


def test_the_declaration_is_case_insensitive() -> None:
    """`detect_scripts` says `Cyrillic`; `target_script` takes `cyrillic`. Both work."""
    for spelling in ("Cyrillic", "cyrillic", "CYRILLIC"):
        assert disarm.find_confusables("Москва", allowed_scripts=[spelling]) == [], spelling


def test_the_default_is_unchanged() -> None:
    """No declaration, no behaviour change — this is additive."""
    assert disarm.find_confusables("pɑypal") == [("ɑ", 1, "a")]
    assert disarm.find_confusables("paypal") == []
    assert disarm.find_confusables("Москва") == disarm.find_confusables(
        "Москва", allowed_scripts=[]
    )


def test_several_scripts_can_be_declared_at_once() -> None:
    """A bilingual service declares both; #901 is what remains ambiguous after that."""
    both = disarm.find_confusables("Москва Ελλάδα", allowed_scripts=["Cyrillic", "Greek"])
    assert both == []
    only_one = disarm.find_confusables("Москва Ελλάδα", allowed_scripts=["Cyrillic"])
    assert only_one, "Greek should still be reported when only Cyrillic is declared"


def test_an_unknown_script_is_rejected_by_name() -> None:
    with pytest.raises(disarm.DisarmError) as excinfo:
        disarm.find_confusables("x", allowed_scripts=["Nonsense"])
    assert "Nonsense" in str(excinfo.value)


def test_the_script_enum_works_as_well_as_the_string() -> None:
    assert disarm.find_confusables("Москва", allowed_scripts=[disarm.Script.CYRILLIC]) == []
