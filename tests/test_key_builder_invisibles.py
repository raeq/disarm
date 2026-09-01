"""#805 — the key builders passed invisible characters straight through.

A key builder exists so two spellings of one identity compare equal. Every invisible
character is a way to vary the key without varying what a human sees, so an evasion here
defeats the whole point of the function — and `canonicalize` and `strip_obfuscation`
already stripped these, which made it an asymmetry inside the library rather than a
missing capability.

#805 measured noncharacters. Measured over the wider class before fixing it, the gap was
larger and the shape explains why it went unnoticed:

    class                  search_key  catalog_key  sort_key
    noncharacters             EVADES       EVADES     EVADES
    tag characters            EVADES       EVADES     EVADES
    PUA, plane 15             EVADES       EVADES     EVADES
    PUA, BMP                      ok           ok         ok
    variation selectors           ok           ok     EVADES
    CGJ                           ok           ok     EVADES

BMP private-use was already handled, so a spot check with `U+E000` came back clean and the
class looked covered. It was the supplementary planes, the Tags block and the
noncharacters that were not — and the Tags block is the ASCII-smuggling channel #700 gave
the *detector*, never the key builders.

The fix is one step, because it is one class: `StripInvisible(COMPARISON_STRIP)`, the
policy `canonicalize` already uses. #805 asked for noncharacters; fixing only those would
have left tags and supplementary PUA evading, which is a worse place to stop than either
end.
"""

from __future__ import annotations

import pytest

import disarm

KEY_BUILDERS = ("search_key", "catalog_key", "sort_key")

#: One representative per invisible class, every one as an escape.
#:
#: The #802 gate does not reach these — noncharacters are `Cn`, private use is `Co`, and
#: the selectors and CGJ are `Mn`, while that gate covers `Cf`/`Cc` — so nothing forced
#: the convention here. It applies anyway, for the reason #802 exists rather than because
#: a check demanded it: every one renders as nothing, so a literal leaves a reviewer
#: looking at blank space and taking the dictionary key's word for what is there.
INVISIBLES = {
    "noncharacter U+FDD0": "\ufdd0",
    "noncharacter U+FDEF": "\ufdef",
    "noncharacter U+FFFE": "\ufffe",
    "noncharacter U+FFFF": "\uffff",
    "noncharacter U+1FFFE": "\U0001fffe",
    "noncharacter U+10FFFF": "\U0010ffff",
    "tag letter U+E0041": "\U000e0041",
    "tag terminator U+E007F": "\U000e007f",
    "PUA BMP U+E000": "\ue000",
    "PUA plane 15": "\U000f0000",
    "PUA plane 16": "\U0010fffd",
    "variation selector 1": "\ufe00",
    "variation selector 16": "\ufe0f",
    "CGJ U+034F": "\u034f",
}


@pytest.mark.parametrize("builder", KEY_BUILDERS)
@pytest.mark.parametrize(("name", "char"), INVISIBLES.items(), ids=list(INVISIBLES))
def test_an_invisible_does_not_change_the_key(builder: str, name: str, char: str) -> None:
    """The evasion, per class per builder."""
    reduce = getattr(disarm, builder)
    assert reduce(f"a{char}b") == reduce("ab"), f"{builder} is evaded by {name}"


@pytest.mark.parametrize("builder", KEY_BUILDERS)
def test_the_position_does_not_matter(builder: str) -> None:
    """Leading, trailing and doubled — an attacker picks the position."""
    reduce = getattr(disarm, builder)
    baseline = reduce("admin")
    for variant in ("\ufdd0admin", "admin\ufdd0", "ad\ufdd0min", "ad\ufdd0\ufdd0min"):
        assert reduce(variant) == baseline, f"{builder} evaded by {variant!r}"


@pytest.mark.parametrize("builder", KEY_BUILDERS)
def test_the_library_no_longer_disagrees_with_itself(builder: str) -> None:
    """`canonicalize` and `strip_noncharacters` always stripped these.

    The asymmetry is what made this a defect rather than a policy: two functions in one
    library gave different answers about whether an invisible character is part of an
    identity.
    """
    reduce = getattr(disarm, builder)
    for char in ("\ufdd0", "\U000e0041", "\U000f0000"):
        assert disarm.canonicalize(f"a{char}b") == "ab"
        assert reduce(f"a{char}b") == reduce("ab")


# ── what must NOT change ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    ["café", "Müller", "Иван", "北京", "مرحبا", "groß.txt", "खान", "ශ්‍රී ලංකා"],
    ids=["french", "german", "cyrillic", "cjk", "arabic", "eszett", "devanagari", "sinhala"],
)
def test_legitimate_text_still_produces_a_useful_key(text: str) -> None:
    """The step must not eat real content. Sinhala is the sharp one — its ZWJ is
    orthography (#802), and the key still transliterates rather than fragmenting."""
    for builder in KEY_BUILDERS:
        key = getattr(disarm, builder)(text)
        assert key, f"{builder} produced an empty key for {text!r}"


def test_a_valid_emoji_flag_keeps_its_tag_sequence() -> None:
    """The #413 carve-out: tags inside a well-formed flag are the character, not smuggling.

    Stripping them would collapse every regional flag onto one black flag, which is a
    worse key than the one it replaced.
    """
    flag = "\U0001f3f4\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f"
    assert "\U000e0067" in disarm.search_key(flag)


def test_an_emoji_zwj_sequence_survives() -> None:
    """ZWJ is not in this class, and the family emoji must not lose its members."""
    # Escaped throughout, joiners included: a literal ZWJ between *escaped* bases is
    # not an emoji sequence to a reader or to the #802 gate, whose exemption looks at
    # the neighbouring characters and finds a backslash.
    family = "\U0001f469\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466"
    key = disarm.sort_key(family)
    assert key.count("\U0001f469") == 2, key
