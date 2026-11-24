"""Hiding data in ordinary characters: what reports, what cannot, and which page says so (#1207)."""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

import disarm
from benchmarks.meta.suites.practitioner import St3ggTextExamples

ROOT = Path(__file__).resolve().parents[1]
EN, EM, THIN, NARROW, IDEOGRAPHIC = chr(0x2002), chr(0x2003), chr(0x2009), chr(0x202F), chr(0x3000)
NBSP = chr(0xA0)
HAIR, OGHAM, MEDIUM, EN_QUAD = chr(0x200A), chr(0x1680), chr(0x205F), chr(0x2000)
COMBINING_ACUTE = chr(0x301)
COMPOSED_E = chr(0xE9)


def _page(relative: str) -> str:
    return " ".join((ROOT / relative).read_text(encoding="utf-8").split())


def _example(name: str) -> str:
    root = St3ggTextExamples().locate()
    if root is None:
        pytest.skip("ST3GG is not cached")
    with open(root / name, encoding="utf-8", newline="") as fh:
        return fh.read()


# --- two kinds of exotic space ---------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "the" + EN + "quick" + EM + "brown",
        "one" + EN + "two three" + THIN + "four",
        "the" + EN + EM + "quick",
        "the" + HAIR + "quick" + OGHAM + "brown",
        "the" + MEDIUM + "quick" + NARROW + "brown",
        "the" + IDEOGRAPHIC + "quick" + EM + "brown",
    ],
    ids=ascii,
)
def test_two_kinds_of_exotic_space_report(text: str) -> None:
    assert disarm.has_anomalies(text)
    assert disarm.inspect_anomalies(text).kinds == ["compat_fold"]


@pytest.mark.parametrize(
    "text",
    [
        "Mr." + THIN + "Smith",
        "10" + NBSP + "km",
        "Mr." + NBSP + "Smith",
        "the" + EM + "quick" + EM + "brown" + EM + "fox",
        "10" + NBSP + "km and " + "Mr." + THIN + "Smith",
        "20" + NARROW + "000" + NBSP + "km",
        "two" + IDEOGRAPHIC + "words",
        chr(0x65E5) + IDEOGRAPHIC + chr(0x672C),
        "plain words",
    ],
    ids=ascii,
)
def test_one_kind_is_a_space_doing_its_job(text: str) -> None:
    assert not disarm.has_anomalies(text)
    assert disarm.inspect_anomalies(text).kinds == []


def test_the_finding_points_at_the_first_exotic_space() -> None:
    text = "the" + EN + "quick" + EM + "brown"
    [finding] = disarm.inspect_anomalies(text).findings
    assert (finding.start, finding.end) == (3, 3 + len(EN.encode()))
    assert finding.token == EN
    assert "2 kinds of exotic space" in finding.detail


def test_canonicalize_folds_them_and_the_output_reads_clean() -> None:
    text = "the" + EN + "quick" + EM + "brown"
    assert disarm.canonicalize(text) == "the quick brown"
    assert not disarm.has_anomalies(disarm.canonicalize(text))


def test_a_text_s_two_normal_forms_get_one_verdict() -> None:
    """`U+2000` is a singleton for `U+2002`, so it is judged as spelled, as the guide says."""
    text = "the" + EN_QUAD + "quick" + EN + "brown"
    assert disarm.has_anomalies(text)
    nfc, nfd = unicodedata.normalize("NFC", text), unicodedata.normalize("NFD", text)
    assert disarm.has_anomalies(nfc) == disarm.has_anomalies(nfd)


def test_the_st3gg_file_reports_when_it_is_cached() -> None:
    assert disarm.has_anomalies(_example("example_confusable_whitespace.txt"))


# --- the two that stay silent, as stated limits ----------------------------


def test_a_mix_of_nfc_and_nfd_gets_one_verdict_and_is_normalized_answers() -> None:
    """A report would give two verdicts for one canonically equivalent text."""
    mixed = "caf" + COMPOSED_E + " cafe" + COMBINING_ACUTE
    assert not disarm.has_anomalies(mixed)
    assert not disarm.is_normalized(mixed, form="NFC")
    assert not disarm.has_anomalies(unicodedata.normalize("NFC", mixed))


def test_the_st3gg_normalization_file_stays_clean_when_it_is_cached() -> None:
    text = _example("example_normalization.txt")
    assert not disarm.has_anomalies(text)
    assert not disarm.is_normalized(text, form="NFC")


def test_trailing_whitespace_stays_clean_and_canonicalize_removes_it() -> None:
    text = "the quick \t\nbrown fox\t \nover it  \n"
    assert not disarm.has_anomalies(text)
    assert "\t" not in disarm.canonicalize(text)


def test_the_st3gg_whitespace_file_stays_clean_when_it_is_cached() -> None:
    assert not disarm.has_anomalies(_example("example_whitespace.txt"))


# --- the pages -------------------------------------------------------------

SENTENCE = (
    "Two ways of hiding data in ordinary characters report nothing. A mix of NFC and NFD gets "
    "one verdict, because canonically equivalent text always does; use `is_normalized`. "
    "Trailing spaces and tabs are plain ASCII, and no rule reads them. `canonicalize` removes "
    "both."
)


@pytest.mark.parametrize("page", ["docs/user-guide/anomaly-detection.md", "docs/limitations.md"])
def test_both_pages_name_them(page: str) -> None:
    text = _page(page)
    assert SENTENCE in text
    assert "two or more kinds of exotic space" in text


def test_the_corpora_page_says_what_the_row_s_input_is() -> None:
    text = _page("docs/security/adversarial-corpora.md")
    assert "`whitespace steganography` row" in text
    assert "`U+200B U+200C U+200B U+200C`" in text
    assert "not whitespace" in text


def test_the_threshold_sits_beside_the_720_comment() -> None:
    source = (ROOT / "src/anomalies.rs").read_text(encoding="utf-8")
    at = source.index("Whitespace is excluded from the trigger (#720)")
    assert "#1207" in source[at : at + 900]
