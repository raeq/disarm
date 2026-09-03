"""Every profile says what it is for, and the sentence matches the page (#860).

`list_profiles()` returns names and `TextPipeline.steps` says what a pipeline *does*.
Neither said what a profile is *for*, which made the profiles the one part of the public
surface a reader could not evaluate without leaving the REPL.

It matters most where two profiles look alike and are not. `rag_ingest` has no confusables
step — its recovery is transliteration — so a Cyrillic look-alike of `paypal` romanizes to
`raural`, where `llm_guardrail` folds it to `paypal`. Choosing wrong there fails silently
and in the unsafe direction, which is why one sentence in the REPL is worth its keep.

**The gate is the reason this is safe to ship.** The sentence lives in `src/pipeline.rs`
and on `docs/policy-templates.md`, and two copies of one sentence in this repository have
parted company before. Every purpose must appear on that page verbatim.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import disarm

PAGE = Path(__file__).resolve().parent.parent / "docs" / "policy-templates.md"
PROFILES = sorted(disarm.list_profiles())


def test_there_are_profiles_to_check() -> None:
    """A registry that returned nothing would make every test below vacuous."""
    assert len(PROFILES) == 8, PROFILES


@pytest.mark.parametrize("profile", PROFILES)
def test_every_profile_states_a_purpose(profile: str) -> None:
    purpose = disarm.get_pipeline(profile).purpose
    assert purpose, profile
    assert purpose.endswith("."), f"{profile}: a purpose is a sentence: {purpose!r}"


@pytest.mark.parametrize("profile", PROFILES)
def test_the_purpose_appears_on_the_page_verbatim(profile: str) -> None:
    """The drift gate. Two copies of one sentence do not stay equal by good intentions."""
    page = PAGE.read_text(encoding="utf-8")
    purpose = disarm.get_pipeline(profile).purpose
    assert purpose in page, (
        f"{profile}: docs/policy-templates.md does not carry its purpose verbatim.\n  {purpose!r}"
    )


@pytest.mark.parametrize("profile", PROFILES)
def test_every_profile_has_a_section_on_the_page(profile: str) -> None:
    """Three of the eight were undocumented when this landed."""
    assert f"### {profile}" in PAGE.read_text(encoding="utf-8"), profile


def test_a_hand_built_pipeline_has_no_purpose() -> None:
    """The caller composed it and knows why; inventing a sentence would be worse."""
    assert disarm.TextPipeline(fold_case=True).purpose is None
    assert disarm.TextPipeline().purpose is None


def test_the_two_profiles_a_reader_confuses_say_how_they_differ() -> None:
    """The specific mistake this exists to prevent, asserted on both sides."""
    spoof = "раураl"  # Cyrillic р, а, у
    assert disarm.get_pipeline("llm_guardrail")(spoof) == "paypal"
    assert disarm.get_pipeline("rag_ingest")(spoof) == "raural"
    assert "folding homoglyphs" in disarm.get_pipeline("llm_guardrail").purpose
    assert "rather than folding" in disarm.get_pipeline("rag_ingest").purpose


def test_the_list_with_purposes_idiom_works() -> None:
    """`list_profiles()` stays a list of strings; this is the one line that pairs them."""
    table = {p: disarm.get_pipeline(p).purpose for p in disarm.list_profiles()}
    assert len(table) == 8
    assert all(v for v in table.values())
