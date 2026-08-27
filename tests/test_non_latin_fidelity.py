"""#624 — what the destructive presets do to non-Latin text, measured.

``test_accented_latin_fidelity.py`` (#564) establishes that accent destruction is a
property of the *bundle* a caller chose rather than of the confusable primitive:
``normalize_confusables`` preserves ``José`` and ``strip_obfuscation`` does not.

**That framing does not extend to non-Latin, and the way it fails is the point.** There
are three destructive mechanisms here, not one, and they are orthogonal:

1. ``strip_accents`` deletes Indic vowel signs and viramas. Both they and a Latin acute
   are general category ``Mn``; in Latin an ``Mn`` is decoration, in Indic it is a vowel.
   ``José`` -> ``Jose`` is degraded and readable. ``বাংলা`` -> ``বল`` is not a word.
2. The to-Latin confusable fold splices Latin letters into Arabic, Hebrew, Greek and
   Telugu. This one is in the **primitive**, so the #564 escape hatch does not exist for
   those scripts.
3. Format-character removal takes the ZWNJ that Persian orthography requires.

Nothing here is a bug report. Every step is doing what it says, and the key builders
(``search_key`` / ``catalog_key``) are excluded throughout because a key is *supposed* to
be destructive — that is what #620 turns on. What these tests hold is the claim the docs
make about *scope*: these presets are for identifiers, hostnames, filenames and log
lines, and not for body text.
"""

from __future__ import annotations

import pytest

import disarm

#: (id, sample, gloss). Real words, so "this is no longer a word" is checkable rather
#: than a matter of opinion.
SAMPLES = [
    ("telugu", "జ్ఞానం", "Telugu for 'knowledge'"),
    ("devanagari", "हिन्दी", "the word 'Hindi'"),
    ("bengali", "বাংলা", "the name of the Bengali language"),
    ("tamil", "தமிழ்", "the name of the Tamil language"),
    ("kannada", "ಕನ್ನಡ", "the name of the Kannada language"),
    ("malayalam", "മലയാളം", "the name of the Malayalam language"),
    ("gujarati", "ગુજરાતી", "the name of the Gujarati language"),
    ("khmer", "ភាសាខ្មែរ", "Khmer for 'Khmer language'"),
    ("arabic", "العربية", "Arabic for 'Arabic'"),
    # The ZWNJ is escaped for the same reason as the ZWNJ constant below: invisible
    # in a diff, and this sample exists precisely to carry it.
    ("persian", "می\u200cخواهم", "Persian for 'I want', with the required ZWNJ"),
    ("hebrew", "עברית", "Hebrew for 'Hebrew'"),
    ("greek", "Ελληνικά", "Greek for 'Greek'"),
    ("thai", "ภาษาไทย", "Thai for 'Thai language'"),
]

IDS = [s[0] for s in SAMPLES]
TEXTS = {s[0]: s[1] for s in SAMPLES}


def _param(*ids: str) -> list:
    return [pytest.param(TEXTS[i], id=i) for i in ids]


# ── Mechanism 1: strip_accents deletes Indic vowels ──────────────────


#: Which samples each mechanism touches, derived from behaviour rather than listed.
#: A hand-written membership list is the thing that goes stale when a table is
#: refreshed — and it already did once while this file was being written, because
#: Malayalam's anusvara folds to `o` exactly as Telugu's does and the hand-list
#: missed it. `test_the_mechanism_partition_is_what_we_think` pins the derived sets.
#: Split by the property that actually distinguishes the two losses, on NFC input:
#: an accent sits *on* a precomposed letter, so removing it keeps the length; an Indic
#: vowel sign is its own code point carrying the vowel, so removing it shortens the
#: word. Greek is the case that forces the split — `strip_accents` changes `Ελληνικά`,
#: but to `Ελληνικα`, which is the `José` -> `Jose` kind of loss and not the Indic kind.
ACCENT_ONLY_SCRIPTS = tuple(
    i
    for i in IDS
    if disarm.strip_accents(TEXTS[i]) != TEXTS[i]
    and len(disarm.strip_accents(TEXTS[i])) == len(TEXTS[i])
)
VOWEL_SIGN_SCRIPTS = tuple(i for i in IDS if len(disarm.strip_accents(TEXTS[i])) < len(TEXTS[i]))
SPLICED_SCRIPTS = tuple(i for i in IDS if disarm.normalize_confusables(TEXTS[i]) != TEXTS[i])
UNTOUCHED_BY_BOTH = tuple(
    i for i in IDS if i not in VOWEL_SIGN_SCRIPTS + ACCENT_ONLY_SCRIPTS + SPLICED_SCRIPTS
)


def test_the_mechanism_partition_is_what_we_think() -> None:
    """The derived sets, pinned. Two mechanisms, overlapping but not nested.

    Thai is the only sample neither reaches. Telugu, Malayalam and Greek are reached by
    both. The overlap and the gap are each the point: a caller cannot avoid the damage
    by reaching past the bundle to the primitive, because for six of these samples the
    primitive is where the damage is.
    """
    assert set(VOWEL_SIGN_SCRIPTS) == {
        "telugu",
        "devanagari",
        "bengali",
        "tamil",
        "kannada",
        "malayalam",
        "gujarati",
        "khmer",
    }
    assert set(ACCENT_ONLY_SCRIPTS) == {"greek"}
    assert set(SPLICED_SCRIPTS) == {
        "arabic",
        "persian",
        "hebrew",
        "greek",
        "telugu",
        "malayalam",
    }
    assert set(UNTOUCHED_BY_BOTH) == {"thai"}


@pytest.mark.parametrize("text", _param(*VOWEL_SIGN_SCRIPTS))
def test_strip_accents_deletes_indic_vowels(text: str) -> None:
    """The category is the same; the linguistic role is not."""
    stripped = disarm.strip_accents(text)
    assert stripped != text
    assert len(stripped) < len(text), "characters were removed, not replaced"


def test_the_loss_is_a_different_kind_from_the_latin_one() -> None:
    """Named separately because a count does not carry it, and the count is what a
    "14 of 15 samples changed" table would have reported.

    ``José`` keeps every letter and loses an accent, and Greek behaves the same way.
    ``বাংলা`` loses two of its five code points and the result is not a word — the
    vowel sign *is* part of the letter's identity, not decoration on it.
    """
    assert disarm.strip_accents("José") == "Jose"  # readable
    assert disarm.strip_accents("Ελληνικά") == "Ελληνικα"  # readable, same length
    assert disarm.strip_accents("বাংলা") == "বল"  # not a word, shorter


@pytest.mark.parametrize(
    "text", _param(*(i for i in VOWEL_SIGN_SCRIPTS if i not in SPLICED_SCRIPTS))
)
def test_the_confusable_primitive_is_not_what_removes_them(text: str) -> None:
    """#564's structure holds for the scripts mechanism 2 leaves alone: the loss is
    the bundle's, and a caller who wants homoglyph folding without it can call the
    primitive. For the overlap — Telugu, Malayalam, Greek — it does not."""
    assert disarm.normalize_confusables(text) == text


# ── Mechanism 2: the to-Latin fold splices Latin in ──────────────────


@pytest.mark.parametrize("text", _param(*SPLICED_SCRIPTS))
def test_the_primitive_itself_splices_latin_into_non_latin(text: str) -> None:
    folded = disarm.normalize_confusables(text)
    assert folded != text, "the primitive is not the safe escape hatch here"
    assert any((c.isascii() and c.isalpha()) or c == "'" for c in folded), (
        "expected an ASCII letter or apostrophe spliced into the output"
    )


def test_the_exact_splices_are_pinned() -> None:
    """Spelled out, because "it changes" is not the interesting part — *what* it
    becomes is. Each of these is ordinary text in its language."""
    assert disarm.normalize_confusables("العربية") == "lلعربية"  # alef -> l
    assert disarm.normalize_confusables("עברית") == "עבר'ת"  # yod -> apostrophe
    assert disarm.normalize_confusables("Ελληνικά") == "Eλλnvikά"  # half-Latin
    assert disarm.normalize_confusables("జ్ఞానం") == "జ్ఞానo"  # anusvara -> o
    assert disarm.normalize_confusables("മലയാളം") == "മലയാളo"  # and again in Malayalam


def test_greek_comes_out_neither_greek_nor_latin() -> None:
    """The worst shape of the three, and the reason a count understates it.

    A fully folded word would at least be searchable as Latin. ``Ελληνικά`` comes back
    as ``Eλλnvikά`` — four letters folded, four left alone — which is a word in no
    script and matches nothing in either.
    """
    folded = disarm.normalize_confusables("Ελληνικά")
    assert any(c.isascii() for c in folded)
    assert any(not c.isascii() for c in folded)
    scripts = disarm.detect_scripts(folded)
    assert disarm.Script.GREEK in scripts
    assert disarm.Script.LATIN in scripts


def test_there_is_no_do_not_fold_target() -> None:
    """The escape hatch that does not exist, stated so the docs cannot imply it.

    ``target_script`` selects *which* script to fold toward, not whether to fold. A
    caller who wants to know about homoglyphs without rewriting the text uses the
    predicates instead.
    """
    with pytest.raises(disarm.InvalidArgumentError):
        disarm.normalize_confusables("العربية", target_script="none")
    assert disarm.is_confusable("العربية") is True
    assert disarm.normalize_confusables("العربية", target_script="cyrillic") != "العربية"


def test_the_damage_cannot_be_scoped_away_by_looking_for_latin() -> None:
    """MEASURED, and it settles #624's open question the other way.

    The obvious fix is to skip the fold when the input contains no Latin: there is
    no Latin there for a homoglyph to be confused with, so wholly-Arabic text would
    survive. Every one of the CVE probes that needs the fold does contain Latin, so
    the rule looked free.

    It is not. Latin is the *pivot* alphabet, not the threat: two non-Latin scripts
    are made to collide by folding both toward it. The pairs below contain no Latin
    at all, and the fold is the only reason they meet — under a presence-of-Latin
    gate, registering the Cyrillic spelling and impersonating the Greek one would go
    unnoticed.

    So the fold stays unconditional, and the damage to non-Latin body text is the
    cost of having a pivot at all rather than an oversight. That is why #624 is
    answered with scope documentation instead of a behaviour change.
    """
    cross_script_pairs = [("оо", "οο"), ("а", "α"), ("р", "ρ")]  # Cyrillic vs Greek
    for cyrillic, greek in cross_script_pairs:
        assert disarm.Script.LATIN not in disarm.detect_scripts(cyrillic)
        assert disarm.Script.LATIN not in disarm.detect_scripts(greek)
        assert disarm.normalize_confusables(cyrillic) == disarm.normalize_confusables(greek)
        assert cyrillic != greek


# ── Mechanism 3: the ZWNJ Persian requires ───────────────────────────


#: Escaped rather than written literally: it is invisible, so a literal is easy to
#: delete by accident and impossible to see in a diff — which would silently turn
#: every assertion below into a tautology (review on #636).
ZWNJ = "\u200c"


@pytest.mark.parametrize(
    "preset",
    ["canonicalize", "canonicalize_strict", "strip_obfuscation", "ml_normalize", "strip_format"],
)
def test_every_cleaning_preset_removes_the_persian_zwnj(preset: str) -> None:
    """ZWNJ is not decoration in Persian: it separates a word's parts and its absence
    changes the rendering. Every preset that removes format characters removes it, which
    is correct for a filename and wrong for a sentence."""
    assert ZWNJ in TEXTS["persian"]
    assert ZWNJ not in getattr(disarm, preset)(TEXTS["persian"])


# ── The gap that makes it worth documenting ──────────────────────────


@pytest.mark.parametrize("text", _param(*IDS))
def test_nothing_flags_ordinary_non_latin_before_it_is_damaged(text: str) -> None:
    """MEASURED, and the reason "clean unconditionally" needs a scope qualifier.

    ``has_anomalies`` is *correct* to stay silent — this is ordinary text, not an
    attack. But it means a pipeline that screens first and cleans what it flagged gets
    no warning before the damage, so the choice has to be made by context rather than by
    detector output.
    """
    assert disarm.has_anomalies(text) is False
    assert disarm.is_mixed_script(text) is False


# ── The key builders are excluded on purpose ─────────────────────────


@pytest.mark.parametrize("text", _param(*IDS))
@pytest.mark.parametrize("key", ["search_key", "catalog_key"])
def test_the_key_builders_are_destructive_and_that_is_the_point(key: str, text: str) -> None:
    """No caveat is owed here. A key exists to collide (#620); a key that preserved the
    input would not be a key. They are listed in the docs as keys, not as cleaners."""
    assert getattr(disarm, key)(text) != text
