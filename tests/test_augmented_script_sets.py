"""#776 — three surfaces answered one question three ways.

UTS #39 §5.1 augmented script sets treat Han + Hiragana + Katakana as one writing system
(Japanese), Han + Hangul as Korean, and Han + Bopomofo as Chinese. `inspect_anomalies`
applied them; `is_mixed_script` and the hostname path did not. So `例え` was clean to the
detector, mixed-script to the predicate, and **suspicious as a hostname** — which meant
every Japanese domain name was reported as a spoof.

All three now share one resolver rather than three implementations that agree by
inspection.
"""

from __future__ import annotations

import pytest

import disarm

#: Text that resolves to a single writing system under the augmented sets.
ONE_SYSTEM = [
    ("例え", "Han + Hiragana"),
    ("例テ", "Han + Katakana"),
    ("ひらカタ", "Hiragana + Katakana"),
    ("日本語テスト", "ordinary Japanese"),
    ("例한", "Han + Hangul — Korean"),
    ("한국어", "Hangul only"),
    ("漢ㄅ", "Han + Bopomofo — Chinese"),
    ("中文", "Han only"),
]

#: Text that is genuinely mixed, and must stay so.
STILL_MIXED = [
    ("ひら한", "Japanese + Korean share no augmented set"),
    ("例えa", "Japanese + Latin — no set contains both"),
    ("аpple", "Cyrillic + Latin — the case the rule exists for"),
    ("Ρаypal", "Greek + Cyrillic + Latin"),
]


@pytest.mark.parametrize(("text", "why"), ONE_SYSTEM)
def test_one_writing_system_is_not_mixed(text: str, why: str) -> None:
    assert not disarm.is_mixed_script(text), why


@pytest.mark.parametrize(("text", "why"), STILL_MIXED)
def test_two_writing_systems_are_mixed(text: str, why: str) -> None:
    """The augmented sets narrow the answer; they must not remove it."""
    assert disarm.is_mixed_script(text), why


@pytest.mark.parametrize(("text", "why"), ONE_SYSTEM)
def test_the_hostname_path_agrees(text: str, why: str) -> None:
    """The surface #776 is really about: every Japanese domain was a reported spoof."""
    _, details = disarm.is_suspicious_hostname(f"{text}.example")
    assert not details.mixed_script, why


@pytest.mark.parametrize(("text", "why"), STILL_MIXED)
def test_the_hostname_path_still_flags_a_real_mix(text: str, why: str) -> None:
    _, details = disarm.is_suspicious_hostname(f"{text}.example")
    assert details.mixed_script, why


@pytest.mark.parametrize(("text", "_why"), ONE_SYSTEM)
def test_all_three_surfaces_agree_on_one_writing_system(text: str, _why: str) -> None:
    """The actual complaint: one question, one answer.

    Asserted together rather than separately, because the defect was never any single
    surface being wrong — it was the three of them disagreeing.
    """
    detector = "mixed_script" in disarm.inspect_anomalies(text).kinds
    predicate = disarm.is_mixed_script(text)
    _, details = disarm.is_suspicious_hostname(f"{text}.example")
    assert (detector, predicate, details.mixed_script) == (False, False, False)


def test_the_detector_stays_wider_on_purpose() -> None:
    """One difference is left, and it is a policy rather than an oversight.

    `inspect_anomalies` exempts CJK beside Latin as well, because it runs over prose and
    a Japanese sentence containing a product name in Latin is ordinary text. The
    predicate and the hostname path do not, because a *label* mixing Latin with Japanese
    is the shape the mixed-script rule exists to catch.

    Recorded here so the remaining gap is a stated choice. If it ever becomes a problem,
    this test is the place that says what the choice was.
    """
    latin_and_japanese = "例えa"
    assert "mixed_script" not in disarm.inspect_anomalies(latin_and_japanese).kinds
    assert disarm.is_mixed_script(latin_and_japanese)


def test_japanese_hostnames_are_no_longer_suspicious_for_being_japanese() -> None:
    """The user-visible consequence, stated as its own test."""
    for host in ("例え.jp", "日本語.jp", "ひらがな.example"):
        _, details = disarm.is_suspicious_hostname(host)
        assert not details.mixed_script, host
