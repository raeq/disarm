"""``digit_policy`` reaches the six key builders through the core (#896), so ``preserve``
holds (#949).

#885 shipped the setting as a Python pre-pass: ``numeric`` returned the input untouched,
and the other two policies ran ``normalize_confusables`` before the key pipeline, whose own
fold stayed at the default. Two consequences: the Rust API and every other binding could
not express the setting at all, and ``preserve`` did nothing on six of the seven builders —
the pre-pass kept the numeral and the preset's own fold then folded it.

Now the pre-pass is a step at the head of each builder's list, a no-op under the default,
and the builder's own fold runs under the same policy. The port was measured before it was
written: over 290,889 probes — every assigned non-control code point, alone and between
letters — ``tr39`` output is identical to the pre-pass on all six builders. The two
deltas that sweep found on ``sort_key`` are pinned below.
"""

import pytest

import disarm

SIX = (
    "canonicalize",
    "canonicalize_strict",
    "strip_obfuscation",
    "search_key",
    "catalog_key",
    "sort_key",
)
OWN_FOLD = ("canonicalize", "canonicalize_strict", "strip_obfuscation")
TRANSLITERATING = ("search_key", "catalog_key", "sort_key")
NUMERAL = "amount-١"  # ARABIC-INDIC DIGIT ONE
SPOOF = "g੦ogle"  # GURMUKHI ZERO standing in for "o"
CORPUS = [
    SPOOF,
    NUMERAL,
    "paypaІ",
    "SKU-1O0",
    "٢٠٢٤",
    "Ω",
    "①⓪⓪.⓪⓪",
    "qty-½",
    "Café Résumé",
    "āb",  # a-macron: a tr39-only row
    "āb",  # the same, decomposed
    "",
]


@pytest.mark.parametrize("name", SIX)
class TestEveryBuilder:
    def test_numeric_is_byte_identical_to_the_plain_call(self, name: str) -> None:
        f = getattr(disarm, name)
        for text in CORPUS:
            assert f(text, digit_policy="numeric") == f(text), (name, text)

    def test_tr39_is_the_pre_pass_exactly(self, name: str) -> None:
        # What #885 defined, now produced by the core: fold on the raw text, then the key.
        f = getattr(disarm, name)
        for text in CORPUS:
            expected = f(disarm.normalize_confusables(text, digit_policy="tr39"))
            assert f(text, digit_policy="tr39") == expected, (name, text)

    def test_a_bad_token_is_refused_by_name(self, name: str) -> None:
        with pytest.raises(disarm.InvalidArgumentError, match="digit_policy"):
            getattr(disarm, name)("x", digit_policy="loose")


class TestPreserve:
    @pytest.mark.parametrize("name", OWN_FOLD)
    def test_holds_where_the_builder_owns_a_fold(self, name: str) -> None:
        # #949: these three returned "amount-1" under preserve.
        assert getattr(disarm, name)(NUMERAL, digit_policy="preserve") == NUMERAL

    @pytest.mark.parametrize("name", TRANSLITERATING)
    def test_transliteration_still_romanizes_the_numeral(self, name: str) -> None:
        # Both halves: a key that maps every script to Latin romanizes the digit by
        # transliteration, not by the fold, and preserve neither can nor should stop it.
        assert getattr(disarm, name)(NUMERAL, digit_policy="preserve") == "amount-1"

    def test_the_fold_and_the_skeleton_keep_it_too(self) -> None:
        assert disarm.normalize_confusables(NUMERAL, digit_policy="preserve") == NUMERAL
        assert disarm.skeleton_key(NUMERAL, digit_policy="preserve") == NUMERAL


class TestTheTwoDeltasTheSweepFound:
    """Both on `sort_key`, whose other steps leave the input alone."""

    def test_a_decomposed_base_and_mark_reach_the_row_on_their_composed_form(self) -> None:
        # The single-pass fold missed `a` + U+0304 where the pre-pass (the public,
        # fixed-point fold, which composes between passes) folded `ā` to `ã`.
        assert disarm.sort_key("āb", digit_policy="tr39") == "ãb"

    def test_the_inert_guard_does_not_skip_the_pre_fold(self) -> None:
        # The guard's confusable-source set is generated for the default policy; `ā` is a
        # source only under tr39, so the fast path handed `āb` back unfolded.
        assert disarm.sort_key("āb", digit_policy="tr39") == "ãb"
        assert disarm.sort_key("āb") == "āb"  # and the default still leaves it


def test_the_python_pre_pass_is_gone() -> None:
    # One implementation for all seven surfaces: the Python layer no longer folds first.
    import disarm._presets as presets

    assert not hasattr(presets, "_apply_digit_policy")
    assert not hasattr(presets, "_NON_DEFAULT_DIGIT_POLICIES")
