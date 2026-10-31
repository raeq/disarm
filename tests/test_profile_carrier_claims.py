"""What the pages say two profiles do with each carrier class (#1122, #1123, #1124).

Every doc gate reads fenced code, and none reads a table or a sentence, which is how three
false statements stayed on these pages: `code_context` "removes the invisible classes" and
keeps the TAG block and every selector; `normalize_web_input` does "no zero-width or control
stripping" and does both; `TextPipeline` "does not support" two arguments it has taken since
#139. Each statement is measured here and then read off the page.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import disarm
from disarm import TextPipeline, decode_smuggled, get_pipeline, has_anomalies, inspect_anomalies

ROOT = Path(__file__).resolve().parent.parent
LLM = ROOT / "docs" / "user-guide" / "llm-pipelines.md"
TEMPLATES = ROOT / "docs" / "policy-templates.md"
CODE = get_pipeline("code_context")
WEB = get_pipeline("normalize_web_input")

#: Pinned as a decision: #413, #914 and #1122 for `code_context`, #1123 for the web profile.
KEPT, REMOVED = "kept", "removed"
CODE_CONTEXT = [
    ("\U000e0041", KEPT),  # TAG block
    ("\U000e0100", KEPT),  # VS17
    ("\ufe00", KEPT),  # VS1
    ("\ufe0e", KEPT),  # VS15
    ("\ufe0f", KEPT),  # VS16
    ("\u034f", KEPT),  # CGJ
    ("\ue000", KEPT),  # PUA
    ("\x0b", KEPT),  # VT, in the whitespace set (#433)
    ("\x85", KEPT),  # NEL, likewise
    ("\u200b", REMOVED),
    ("\u202e", REMOVED),
    ("\x01", REMOVED),
    ("\x9f", REMOVED),
]
NORMALIZE_WEB_INPUT = [
    ("\u200b", REMOVED),
    ("\x01", REMOVED),
    ("\ue000", REMOVED),
    ("\u202e", KEPT),
    ("\U000e0041", KEPT),
    ("\ufe00", KEPT),
    ("\U000e0100", KEPT),
]


def _outcome(pipeline, ch: str) -> str:
    out = pipeline(f"a{ch}b")
    if out == "ab":
        return REMOVED
    assert out == f"a{ch}b", repr(out)
    return KEPT


def _prose(path: Path) -> str:
    """The page with its line wrapping and admonition indent folded away."""
    return " ".join(path.read_text(encoding="utf-8").split())


@pytest.mark.parametrize(("ch", "expected"), CODE_CONTEXT)
def test_code_context_keeps_and_removes_what_the_page_says(ch: str, expected: str) -> None:
    assert _outcome(CODE, ch) == expected


@pytest.mark.parametrize(("ch", "expected"), NORMALIZE_WEB_INPUT)
def test_normalize_web_input_keeps_and_removes_what_the_page_says(ch: str, expected: str) -> None:
    assert _outcome(WEB, ch) == expected


def test_normalize_web_input_keeps_every_zalgo_mark_and_strict_caps_them() -> None:
    text = "a" + "\u0301" * 5
    assert WEB(text) == disarm.normalize(text, form="NFKC")
    assert disarm.canonicalize_strict(text).count("\u0301") < 5


@pytest.mark.parametrize("zero", [0xE0000, 0xE0100 - 16], ids=["tags", "selectors"])
def test_a_run_is_kept_reported_and_decodable(zero: int) -> None:
    """The report half, which the page now states. VS17 carries the byte 0x10."""
    src = "# fine" + "".join(chr(zero + byte) for byte in b"hidden")
    assert CODE(src) == src
    assert "smuggled" in inspect_anomalies(src).kinds
    assert decode_smuggled(src)[0].text == "hidden"


def test_one_selector_alone_is_not_reported() -> None:
    assert not has_anomalies("A\U000e0100")


@pytest.mark.parametrize(
    "stale",
    [
        "It removes the invisible classes and leaves the visible ones",
        "| bidi controls, zero-width, C0/C1 controls | **removed**",
        "| whitespace, case | **untouched**",
    ],
)
def test_the_guide_no_longer_makes_the_false_claims(stale: str) -> None:
    assert stale not in _prose(LLM)


@pytest.mark.parametrize(
    "claim",
    [
        "It also keeps the Private Use Area, the TAG block and every variation selector, "
        "because it exists to preserve its input.",
        "| Private Use Area, TAG block, variation selectors, `U+034F` | **kept** |",
        "| whitespace, including VT, FF, FS, GS, RS, US and NEL, and case | **untouched** |",
        "a run of tags or selectors is reported as `smuggled`",
        "One selector alone is not a run",
    ],
)
def test_the_guide_states_each_class(claim: str) -> None:
    assert claim in _prose(LLM)


@pytest.mark.parametrize(
    "stale",
    [
        "neutralizes the invisible, bidi and control classes",
        "no bidi/zero-width/control/zalgo stripping",
        "that `TextPipeline` does not support",
    ],
)
def test_the_templates_no_longer_make_the_false_claims(stale: str) -> None:
    assert stale not in _prose(TEMPLATES)


@pytest.mark.parametrize(
    "claim",
    [
        "keeps the Private Use Area, the TAG block and variation selectors, and leaves the "
        "homoglyph class",
        "it strips control and zero-width characters and the Private Use Area, and keeps bidi "
        "controls, zalgo marks, the TAG block and variation selectors.",
        "or pass `strip_zalgo` and `strip_bidi` to a composed `TextPipeline`",
        "(api/classes.md#strip_zalgo-is-a-cap-and-0-is-not-off)",
    ],
)
def test_the_templates_state_each_class(claim: str) -> None:
    assert claim in _prose(TEMPLATES)


def test_text_pipeline_takes_both_arguments_the_note_names() -> None:
    """#1124: both have run since #139."""
    assert TextPipeline(strip_bidi=False)("a\u202eb") == "a\u202eb"
    assert TextPipeline(strip_bidi=True)("a\u202eb") == "ab"
    zalgo = "a" + "\u0301" * 5
    assert TextPipeline(strip_zalgo=None)(zalgo) == zalgo
    assert disarm.normalize(TextPipeline(strip_zalgo=2)(zalgo), form="NFD") == "a" + "\u0301" * 2
