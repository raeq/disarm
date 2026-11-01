"""Substitution into a real script has no Unicode answer, and the pages say so (#1205).

No test here asks for a map from a substitution alphabet to Latin. The bar in #40 stands.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import disarm

ROOT = Path(__file__).resolve().parents[1]

#: `LATIN LETTER SMALL CAPITAL` for each letter these words use.
SMALL_CAPITAL = {
    "a": 0x1D00,
    "c": 0x1D04,
    "e": 0x1D07,
    "h": 0x29C,
    "k": 0x1D0B,
    "t": 0x1D1B,
}


def _spell_sc(word: str) -> str:
    return "".join(chr(SMALL_CAPITAL[letter]) for letter in word)


def _page(relative: str) -> str:
    return " ".join((ROOT / relative).read_text(encoding="utf-8").split()).replace("**", "")


MOSCOW = "".join(map(chr, (0x41C, 0x43E, 0x441, 0x43A, 0x432, 0x430)))
PAYPAL_LOOKALIKE = "".join(map(chr, (0x440, 0x430, 0x443, 0x440, 0x430))) + "l"
KATAKANA = "".join(map(chr, (0x30A2, 0x30A4, 0x30A6, 0x30A8)))
HIRAGANA = "".join(map(chr, (0x3042, 0x3044, 0x3046, 0x3048)))
GREEK = "".join(map(chr, (0x3B1, 0x3B2, 0x3B3)))
RUNIC = "".join(map(chr, (0x16A0, 0x16A2, 0x16A6, 0x16A8)))
OGHAM = "".join(map(chr, (0x1681, 0x1682, 0x1683, 0x1684)))


def test_rag_ingest_loses_a_latin_letter_with_no_row() -> None:
    """A stated limit. The rows move `search_key`, so they wait for a minor release."""
    rag = disarm.get_pipeline("rag_ingest")
    assert rag(_spell_sc("attack")) == ""
    assert rag(_spell_sc("the") + " report") == "H report"


def test_llm_guardrail_gives_those_letters_back() -> None:
    guardrail = disarm.get_pipeline("llm_guardrail")
    assert guardrail(_spell_sc("attack")) == "attack"
    assert guardrail(_spell_sc("the") + " report") == "the report"


def test_a_caller_who_screens_first_is_told() -> None:
    assert "confusable" in disarm.inspect_anomalies(_spell_sc("attack")).kinds


def test_the_reason_rag_ingest_has_no_fold_stands() -> None:
    rag = disarm.get_pipeline("rag_ingest")
    assert rag(MOSCOW) == "Moskva"
    assert rag(PAYPAL_LOOKALIKE) == "raural"


@pytest.mark.parametrize("text", [KATAKANA, HIRAGANA, GREEK], ids=["katakana", "hiragana", "greek"])
def test_a_living_script_stays_clean(text: str) -> None:
    assert not disarm.has_anomalies(text)


@pytest.mark.parametrize("text", [RUNIC, OGHAM], ids=["runic", "ogham"])
def test_a_text_wholly_in_runic_or_ogham_stays_clean(text: str) -> None:
    """Scope item 4 says no. A rule for two scripts would cover 879 of the 4,155 kept letters."""
    assert not disarm.has_anomalies(text)


@pytest.mark.parametrize("text", [KATAKANA, HIRAGANA, OGHAM], ids=["katakana", "hiragana", "ogham"])
def test_llm_guardrail_keeps_the_letters_no_look_alike_covers(text: str) -> None:
    assert disarm.get_pipeline("llm_guardrail")(text) == text


def test_the_fold_can_leave_part_of_a_runic_word_latin() -> None:
    """The eight rows of UTS #39, and why the output can report what the input did not."""
    word = chr(0x16B1) + chr(0x16A0) + chr(0x16D2) + chr(0x16A2)
    out = disarm.get_pipeline("llm_guardrail")(word)
    assert out != word
    assert not out.isascii()


SUBSTITUTION = (
    "Substitution into a real script is out of scope. A text that writes Latin letters as "
    "Katakana, Hiragana, Runic, Ogham or Greek by a chosen map has no Unicode answer: the fold "
    "works on look-alikes, and `rag_ingest` romanizes by sound, so neither returns the source "
    "text."
)


@pytest.mark.parametrize("page", ["THREAT_MODEL.md", "docs/security/adversarial-corpora.md"])
def test_the_class_is_named_out_of_scope(page: str) -> None:
    assert SUBSTITUTION in _page(page)


def test_the_llm_page_no_longer_says_small_capitals_pass_through() -> None:
    page = _page("docs/user-guide/llm-pipelines.md")
    assert "Braille, turned letters, small capitals" not in page
    assert (
        "A table-driven fold is enumerate-the-known: Braille, many turned letters and the other "
        "stylized variants that carry no confusable row pass through unchanged."
    ) in page


@pytest.mark.parametrize("page", ["docs/policy-templates.md", "docs/limitations.md"])
def test_the_rag_ingest_limit_is_stated(page: str) -> None:
    text = _page(page)
    assert "17 of 25 small capitals" in text
    assert "`search_key`" in text
    assert "#1205" in text


def test_the_runic_decision_is_recorded() -> None:
    text = _page("docs/limitations.md")
    assert "wholly in Runic or Ogham" in text
    assert "`mixed_script`" in text
