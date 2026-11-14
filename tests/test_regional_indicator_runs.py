"""A run of regional indicators that is not a sequence of flags spells letters, so it reports (#1206).

A flag stays clean. Nothing folds: a new fold is a new capability, and a patch release adds none.
"""

from __future__ import annotations

import string
from pathlib import Path

import pytest

import disarm

ROOT = Path(__file__).resolve().parents[1]

#: `RGI_Emoji_Flag_Sequence` of Emoji 18.0, `emoji-sequences.txt`, sha256 `1823dce71f3dd9cb...`.
REGISTERED = frozenset(
    """
    AC AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ
    BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CP CQ CR CU CV CW CX CY CZ DE DG DJ
    DK DM DO DZ EA EC EE EG EH ER ES ET EU FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP
    GQ GR GS GT GU GW GY HK HM HN HR HT HU IC ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH
    KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO
    MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL
    PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV
    SX SY SZ TA TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM UN US UY UZ VA VC VE VG
    VI VN VU WF WS XK YE YT ZA ZM ZW
    """.split()
)


def _spell(word: str) -> str:
    return "".join(chr(0x1F1E6 + ord(letter) - ord("a")) for letter in word.lower())


def test_the_table_is_the_size_the_issue_states() -> None:
    assert len(REGISTERED) == 259


@pytest.mark.parametrize(
    "text",
    [
        _spell("the") + " " + _spell("quick"),
        "h" + _spell("e") + "llo",
        _spell("e") + "llo",
        "h" + _spell("e"),
        _spell("word"),
        _spell("us") + _spell("g"),
        "say " + _spell("xx") + " now",
    ],
    ids=ascii,
)
def test_a_run_that_is_not_flags_reports(text: str) -> None:
    assert disarm.has_anomalies(text)
    assert disarm.inspect_anomalies(text).kinds == ["confusable"]


@pytest.mark.parametrize(
    "text",
    [
        _spell("us"),
        _spell("us") + _spell("gb"),
        "I love " + _spell("us") + " and " + _spell("gb"),
        _spell("eu"),
        _spell("th"),
        _spell("bear"),
        _spell("e"),
        _spell("a") + " " + _spell("b"),
        "1" + _spell("e") + "2",
        "plain words",
    ],
    ids=ascii,
)
def test_a_sequence_of_flags_stays_clean(text: str) -> None:
    """`bear` is `BE` and `AR`, both registered, so a word can pass as flags, as #1206 records."""
    assert not disarm.has_anomalies(text)
    assert disarm.inspect_anomalies(text).kinds == []


@pytest.mark.parametrize("letter", string.ascii_lowercase)
def test_a_lone_indicator_keeps_the_single_code_point_guarantee(letter: str) -> None:
    """`docs/api/predicates.md`: the detector never fires on a code point `canonicalize` keeps.

    A cut message leaves half a flag by accident, as it leaves a ZWJ. Beside a letter it is
    inside a word, and no flag is.
    """
    indicator = _spell(letter)
    assert disarm.is_canonical(indicator)
    assert not disarm.has_anomalies(indicator)
    assert disarm.has_anomalies("x" + indicator)


def test_every_pair_of_letters_answers_by_the_table() -> None:
    wrong = [
        first + second
        for first in string.ascii_uppercase
        for second in string.ascii_uppercase
        if disarm.has_anomalies(_spell(first + second)) == (first + second in REGISTERED)
    ]
    assert wrong == []


def test_the_finding_points_at_the_run() -> None:
    text = "say " + _spell("the") + " now"
    [finding] = disarm.inspect_anomalies(text).findings
    assert (finding.start, finding.end) == (4, 4 + len(_spell("the").encode()))
    assert finding.token == _spell("the")
    assert "regional indicators" in finding.detail


def test_only_the_first_such_run_is_reported() -> None:
    assert len(disarm.inspect_anomalies(_spell("the") + " " + _spell("quick")).findings) == 1


@pytest.mark.parametrize("word", ["us", "the"])
def test_nothing_folds(word: str) -> None:
    """Scope item 3: `styles_recovered` stays 48 of 64."""
    spelled = _spell(word)
    assert disarm.canonicalize(spelled) == spelled
    assert disarm.get_pipeline("llm_guardrail")(spelled) == spelled


def test_the_limitation_is_replaced() -> None:
    page = " ".join((ROOT / "docs/limitations.md").read_text(encoding="utf-8").split())
    assert "A run of them that forms no flag is not reported either" not in page
    assert "`has_anomalies` is False. " not in page
    assert "that is not a sequence of registered flags reports `confusable`" in page
    assert "half a flag" in page


def test_the_guide_states_the_rule() -> None:
    guide = " ".join(
        (ROOT / "docs/user-guide/anomaly-detection.md").read_text(encoding="utf-8").split()
    )
    assert "a run of **regional indicators** that is not a sequence of registered flags" in guide
