"""#853 — a named profile is a curated recommendation, so it takes the preset policy.

#757 measured `ml_normalize` turning `film’s` into `film right apostrophe s`: 326 code
points carry neither the Unicode `Emoji` nor the `Extended_Pictographic` property and were
being named as English words. #803 fixed it for `PRESETS` and did not reach
`list_profiles()`.

That is the second time this boundary swallowed a fix — #757's own title records #614
being lost across it one layer in. So this file asserts the two lists agree rather than
only that the one code point behaves.
"""

from __future__ import annotations

import pytest

import disarm


def test_the_profile_matches_its_preset() -> None:
    """The pair the issue names, and the reason it is a pair.

    `ml_normalize` and `ml_corpus_normalize` are documented for the same job. A caller
    choosing between them should not get a different answer about typographic
    punctuation.
    """
    text = "⛑"
    assert disarm.get_pipeline("ml_corpus_normalize")(text) == disarm.ml_normalize(text)


@pytest.mark.parametrize("profile", sorted(disarm.list_profiles()))
def test_every_profile_is_a_fixed_point_on_a_cldr_name(profile: str) -> None:
    """A CLDR name containing `U+2019` must not be re-named on the next pass.

    That feedback loop is what made the profile non-idempotent: `demojize`'s own output
    carried a code point `demojize` would name.
    """
    pipe = disarm.get_pipeline(profile)
    once = pipe("⛑")
    assert pipe(once) == once, f"{profile} renames its own output"


@pytest.mark.parametrize("char", ["’", "€", "¼", "×", "°"])
def test_a_named_profile_does_not_name_a_non_emoji(char: str) -> None:
    """None of these is an emoji, and none should become an English word."""
    for profile in disarm.list_profiles():
        out = disarm.get_pipeline(profile)(char)
        assert "apostrophe" not in out, f"{profile} named {char!r} as {out!r}"
        assert "euro" not in out, f"{profile} named {char!r} as {out!r}"
        assert "fraction slash" not in out, f"{profile} named {char!r} as {out!r}"


@pytest.mark.parametrize(
    ("emoji", "expected"),
    [("☕", "hot beverage"), ("🎉", "party popper"), ("🚀", "rocket"), ("😀", "grinning face")],
)
def test_a_genuine_emoji_is_still_named(emoji: str, expected: str) -> None:
    """The skip must not cost the feature. These carry `Extended_Pictographic`."""
    assert disarm.get_pipeline("ml_corpus_normalize")(emoji) == expected


def test_demojize_and_a_hand_built_pipeline_still_name_everything() -> None:
    """The distinction the fix rests on.

    A caller who writes `demojize` or `TextPipeline(demojize=True)` asked for the step by
    name and gets exactly what it says. A *named profile* is a recommendation, and a
    recommendation carrying a known token-inflation hazard is the thing #757 is about.
    """
    assert disarm.demojize("’") == "right apostrophe"
    assert disarm.TextPipeline(demojize=True)("’") == "right apostrophe"


def test_llm_guardrail_now_clears_the_whole_cve_matrix() -> None:
    """The consequence worth stating: naming the euro sign was breaking the fold.

    `strip_obfuscation("€xample.com")` returned `euro xample.com`, so the spoof and the
    genuine string stopped being equal rather than becoming equal — #614's mechanism,
    which #803 fixed for the presets and not for the profiles.
    """
    guard = disarm.get_pipeline("llm_guardrail")
    assert guard("€xample.com") == guard("example.com")
