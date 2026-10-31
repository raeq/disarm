"""#769/#770/#772 — three limits that were true and unwritten.

None of these is a defect. Each is a place where two things that look like they answer the
same question do not, and no page said so — which is the shape that costs a caller a wrong
assumption rather than a crash.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

import disarm

ROOT = Path(__file__).resolve().parent.parent
LIMITATIONS = ROOT / "docs" / "limitations.md"
WHICH = ROOT / "docs" / "concepts" / "which-function.md"

#: `Default_Ignorable_Code_Point`, as ranges. Written out because `unicodedata` exposes no
#: predicate for it — the derived property is not one of the fields it carries.
DEFAULT_IGNORABLE_RANGES = (
    (0x00AD, 0x00AD),
    (0x034F, 0x034F),
    (0x061C, 0x061C),
    (0x115F, 0x1160),
    (0x17B4, 0x17B5),
    (0x180B, 0x180F),
    (0x200B, 0x200F),
    (0x202A, 0x202E),
    (0x2060, 0x206F),
    (0x3164, 0x3164),
    (0xFE00, 0xFE0F),
    (0xFEFF, 0xFEFF),
    (0xFFA0, 0xFFA0),
    (0xFFF0, 0xFFF8),
    (0x1BCA0, 0x1BCA3),
    (0x1D173, 0x1D17A),
    (0xE0000, 0xE0FFF),
)


def default_ignorable() -> list[str]:
    return [
        chr(cp)
        for start, end in DEFAULT_IGNORABLE_RANGES
        for cp in range(start, end + 1)
        if unicodedata.category(chr(cp)) != "Cn"
    ]


# ── #769: whole string vs one token ──────────────────────────────────────────


def test_the_two_bidi_checks_disagree_across_a_space() -> None:
    """The example both the docstring and the routing table now carry."""
    across = "hello שלום"
    assert disarm.has_bidi_conflict(across), "the whole-string check should see the mix"
    assert disarm.inspect_anomalies(across).kinds == [], (
        "the token-scoped check should see two clean words"
    )


def test_they_agree_within_one_token() -> None:
    """The other half: with no space, both fire. Pinned so the contrast stays a contrast."""
    joined = "helloשלום"
    assert disarm.has_bidi_conflict(joined)
    assert "bidi_mixed" in disarm.inspect_anomalies(joined).kinds


def test_the_routing_table_now_names_both() -> None:
    """#769's actual complaint: the table routed only to the token-scoped one."""
    page = WHICH.read_text(encoding="utf-8")
    assert "has_bidi_conflict" in page, "the routing table still omits the whole-string check"
    assert "single token" in page and "across a whole string" in page


# ── #770: the primitives do not compose to toNFKC_Casefold ───────────────────


def test_nfkc_plus_fold_case_removes_no_default_ignorables() -> None:
    """The claim on the page, as a measurement.

    The interesting number is zero: not "few survive" but "none are removed", which is
    what makes the composition the wrong tool rather than an approximate one.
    """
    ignorable = default_ignorable()
    removed = [ch for ch in ignorable if disarm.fold_case(disarm.normalize(ch, form="NFKC")) == ""]
    assert removed == [], (
        f"fold_case(normalize(s, NFKC)) now removes {len(removed)} Default_Ignorable code "
        "points; docs/limitations.md says it removes none"
    )
    documented = "removes **none of them**" in LIMITATIONS.read_text(encoding="utf-8")
    assert documented, "the #770 section no longer states the result it was written for"


def test_canonicalize_is_the_one_that_removes_them() -> None:
    """The page's recommendation, checked as a floor rather than an exact count."""
    ignorable = default_ignorable()
    removed = [ch for ch in ignorable if disarm.canonicalize(ch) == ""]
    assert len(removed) > 350, (
        f"canonicalize now removes only {len(removed)} of {len(ignorable)}; the page "
        "recommends it as the stand-in for the missing toNFKC_Casefold step"
    )


def test_the_survivors_are_the_ones_the_page_lists() -> None:
    """#858 review: the page named the variation selectors, which do not survive.

    `COMPARISON_STRIP` removes every variation selector including the presentation ones —
    that is what a comparison policy is for. What survives is four blocks of
    script-specific formatting controls, and the page now says so. Asserted by range so
    a newly assigned code point inside one of them does not fail the page.
    """
    survivors = {ord(ch) for ch in default_ignorable() if disarm.canonicalize(ch) != ""}
    documented = (
        (0x17B4, 0x17B5),  # Khmer inherent vowels
        (0x180B, 0x180F),  # Mongolian free variation selectors
        (0x1BCA0, 0x1BCA3),  # Duployan shorthand format controls
        (0x1D173, 0x1D17A),  # musical beam/tie/slur/phrase controls
    )
    unexpected = sorted(cp for cp in survivors if not any(lo <= cp <= hi for lo, hi in documented))
    assert not unexpected, (
        "docs/limitations.md lists the Default_Ignorable code points canonicalize keeps; "
        f"these survive and are not on it: {[f'U+{cp:04X}' for cp in unexpected]}"
    )
    assert not any(0xFE00 <= cp <= 0xFE0F for cp in survivors), (
        "a variation selector now survives canonicalize; the page says none does"
    )


def test_the_soft_hyphen_example_on_the_page_is_real() -> None:
    # Escapes, per #802: a literal soft hyphen renders as nothing and reads as smuggling.
    assert disarm.fold_case(disarm.normalize("a\u00ada", form="NFKC")) == "a\u00ada"


# ── #772: a registered IVS and an arbitrary base + selector ──────────────────

#: A registered Ideographic Variation Sequence, and a base that cannot form one.
REGISTERED_IVS = "葛\U000e0100"
NOT_A_SEQUENCE = "A\U000e0100"


@pytest.mark.parametrize("name", ["canonicalize", "strip_format", "strip_obfuscation"])
def test_no_surface_distinguishes_the_two(name: str) -> None:
    """Both lose the selector, which is the fidelity loss the page now records."""
    fn = getattr(disarm, name)
    assert fn(REGISTERED_IVS) == "葛"
    assert fn(NOT_A_SEQUENCE) == "A"


def test_neither_is_reported() -> None:
    """The security-relevant half: a base carrying an unjustified ignorable selector."""
    assert disarm.inspect_anomalies(REGISTERED_IVS).kinds == []
    assert disarm.inspect_anomalies(NOT_A_SEQUENCE).kinds == []


def test_the_page_records_it() -> None:
    page = LIMITATIONS.read_text(encoding="utf-8")
    assert "Ideographic Variation Sequences are not distinguished" in page


# --- Named boundaries a reader looks for (#1159, #1167, #1168) -----------------

_ROOT = Path(__file__).resolve().parent.parent
_SENTENCE = "the quick brown fox"


def _flat(relative: str) -> str:
    return " ".join((_ROOT / relative).read_text(encoding="utf-8").split())


def _surfaces():
    return {
        "canonicalize": disarm.canonicalize,
        "llm_guardrail": disarm.get_pipeline("llm_guardrail"),
        "rag_ingest": disarm.get_pipeline("rag_ingest"),
        "strip_obfuscation": disarm.strip_obfuscation,
    }


#: Text a renderer hides, built around one word. Nothing is copied from a project using them.
RENDERER_HIDES = {
    "html comment": "before <!-- note --> after",
    "reference definition": "before\n\n[//]: # (note)\n\nafter",
    "details block": "before <details>note</details> after",
    "image alt text": "before ![note](x.png) after",
    "link title": 'before [a](x "note") after',
    "hidden attribute": "before <span hidden>note</span> after",
    "white span": 'before <span style="color:white">note</span> after',
    "front matter": "---\ntitle: note\n---\nbody",
}


@pytest.mark.parametrize("text", RENDERER_HIDES.values(), ids=RENDERER_HIDES)
def test_text_a_renderer_hides_is_clean_at_the_character_level(text: str) -> None:
    assert not disarm.has_anomalies(text)


@pytest.mark.parametrize(
    "surface", ["canonicalize", "llm_guardrail", "rag_ingest", "strip_obfuscation"]
)
@pytest.mark.parametrize("text", RENDERER_HIDES.values(), ids=RENDERER_HIDES)
def test_text_a_renderer_hides_survives_every_surface(text: str, surface: str) -> None:
    assert "note" in _surfaces()[surface](text).lower()


def test_the_threat_model_states_the_renderer_boundary() -> None:
    assert (
        "**Text a renderer hides.** An HTML comment, a Markdown reference definition, a "
        "`details` block, alt text or a hidden attribute holds ordinary characters, so disarm "
        "reports nothing and removes nothing. The page a person reads and the text a model "
        "receives can then differ. Render or strip the markup yourself before retrieval or "
        "review if your pipeline depends on the two matching."
    ) in _flat("THREAT_MODEL.md")


def test_the_llm_guide_points_at_the_renderer_boundary_where_it_recommends_rag_ingest() -> None:
    page = _flat("docs/user-guide/llm-pipelines.md")
    assert "Text a renderer hides" in page


def _caesar(text: str, shift: int = 3) -> str:
    return "".join(chr((ord(c) - 97 + shift) % 26 + 97) if c.islower() else c for c in text)


def _atbash(text: str) -> str:
    return "".join(chr(219 - ord(c)) if c.islower() else c for c in text)


#: Each follows the project's own description, on a benign sentence.
NAMED_ASCII_ATTACKS = {
    "FlipAttack, word order": " ".join(reversed(_SENTENCE.split())),
    "FlipAttack, letters in each word": " ".join(w[::-1] for w in _SENTENCE.split()),
    "FlipAttack, whole sentence": _SENTENCE[::-1],
    "CipherChat, Caesar": _caesar(_SENTENCE),
    "CipherChat, Atbash": _atbash(_SENTENCE),
    "CipherChat, Morse": "- .... . / --.- ..- .. -.-. -.-",
    "CipherChat, ASCII codes": " ".join(str(ord(c)) for c in _SENTENCE),
    "CipherChat, UTF-8 hex": _SENTENCE.encode().hex(),
    "BitBypass, hyphen-separated binary": "-".join(format(ord(c), "08b") for c in "fox"),
    "ArtPrompt, block letter": " ___ \n|_ _|\n | | \n |_| ",
}


@pytest.mark.parametrize("text", NAMED_ASCII_ATTACKS.values(), ids=NAMED_ASCII_ATTACKS)
def test_a_named_ascii_attack_is_ordinary_ascii_to_disarm(text: str) -> None:
    assert text.isascii()
    assert not disarm.has_anomalies(text)
    assert not disarm.decode_smuggled(text)


def test_the_threat_model_names_the_four_attacks() -> None:
    assert (
        "FlipAttack (reordered words and letters), CipherChat (classical ciphers and character "
        "codes), BitBypass (binary spelled in ASCII) and ArtPrompt (ASCII art) all fall here: "
        "each is ordinary ASCII to disarm, which reports nothing and decodes nothing."
    ) in _flat("THREAT_MODEL.md")


@pytest.mark.parametrize("name", ["FlipAttack", "CipherChat", "ArtPrompt", "BitBypass"])
def test_the_source_ledger_records_each_as_read_and_left_out(name: str) -> None:
    rows = [
        line
        for line in (_ROOT / "benchmarks/meta/README.md").read_text(encoding="utf-8").splitlines()
        if line.startswith(f"| {name}")
    ]
    assert rows, name
    assert "left out" in rows[0]


UTF7_BYTES = b"+ADw-b+AD4-note+ADw-/b+AD4-"


def test_utf7_bytes_read_as_ascii_and_report_nothing() -> None:
    assert disarm.detect_encoding(UTF7_BYTES) == ("UTF-8", 0.95)
    text, had_errors = disarm.decode_to_utf8(UTF7_BYTES)
    assert not had_errors
    assert "<" not in text
    assert not disarm.has_anomalies(text)


def test_a_utf7_decoder_reads_what_disarm_was_not_shown() -> None:
    assert UTF7_BYTES.decode("utf-7") == "<b>note</b>"


def test_the_threat_model_states_the_charset_boundary() -> None:
    assert (
        "**Charset confusion between two decoders.** disarm reads the bytes one way. If a later "
        "component decodes the same bytes differently, as UTF-7 or a legacy Chinese charset can "
        "be, then disarm examined text that component never saw. Fix the charset at the boundary "
        "and pass `str`, or use `decode_to_utf8` with an explicit encoding."
    ) in _flat("THREAT_MODEL.md")


def test_the_encoding_page_names_utf7() -> None:
    assert "UTF-7" in _flat("docs/api/encoding.md")


def test_the_limitations_cross_reference_names_what_the_threat_model_says() -> None:
    """It said the threat model scopes out "the ambiguous-bytes case", a phrase it never uses."""
    page = _flat("docs/limitations.md")
    assert "ambiguous-bytes" not in page
    assert "Charset confusion between two decoders" in page
