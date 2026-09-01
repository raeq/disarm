"""#778 — the complete bidi-control answer existed and was reachable only via a hostname.

`is_bidi_control` calls itself "the single definition of the set for the crate" and covers
all twelve UAX #9 explicit formatting characters. It and its wrapper were `pub(crate)`, so
the only public surface carrying the complete answer was `HostnameAnalysis.bidi_control` —
which meant calling `is_suspicious_hostname` on something that is not a hostname.

Three predicates, three different questions, and the point of this file is that they are
not substitutes:

| | answers |
|---|---|
| `has_bidi_control` | all 12 controls, no context |
| `inspect_anomalies` kind `bidi` | 9 of 12 — a judgement |
| `has_bidi_conflict` | strong-direction **letters**, no controls at all |

The middle row moved since #778 was filed: it measured 6 of 12, and #741 added the
embeddings, so it is 9 now. The three still held back are the *marks* — LRM, RLM and ALM —
because a lone directional mark is ordinary in right-to-left text and reporting it would
fire on any page that uses one. That is a deliberate judgement, and `has_bidi_control` is
the uncontexted counterpart for a caller who has already decided their input should carry
none at all: a filename, an identifier, a source file.
"""

from __future__ import annotations

import pytest

import disarm

#: The twelve, by name. Written as escapes (#802) — they render as nothing.
CONTROLS = {
    "LRM": "\u200e",
    "RLM": "\u200f",
    "ALM": "\u061c",
    "LRE": "\u202a",
    "RLE": "\u202b",
    "PDF": "\u202c",
    "LRO": "\u202d",
    "RLO": "\u202e",
    "LRI": "\u2066",
    "RLI": "\u2067",
    "FSI": "\u2068",
    "PDI": "\u2069",
}

#: The three the anomaly detector holds back, by design.
MARKS = ("LRM", "RLM", "ALM")


@pytest.mark.parametrize("name", CONTROLS, ids=list(CONTROLS))
def test_every_control_is_reported(name: str) -> None:
    """All twelve. This is the census the crate always had and never exposed."""
    assert disarm.has_bidi_control(f"abc{CONTROLS[name]}def")


@pytest.mark.parametrize("name", MARKS, ids=list(MARKS))
def test_the_marks_are_reported_here_and_not_by_the_detector(name: str) -> None:
    """The gap this closes, stated as the difference rather than as a count.

    A count would need updating every time the detector's judgement changes; this says
    what each surface is *for*, which does not.
    """
    text = f"abc{CONTROLS[name]}def"
    assert disarm.has_bidi_control(text), name
    assert "bidi" not in disarm.inspect_anomalies(text).kinds, name


def test_the_detector_still_reports_the_other_nine() -> None:
    """The judgement half must not have widened by accident."""
    reported = [
        name
        for name, char in CONTROLS.items()
        if "bidi" in disarm.inspect_anomalies(f"abc{char}def").kinds
    ]
    assert sorted(reported) == sorted(set(CONTROLS) - set(MARKS)), reported


def test_it_is_disjoint_from_has_bidi_conflict() -> None:
    """The two answer different questions and neither implies the other (#599)."""
    override = "invoice\u202egpj.exe"
    conflict = "varonis.com.ו"
    assert disarm.has_bidi_control(override)
    assert not disarm.has_bidi_conflict(override)
    assert not disarm.has_bidi_control(conflict)
    assert disarm.has_bidi_conflict(conflict)


def test_plain_text_is_clean() -> None:
    for text in ("plain text", "", "café", "мир", "日本語"):
        assert not disarm.has_bidi_control(text), text


def test_it_agrees_with_the_hostname_field() -> None:
    """The surface that used to be the only route to this answer."""
    for name, char in CONTROLS.items():
        host = f"abc{char}def.com"
        assert disarm.is_suspicious_hostname(host)[1].bidi_control is disarm.has_bidi_control(
            host
        ), name


def test_it_agrees_with_strip_bidi() -> None:
    """`strip_bidi` removes all twelve, so "it changed something" must match "it is there"."""
    for name, char in CONTROLS.items():
        text = f"abc{char}def"
        assert (disarm.strip_bidi(text) != text) is disarm.has_bidi_control(text), name
