"""#559 — ``ml_normalize(fold_case=False)`` for a cased downstream model.

``ml_normalize`` folds case deliberately, and that is defensible: most tokenizers are
uncased. What was missing is a way to turn it off for one call. Every other stage the
preset runs — NFKC, demojize, transliterate, strip-accents, control/zero-width removal,
whitespace folding — is wanted in front of a *cased* model too, and there was no route
to them without the fold.

The tests below pin two things: the default did not move, and the flag changes exactly
one property of the output.
"""

from __future__ import annotations

import pytest

import disarm
from disarm import Text

#: Inputs that exercise a different stage of the pipeline each. Used to assert the flag
#: is surgical rather than merely "different".
STAGE_INPUTS = [
    pytest.param("José Martínez", id="accents"),
    pytest.param("MÜNCHEN Straße", id="sharp-s"),
    pytest.param("Hi \U0001f600 THERE", id="emoji-cldr"),
    pytest.param("ﬁLTER", id="ligature-nfkc"),
    pytest.param("Ｆｕｌｌｗｉｄｔｈ", id="fullwidth-nfkc"),
    pytest.param("A​B\tC   D", id="zero-width-control-whitespace"),
    pytest.param("café ≇ X", id="exposed-base-demojize"),
    pytest.param("", id="empty"),
    pytest.param("ΣΊΣΥΦΟΣ", id="greek-final-sigma"),
]


def test_default_still_folds() -> None:
    """No behaviour change for existing callers — the whole point of defaulting True."""
    assert disarm.ml_normalize("José Martínez") == "jose martinez"
    assert disarm.ml_normalize("Café RÉSUMÉ") == "cafe resume"


def test_fold_case_false_keeps_capitals() -> None:
    assert disarm.ml_normalize("José Martínez", fold_case=False) == "Jose Martinez"


def test_fold_case_false_still_strips_accents() -> None:
    """``fold_case=False`` is not "leave my text alone".

    ``strip_accents`` is a separate step and still runs, so the diacritic goes and the
    capital stays. A caller who needs the diacritics too wants ``normalize_confusables``
    — see #564 and ``docs/security/adversarial-defense.md``.
    """
    out = disarm.ml_normalize("naïve café", fold_case=False)
    assert out == "naive cafe"
    assert disarm.normalize_confusables("naïve café") == "naïve café"


@pytest.mark.parametrize("text", STAGE_INPUTS)
def test_flag_changes_only_case(text: str) -> None:
    """Case-folding the unfolded output must reproduce the folded output exactly.

    This is stronger than asserting the two differ: it proves no *other* stage behaves
    differently on the no-fold path. If dropping the step perturbed NFKC, demojize,
    accent stripping, or whitespace handling, the two sides would not converge.
    """
    folded = disarm.ml_normalize(text)
    unfolded = disarm.ml_normalize(text, fold_case=False)
    assert disarm.fold_case(unfolded) == folded


@pytest.mark.parametrize("text", STAGE_INPUTS)
@pytest.mark.parametrize("fold_case", [True, False])
def test_idempotent_in_both_modes(text: str, fold_case: bool) -> None:
    """Dropping a step must not cost the preset its fixed point."""
    once = disarm.ml_normalize(text, fold_case=fold_case)
    assert disarm.ml_normalize(once, fold_case=fold_case) == once


def test_transliteration_is_orthogonal_to_case() -> None:
    assert disarm.ml_normalize("MÜNCHEN Straße", lang="de") == "muenchen strasse"
    assert disarm.ml_normalize("MÜNCHEN Straße", lang="de", fold_case=False) == "MUeNCHEN Strasse"


def test_emoji_style_is_orthogonal_to_case() -> None:
    assert disarm.ml_normalize("Hi \U0001f600", emoji="none", fold_case=False) == "Hi \U0001f600"
    assert disarm.ml_normalize("Hi \U0001f600", emoji="cldr", fold_case=False) == "Hi grinning face"


@pytest.mark.parametrize("fold_case", [True, False])
def test_argument_validation_runs_in_both_modes(fold_case: bool) -> None:
    """The no-fold path must not skip the validation prologue."""
    with pytest.raises(disarm.InvalidArgumentError):
        disarm.ml_normalize("x", emoji="bogus", fold_case=fold_case)
    with pytest.raises(disarm.InvalidArgumentError):
        disarm.ml_normalize("x", lang="zzz", fold_case=fold_case)


def test_keyword_only() -> None:
    """``fold_case`` is keyword-only, like every other ``ml_normalize`` option."""
    with pytest.raises(TypeError):
        disarm.ml_normalize("x", None, "cldr", False)  # type: ignore[misc]


def test_text_builder_carries_the_flag() -> None:
    assert str(Text("José Martínez").ml_normalize()) == "jose martinez"
    assert str(Text("José Martínez").ml_normalize(fold_case=False)) == "Jose Martinez"


def test_other_key_presets_have_no_such_switch() -> None:
    """Pins the scope decision.

    ``catalog_key`` / ``search_key`` / ``sort_key`` fold because a key has to collide;
    folding is the purpose there, not a side effect. ``ml_normalize`` is the one preset
    that feeds a model, so it is the one that gets the switch. If a later change adds
    the flag to a key preset, this test asks for that reasoning to be revisited.
    """
    for preset in (disarm.catalog_key, disarm.search_key, disarm.sort_key):
        with pytest.raises(TypeError):
            preset("x", fold_case=False)  # type: ignore[call-arg]
