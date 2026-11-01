"""A payload encoded in ordinary text is out of scope, and the pages now say so (#1208).

No preset decodes one, nothing reports one, and `decode_smuggled` reads only percent-encoding.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

import pytest

import disarm

ROOT = Path(__file__).resolve().parents[1]
SENTENCE = "please read the attached report"
B64 = base64.b64encode(SENTENCE.encode()).decode()
HEX = SENTENCE.encode().hex()
BINARY = " ".join(f"{byte:08b}" for byte in SENTENCE.encode())
PERCENT = "".join(f"%{byte:02X}" for byte in SENTENCE.encode())


def _page(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _unwrapped(text: str) -> str:
    return re.sub(r"\s+", " ", text)


@pytest.mark.parametrize("spelled", [B64, HEX, BINARY], ids=["base64", "hex", "binary"])
def test_no_detector_reports_an_encoded_payload(spelled: str) -> None:
    assert not disarm.has_anomalies(spelled)
    assert disarm.inspect_anomalies(spelled).kinds == []


@pytest.mark.parametrize("spelled", [B64, HEX, BINARY], ids=["base64", "hex", "binary"])
def test_decode_smuggled_does_not_read_them(spelled: str) -> None:
    """The decision on #729's open question: a new scheme is not added for this family."""
    assert disarm.decode_smuggled(spelled) == []


def test_decode_smuggled_reads_percent_encoding() -> None:
    assert disarm.decode_smuggled(PERCENT)[0].text == SENTENCE
    assert disarm.inspect_anomalies(PERCENT).kinds == []


@pytest.mark.parametrize("surface", ["canonicalize", "rag_ingest"])
def test_a_surface_with_no_case_fold_leaves_base64_alone(surface: str) -> None:
    fn = disarm.canonicalize if surface == "canonicalize" else disarm.get_pipeline(surface)
    assert fn(B64) == B64


def test_the_case_fold_corrupts_base64_and_decodes_nothing() -> None:
    """A side effect and not a control, which the pages have to say."""
    out = disarm.get_pipeline("llm_guardrail")(B64)
    assert out != B64
    assert SENTENCE not in out


def test_the_llm_page_names_the_family() -> None:
    page = _unwrapped(_page("docs/user-guide/llm-pipelines.md"))
    assert (
        "**The payload is encoded in ordinary text.** Base64, hex, binary, ROT-n, Morse and "
        "reversal are plain ASCII to every preset, which neither decodes nor reports them. "
        "`llm_guardrail` folds case, which happens to corrupt base64; that is a side effect "
        "and not a control. Decode under your own policy first, then pass the result in."
    ) in page


def test_coverage_and_limits_names_the_family() -> None:
    page = _page("docs/security/adversarial-defense.md")
    section = page.split("## Coverage and limits", 1)[1].split("\n## ", 1)[0]
    assert "base64" in section.lower()
    assert "side effect and not a control" in _unwrapped(section)


def test_the_threat_model_is_right_about_percent_encoding() -> None:
    page = _unwrapped(_page("THREAT_MODEL.md"))
    assert "disarm does not decode these and does not detect them" not in page
    assert (
        "disarm does not rewrite these and `inspect_anomalies` does not report them. "
        "`decode_smuggled` reads one of them, percent-encoding, once and rewrites nothing (#727)."
    ) in page
    assert "side effect and not a control" in page


@pytest.mark.parametrize("name", ["detect_encoding", "decode_to_utf8"])
def test_the_byte_charset_docstrings_say_what_they_answer(name: str) -> None:
    doc = _unwrapped(getattr(disarm, name).__doc__ or "")
    assert (
        "This answers a question about bytes and carriers, not textual encodings. "
        "It does not read base64, hex or binary; see the threat model."
    ) in doc


def test_the_decode_smuggled_docstring_says_what_it_reads() -> None:
    """Not the same sentence as the two above: percent-encoding is a textual encoding."""
    doc = _unwrapped(disarm.decode_smuggled.__doc__ or "")
    assert "It does not read base64, hex or binary; see the threat model." in doc


def test_the_predicates_page_records_the_decision() -> None:
    page = _unwrapped(_page("docs/api/predicates.md"))
    assert "It does not read base64, hex or binary" in page
    assert "#1208" in page


@pytest.mark.parametrize(
    ("relative", "anchor"),
    [
        ("src/api/safety.rs", "pub fn detect_encoding"),
        ("src/api/safety.rs", "pub fn decode_to_utf8"),
    ],
)
def test_the_rust_docs_carry_the_note(relative: str, anchor: str) -> None:
    source = _page(relative)
    before = source.split(anchor, 1)[0].rsplit("\n\n", 1)[-1]
    assert "does not read base64, hex or binary" in _unwrapped(before.replace("///", " "))
    assert not re.search(r"#\[[^\n]*\]\n///", before), "an attribute splits the doc comment"


def test_the_decode_smuggled_rust_doc_carries_the_note() -> None:
    source = _page("src/smuggled.rs")
    before = source.split("pub fn decode_smuggled", 1)[0].rsplit("\n\n", 1)[-1]
    assert "does not read base64, hex or binary" in _unwrapped(before.replace("///", " "))


def test_the_suite_says_upstreams_base64_measures_nothing() -> None:
    source = _unwrapped(_page("benchmarks/meta/README.md"))
    assert "`[Invalid input]`" in source
