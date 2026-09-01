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
