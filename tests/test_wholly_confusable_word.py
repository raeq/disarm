"""#815 scope item 3 — the detector went silent exactly when the attack was complete.

`inspect_anomalies` reports a `confusable` only when the word **also carries an ASCII
letter** (#633's gate). That gate exists for a good reason: it is what keeps `Привет`
from firing, and #907 is the standing record of what happens when a surface treats
legitimate non-Latin text as something to rewrite.

But it inverts. Substituting one letter of `instructions` for its small-capital form
trips the detector; substituting all of them silences it:

    1/8 converted   has_anomalies True
    7/8 converted   has_anomalies True
    8/8 converted   has_anomalies False    <- the finished attack

A word with no ASCII letter at all, whose every character imitates one, is *more*
suspicious than a half-converted one, not less.

The rule added here fires only when all four hold, which is what keeps `Привет` out:

1. no ASCII letter anywhere in the token
2. every non-space character folds to an ASCII **letter**
3. at least `MIN` such characters
4. the token's script is Latin, or it has none at all

`Москва` passes 1–3 — every Cyrillic letter folds to ASCII — and fails 4, because its
script is Cyrillic. That fourth condition is the whole difference between "a word in
another script" and "Latin letters wearing a disguise".

Validated before implementing: 4 hits in the 23,135-row key-stability corpus, every one
an attack string; 0 hits in 235,976 entries of `/usr/share/dict/words`.
"""

from __future__ import annotations

import sys
import unicodedata

import pytest

import disarm


def _small_caps(word: str) -> str:
    m: dict[str, str] = {}
    prefix = "LATIN LETTER SMALL CAPITAL "
    for cp in range(sys.maxunicode + 1):
        if 0xD800 <= cp <= 0xDFFF:
            continue
        name = unicodedata.name(chr(cp), "")
        if name.startswith(prefix) and len(name[len(prefix) :]) == 1:
            m.setdefault(name[len(prefix) :].lower(), chr(cp))
    return "".join(m.get(c, c) for c in word)


def _negative_enclosed(word: str) -> str:
    m: dict[str, str] = {}
    for cp in list(range(0x1F150, 0x1F16A)) + list(range(0x1F170, 0x1F18A)):
        name = unicodedata.name(chr(cp), "")
        if "LATIN CAPITAL LETTER" in name:
            m.setdefault(name[-1].lower(), chr(cp))
    return "".join(m.get(c, c) for c in word)


ATTACKS = ["instructions", "ignore", "password", "admin", "override", "paypal"]


@pytest.mark.parametrize("word", ATTACKS)
def test_a_fully_converted_word_is_reported(word: str) -> None:
    """The inversion, closed: complete conversion must not be quieter than partial."""
    assert disarm.has_anomalies(_small_caps(word))


@pytest.mark.parametrize("word", ATTACKS[:4])
def test_the_negative_enclosed_form_is_reported_too(word: str) -> None:
    """Those are category `So`, so a rule keyed on `is_alphabetic` cannot see them.

    Keyed on "folds to an ASCII letter" instead, which is the property that matters.
    """
    assert disarm.has_anomalies(_negative_enclosed(word))


def test_conversion_is_monotonic() -> None:
    """The property the bug violated: more conversion never means less signal."""
    word = "instructions"
    caps = _small_caps(word)
    seen_true = False
    for k in range(1, len(word) + 1):
        probe = caps[:k] + word[k:]
        fired = disarm.has_anomalies(probe)
        if fired:
            seen_true = True
        elif seen_true:
            pytest.fail(f"signal disappeared at {k}/{len(word)} converted: {probe!r}")
    assert disarm.has_anomalies(caps), "the fully converted form must still fire"


@pytest.mark.parametrize(
    "text", ["Привет", "Ελλάδα", "שלום", "日本語", "العربية", "Москва", "Київ", "Ελληνικά"]
)
def test_legitimate_non_latin_words_stay_clean(text: str) -> None:
    """#633's reason for the gate, and #907's. `Москва` is the sharp one: every letter
    folds to ASCII, so only the script test keeps it out."""
    assert not disarm.has_anomalies(text)


@pytest.mark.parametrize("text", ["café", "naïve", "Việt", "ÀÉÎÕÜ", "Ångström", "ÉTÉ", "ÑOÑO"])
def test_accented_latin_stays_clean(text: str) -> None:
    assert not disarm.has_anomalies(text)


@pytest.mark.parametrize("text", ["ɪɴ", "ʃʊʁ", "ɐɪ"])
def test_short_all_non_ascii_ipa_stays_clean(text: str) -> None:
    """The false-positive tail this rule was actually designed around.

    These are the IPA fragments that are clean *today* — no ASCII letter, so #633's gate
    skips them — and the new rule must not start reporting them. The length floor is what
    keeps them out: two and three characters, and a token that short is where linguistic
    notation lives rather than a disguised identifier.
    """
    assert not disarm.has_anomalies(text)


@pytest.mark.parametrize("text", ["ˈɪnstrəkʃən", "ˈbʊk", "ʃiː", "θɪŋk"])
def test_ipa_that_already_fires_is_not_this_rule(text: str) -> None:
    """Measured, not assumed: these were already reported before this change.

    They carry an ASCII letter beside a non-ASCII one, which is the mixed spelling #633's
    gate treats as the signal — `\u03b8\u026a\u014bk` fires as `mixed_script`, the rest as
    `confusable`. Recorded so the new rule is not credited or blamed for them.
    """
    assert disarm.has_anomalies(text)


def test_the_length_floor_is_what_excludes_the_short_fragments() -> None:
    """Both halves, so the floor cannot be removed or raised without a failure."""
    assert not disarm.has_anomalies(_small_caps("adm"))  # 3 characters
    assert disarm.has_anomalies(_small_caps("admin"))  # 5


def test_ordinary_ascii_is_untouched() -> None:
    for text in ("instructions", "the quick brown fox", "admin", "paypal.com"):
        assert not disarm.has_anomalies(text)
