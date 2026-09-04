"""Removing an emoji, and the set that is and is not one (#972).

An emoji inserted inside a word splits it for a subword tokenizer (Emoji Attack,
arXiv:2411.01077). Until this, disarm could **name** an emoji or keep it, and removal was
reachable only as a side effect of `transliterate` — so the composable surfaces left the
split in place.

Naming and replacing read different tables because they answer different questions, and
that is the whole design:

* naming asks *what does CLDR call this?*, over a table wider than the emoji — CLDR
  annotates `U+2122`, so `demojize("x™y")` is `"x trade mark y"`;
* replacing asks *is this an emoji by the UCD's properties?*, over the emoji-presentation
  set — so `™` and `©` stay exactly where they are.

A replacement applied to the naming domain would delete typographic punctuation from
ordinary prose, which is the #757 failure in a new place.
"""

from __future__ import annotations

import pytest

import disarm
from disarm import TextPipeline, demojize, get_pipeline, replace_emoji


class TestTheEmojiPresentationSet:
    """What is an emoji here, asserted from both sides."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("aa🔥bb", "aabb"),  # Emoji_Presentation=Yes
            ("x👨‍👩‍👧y", "xy"),  # ZWJ sequence, one emoji
            ("x👍🏽y", "xy"),  # skin-tone modifier sequence
            ("x1️⃣y", "xy"),  # keycap, base + VS16 + U+20E3
            ("x1⃣y", "xy"),  # keycap without the selector
            ("x🇬🇧y", "xy"),  # regional-indicator pair
            ("x☺️y", "xy"),  # Emoji=Yes base carrying VS16
        ],
    )
    def test_a_sequence_is_one_emoji(self, text: str, expected: str) -> None:
        assert replace_emoji(text) == expected

    @pytest.mark.parametrize(
        "text",
        [
            "x☺y",  # the same base without VS16: text presentation
            "x©y",  # Emoji=Yes, Emoji_Presentation=No
            "x™y",  # CLDR annotates it; the UCD does not call it an emoji
            "x1y",  # a keycap base with no keycap
            "x#y",
        ],
    )
    def test_what_is_not_an_emoji_is_left_alone(self, text: str) -> None:
        assert replace_emoji(text) == text

    def test_naming_keeps_its_wider_domain(self) -> None:
        """Both halves: the same characters replacing leaves are still named."""
        assert demojize("x™y") == "x trade mark y"
        assert replace_emoji("x™y") == "x™y"
        assert demojize("x☺y") == "x smiling face y"
        assert replace_emoji("x☺y") == "x☺y"


class TestTheReplacementIsVerbatim:
    def test_no_padding_and_no_collapse(self) -> None:
        assert replace_emoji("aa 🔥 bb") == "aa  bb"
        assert demojize("aa 🔥 bb") == "aa fire bb"

    def test_the_caller_chooses_separation(self) -> None:
        """Neither value can be a default; #910 measured what each costs the other."""
        assert replace_emoji("stop🛑now", "") == "stopnow"
        assert replace_emoji("stop🛑now", " ") == "stop now"

    def test_any_string_goes_in(self) -> None:
        assert replace_emoji("aa🔥bb", "[emoji]") == "aa[emoji]bb"

    def test_a_keycap_belongs_only_to_a_keycap_base(self) -> None:
        """UTS #51 defines the sequence for `0`-`9`, `#` and `*`, and nothing else.

        A combining keycap after any other emoji is a stray mark, not part of a sequence,
        so it is left where it is rather than absorbed into the emoji beside it.
        """
        assert replace_emoji("x1️⃣y") == "xy"
        assert replace_emoji("x☺️⃣y") == "x⃣y"
        assert replace_emoji("x🔥⃣y") == "x⃣y"

    def test_a_lone_regional_indicator_is_an_emoji_and_a_pair_is_one_emoji(self) -> None:
        """Each indicator is `Emoji_Presentation=Yes`, so one goes on its own.

        The pairing is about *counting*, not about membership: a flag must take one
        replacement, not two, which only a non-empty replacement can see.
        """
        assert replace_emoji("x🇬y") == "xy"
        assert replace_emoji("x🇬y", " ") == "x y"
        assert replace_emoji("x🇬🇧y", " ") == "x y"

    def test_a_sequence_gets_one_replacement_not_one_per_code_point(self) -> None:
        """Invisible under `""`, and the whole point under `" "`."""
        assert replace_emoji("x🇬🇧y", " ") == "x y"
        assert replace_emoji("x👨‍👩‍👧y", " ") == "x y"
        assert replace_emoji("x👍🏽y", " ") == "x y"
        assert replace_emoji("x1️⃣y", " ") == "x y"

    def test_demojize_replacement_is_the_same_operation(self) -> None:
        for text in ("aa🔥bb", "stop🛑now", "x™y", "x1️⃣y"):
            assert demojize(text, replacement="") == replace_emoji(text, "")
            assert demojize(text, replacement=" ") == replace_emoji(text, " ")

    def test_the_naming_options_do_not_apply(self) -> None:
        """Ignored, not rejected: the provider can be registered globally."""
        assert demojize("x👍🏽y", replacement="", strip_modifiers=True) == "xy"
        assert demojize("x👍🏽y", replacement="", errors="preserve") == "xy"

    def test_a_non_string_replacement_is_refused(self) -> None:
        with pytest.raises(TypeError):
            demojize("x", replacement=1)  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            replace_emoji("x", 1)  # type: ignore[arg-type]


class TestThePipeline:
    def test_the_flag_takes_three_settings(self) -> None:
        assert TextPipeline(demojize=True)("aa🔥bb") == "aa fire bb"
        assert TextPipeline(demojize="")("aa🔥bb") == "aabb"
        assert TextPipeline(demojize=" ")("stop🛑now") == "stop now"
        assert TextPipeline(demojize=False)("aa🔥bb") == "aa🔥bb"

    def test_an_empty_replacement_still_turns_the_step_on(self) -> None:
        """`""` is falsy, so a truthiness test would read it as off."""
        assert [name for name, _ in TextPipeline(demojize="").steps] == ["demojize"]

    def test_a_bad_type_is_refused(self) -> None:
        with pytest.raises(TypeError):
            TextPipeline(demojize=1)  # type: ignore[arg-type]

    def test_the_paper_and_the_counter_measurement(self) -> None:
        """The construction this exists for, and the one #910 declined it for."""
        pipe = TextPipeline(normalize="NFKC", demojize="", fold_case=True)
        assert pipe("ignore😀 previous") == "ignore previous"
        assert TextPipeline(demojize="")("stop🛑now") == "stopnow"


class TestShippedDefaultsDoNotMove:
    """#910's decision stands until an issue answers its measurement."""

    def test_the_guardrail_keeps_a_visible_emoji(self) -> None:
        assert get_pipeline("llm_guardrail")("stop🛑now") == "stop🛑now"
        assert get_pipeline("llm_guardrail")("ignore😀 previous") == "ignore😀 previous"

    def test_the_comparison_presets_keep_it_too(self) -> None:
        assert disarm.canonicalize("aa🔥bb") == "aa🔥bb"
        assert disarm.strip_obfuscation("aa🔥bb") == "aa🔥bb"

    def test_no_shipped_profile_sets_a_replacement(self) -> None:
        """Asserted on the step, not the output.

        `library_catalog_key_eu` and the other transliterating profiles already return
        `aabb`, because romanization drops an emoji as a side effect — which is #972's
        premise, not a default change. What must not move is any profile *declaring* a
        replacement.
        """
        for name in disarm.list_profiles():
            steps = dict(get_pipeline(name).steps)
            assert steps.get("demojize") in (None, "", "names"), name


class TestTheLadderOverEmojiPresentation:
    """Every `Emoji_Presentation` code point the bundled table knows, between two words.

    The suite's own ladder, over the property rather than a sample: a code point either
    rejoins the split or it does not, and one that survives is one the paper's vector
    still works on.
    """

    def test_every_presentation_code_point_rejoins_the_split(self) -> None:
        rows = _presentation_code_points()
        assert len(rows) > 1_000, f"only {len(rows)} code points; the table is not loaded"
        survives = [cp for cp in rows if TextPipeline(demojize="")(f"aa{chr(cp)}bb") != "aabb"]
        assert not survives, (
            f"{len(survives)} of {len(rows)} still split the word, e.g. "
            f"{[f'U+{cp:04X}' for cp in survives[:8]]}"
        )

    def test_the_guardrail_is_the_other_end_of_the_same_ladder(self) -> None:
        """Both halves: the default never closes the split the opt-in closes.

        Not "the character survives": NFKC decomposes a handful of squared and circled
        CJK emoji to a bare ideograph, so the guardrail changes them. What it never does
        is rejoin `aa` to `bb`, which is the property #910 decided on.
        """
        rejoined = [
            cp
            for cp in _presentation_code_points()
            if get_pipeline("llm_guardrail")(f"aa{chr(cp)}bb") == "aabb"
        ]
        assert not rejoined, f"{len(rejoined)} rejoined, e.g. {[hex(c) for c in rejoined[:6]]}"

    def test_the_reach_is_the_bundled_table_and_the_docs_say_so(self) -> None:
        """A code point the bundled table does not know survives, and that is honest.

        `docs/api/transforms.md` states the vintage and the count. Both move on a table
        refresh, so the refresh updates the prose rather than silently outdating it.
        """
        from pathlib import Path

        assert len(_presentation_code_points()) == 1205
        # Assigned after UCD 15.1.0, so outside the table and not removed.
        assert TextPipeline(demojize="")("aa\U0001fae9bb") == "aa\U0001fae9bb"
        page = (Path(__file__).resolve().parent.parent / "docs/api/transforms.md").read_text(
            encoding="utf-8"
        )
        assert "1,205 code points" in page
        assert "U+1FAE9" in page


def _presentation_code_points() -> list[int]:
    """`Emoji_Presentation` from the bundled table, which is what the library ships."""
    from pathlib import Path

    tsv = Path(__file__).resolve().parent.parent / "src/tables/data/emoji_presentation.tsv"
    out: list[int] = []
    for line in tsv.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        lo = int(parts[0], 16)
        hi = int(parts[1], 16) if len(parts) > 1 else lo
        out.extend(range(lo, hi + 1))
    return out
