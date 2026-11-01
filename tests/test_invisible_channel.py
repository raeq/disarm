"""The detector and the neutralizer must agree about what is invisible.

#812, #813 and #814 are three surfaces disagreeing about one channel:

* #813 — twelve ``Cf`` code points that Unicode marks ``Default_Ignorable_Code_Point``
  were removed by nothing and reported by nothing, so ``pay`` + ``U+1D173`` + ``pal``
  survived every entry point and screened clean. That is the worked example from
  ``docs/user-guide/anomaly-detection.md``, which is caught with ``U+200B``.
* #812 — a run of Private Use Area code points was removed by ``canonicalize`` and
  reported by nothing, so a guardrail screening with ``has_anomalies`` passed exactly
  what the comparison presets had already decided was not text.
* #814 — ``ProfileSpec`` had no PUA field, so ``llm_guardrail`` could not strip the
  Private Use Area even in principle.

Every assertion here fails on ``0.14.1``.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

import disarm

# U+1BCA0–U+1BCA3 Duployan shorthand format letters, U+1D173–U+1D17A musical symbol
# BEGIN/END BEAM, TIE, SLUR, PHRASE. Escapes rather than literals: each renders as
# nothing, so a literal would be indistinguishable from a typo (#802).
DEFAULT_IGNORABLE_FORMATS = [chr(c) for c in [*range(0x1BCA0, 0x1BCA4), *range(0x1D173, 0x1D17B)]]

# `Cf` code points that survive `strip_format` and *should*: they render, and they carry
# meaning. Arabic number signs, Kaithi number signs, Egyptian hieroglyph layout controls.
RENDERING_CF = [chr(c) for c in (0x0600, 0x06DD, 0x070F, 0x0890, 0x110BD, 0x13430)]

# BMP Private Use Area. An escape rather than a literal for the #802 reason: a PUA code
# point renders as whatever the reader's font decides, including nothing.
PUA = "\ue000"


class TestDefaultIgnorableFormats:
    """#813."""

    @pytest.mark.parametrize("ch", DEFAULT_IGNORABLE_FORMATS, ids=lambda c: f"U+{ord(c):04X}")
    def test_it_is_removed_by_every_stripping_surface(self, ch: str) -> None:
        split = f"pay{ch}pal"
        assert disarm.strip_format(split) == "paypal"
        assert disarm.canonicalize(split) == "paypal"
        assert disarm.canonicalize_strict(split) == "paypal"
        assert disarm.strip_obfuscation(split) == "paypal"
        assert disarm.get_pipeline("llm_guardrail")(split) == "paypal"

    @pytest.mark.parametrize("ch", DEFAULT_IGNORABLE_FORMATS, ids=lambda c: f"U+{ord(c):04X}")
    def test_it_is_reported(self, ch: str) -> None:
        assert disarm.has_anomalies(f"pay{ch}pal")
        assert "invisible" in disarm.inspect_anomalies(f"pay{ch}pal").kinds

    @pytest.mark.parametrize("ch", RENDERING_CF, ids=lambda c: f"U+{ord(c):04X}")
    def test_a_cf_that_renders_is_still_kept(self, ch: str) -> None:
        """The fix must not widen to every ``Cf``: 29 of them carry meaning."""
        assert unicodedata.category(ch) == "Cf"
        assert disarm.strip_format(f"a{ch}b") == f"a{ch}b"

    def test_the_class_is_exactly_the_default_ignorable_survivors(self) -> None:
        """Anchored to the property, not to the list — the #806 lesson.

        A gate that re-states the twelve code points it is checking passes by
        construction. This asks the question the issue asked: which ``Cf`` code points
        survive ``strip_format``, and is any of them invisible?
        """
        survivors = {
            cp
            for cp in range(0x110000)
            if unicodedata.category(chr(cp)) == "Cf" and disarm.strip_format(f"a{chr(cp)}b") != "ab"
        }
        still_ignorable = survivors & {ord(c) for c in DEFAULT_IGNORABLE_FORMATS}
        assert not still_ignorable, (
            f"invisible Cf survives strip_format: {[hex(c) for c in sorted(still_ignorable)]}"
        )


class TestPrivateUseArea:
    """#812 (the detection half) and #814 (the profile half)."""

    def test_a_run_is_reported(self) -> None:
        assert disarm.has_anomalies("Hello " + PUA * 4)
        assert "invisible" in disarm.inspect_anomalies("Hello " + PUA * 4).kinds

    def test_one_is_not_reported(self) -> None:
        """A single PUA code point beside a letter is an icon-font glyph.

        This is the reason it is a run rule rather than a neighbour rule, and it is why
        ``strip_format`` keeps the block at all (#413).
        """
        assert not disarm.has_anomalies("Menu " + PUA)

    @pytest.mark.parametrize(
        "profile",
        [
            "library_catalog_key_eu",
            "llm_guardrail",
            "ml_corpus_normalize",
            "normalize_web_input",
            "rag_ingest",
            "scholarly_cyrillic_iso9",
            "search_index",
        ],
    )
    def test_the_comparison_profiles_strip_it(self, profile: str) -> None:
        out = disarm.get_pipeline(profile)("Hello" + PUA * 3)
        assert PUA not in out, f"{profile} passed PUA that canonicalize removes"

    def test_code_context_keeps_it(self) -> None:
        """#413's rule, not an omission: the one profile that preserves its input."""
        assert PUA in disarm.get_pipeline("code_context")("Menu " + PUA)

    def test_the_detector_and_canonicalize_agree(self) -> None:
        """The shape of the defect, stated directly.

        ``canonicalize`` deleting a run while ``has_anomalies`` reports clean is a
        guardrail passing what the comparison presets already rejected.
        """
        payload = "Hello " + PUA * 4
        assert disarm.canonicalize(payload) != payload
        assert disarm.has_anomalies(payload)


def test_a_hand_built_pipeline_does_not_strip_pua() -> None:
    """The behavioural half of the #876 review note.

    `STRIP_PUA` is set by `ProfileSpec::build` and by nothing else — it is deliberately
    not a `TextPipeline` parameter, because that constructor is the public hand-built
    path across six bindings and a new positional argument there is a breaking change
    owed to all of them. #814 is about the named profiles, which are curated
    recommendations and can take the preset policy without one.

    Asserted rather than left to the comment, since a comment claiming a setter that does
    not exist is what prompted the note.
    """
    hand_built = disarm.TextPipeline(strip_zero_width=True, strip_control=True)
    assert PUA in hand_built("Menu " + PUA)
    assert "strip_pua" not in [name for name, _ in hand_built.steps]


_E = chr(0xE000)
_LATIN_ACCENT = chr(0xE9)
_COMBINING_ACUTE = chr(0x301)
_COMBINING_CIRCUMFLEX = chr(0x302)
_CYRILLIC = "".join(chr(c) for c in range(0x430, 0x439))
_ARABIC = "".join(chr(c) for c in range(0x628, 0x631))
_HAN = "".join(chr(0x4E00 + i) for i in range(9))
_HIRAGANA = "".join(chr(c) for c in range(0x3042, 0x304B))
_KATAKANA = "".join(chr(c) for c in range(0x30A2, 0x30AB))
_HANGUL = "".join(chr(0xAC00 + i) for i in range(9))


def _spread(word: str, filler: str = _E) -> str:
    return "".join(letter + filler for letter in word)


class TestPrivateUseBetweenLetters:
    """One between two Latin letters of the same case splits a word (#1212).

    #812's reason is about a glyph beside a letter, and it stands: every other row here that
    stays clean is one. `canonicalize` removes all of them, so the detector had nothing to say
    about text the comparison presets had already rewritten.
    """

    @pytest.mark.parametrize(
        "text",
        [
            "pay" + _E + "pal",
            "PAY" + _E + "PAL",
            "pass" + chr(0xF0000) + "word",
            "pass" + chr(0x100000) + "word",
            "caf" + _E + _LATIN_ACCENT,
            "pay" + _E * 2 + "pal",
            "pay" + _E * 3 + "pal",
            "of" + chr(0xF001) + "ce",
            _spread("password"),
            _spread("PaSsWoRdX"),
            _spread(_CYRILLIC),
            _spread(_ARABIC),
            "Hello " + _E * 4,
        ],
        ids=ascii,
    )
    def test_reports(self, text: str) -> None:
        assert disarm.has_anomalies(text)
        assert "invisible" in disarm.inspect_anomalies(text).kinds

    @pytest.mark.parametrize(
        "text",
        [
            "Pay" + _E + "Pal",
            "Save" + chr(0xE001) + "File",
            "Mac" + chr(0xF8FF) + "Book",
            "Home" + chr(0xF0B7) + "About",
            "pass1" + _E + "2word",
            _CYRILLIC[0] + _E + _CYRILLIC[1],
            chr(0x4E00) + chr(0xE78D) + chr(0x4E8C),
            _spread(_CYRILLIC[:8]),
            _spread(_HAN),
            _spread(_HIRAGANA),
            _spread(_KATAKANA),
            _spread(_HANGUL),
            "Menu " + _E,
            _E + " Menu",
            "Menu" + _E,
            _E + "Menu",
            (chr(0xF0B7) + " item\n") * 8,
            "Hello " + _E * 3,
        ],
        ids=ascii,
    )
    def test_stays_clean(self, text: str) -> None:
        assert not disarm.has_anomalies(text)
        assert disarm.inspect_anomalies(text).kinds == []

    def test_a_cjk_letter_on_one_side_does_not_count(self) -> None:
        pairs = "".join(chr(0x4E00 + i) + _E + chr(0x430 + i) + " " for i in range(9))
        assert not disarm.has_anomalies(pairs)

    def test_a_letter_with_a_mark_is_still_a_letter(self) -> None:
        """One verdict for every canonically equivalent spelling, and a base keeps its mark."""
        composed = "caf" + _LATIN_ACCENT + _E + "s"
        decomposed = "cafe" + _COMBINING_ACUTE + _E + "s"
        assert disarm.has_anomalies(composed)
        assert disarm.has_anomalies(decomposed)
        assert disarm.has_anomalies("x" + _COMBINING_CIRCUMFLEX + _E + "y")

    def test_the_finding_points_at_the_whole_run(self) -> None:
        text = "pay" + _E * 3 + "pal"
        [finding] = disarm.inspect_anomalies(text).findings
        assert (finding.start, finding.end) == (3, 3 + len((_E * 3).encode()))
        assert finding.token == _E * 3
        assert "U+E000" in finding.detail
        assert "inside a word" in finding.detail

    def test_a_run_the_run_rule_reports_is_not_reported_twice(self) -> None:
        assert len(disarm.inspect_anomalies("pay" + _E * 4 + "pal").findings) == 1

    def test_the_rewrites_and_the_exemption_do_not_move(self) -> None:
        assert disarm.canonicalize("pay" + _E + "pal") == "paypal"
        assert not disarm.is_canonical("pay" + _E + "pal")
        assert _E in disarm.get_pipeline("code_context")("Menu " + _E)

    def test_the_guide_states_the_rule(self) -> None:
        guide = (
            Path(__file__).resolve().parents[1] / "docs/user-guide/anomaly-detection.md"
        ).read_text(encoding="utf-8")
        assert "between two Latin letters of the same case" in " ".join(guide.split())
        assert "a single private-use character is not an anomaly" not in " ".join(guide.split())
