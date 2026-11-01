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


# --- Styles that have no answer in Unicode (#1138) -------------------------------

PARENTHESIZED = "\u24af\u24a3\u24a0"
REGIONAL = "\U0001f1f9\U0001f1ed\U0001f1ea"
TURNED = "\u0287\u0265\u01dd"


def test_parenthesized_letters_fold_to_their_parentheses() -> None:
    assert disarm.canonicalize(PARENTHESIZED) == "(t)(h)(e)"
    assert disarm.has_anomalies(PARENTHESIZED)


def test_regional_indicators_have_no_signal_and_two_surfaces_disagree() -> None:
    assert disarm.canonicalize(REGIONAL) == REGIONAL
    assert disarm.get_pipeline("llm_guardrail")(REGIONAL) == REGIONAL
    assert disarm.get_pipeline("rag_ingest")(REGIONAL) == ""
    assert not disarm.has_anomalies(REGIONAL)


def test_turned_letters_are_distinct_letters_and_are_kept() -> None:
    assert disarm.canonicalize(TURNED) != "the"
    assert not disarm.has_anomalies(TURNED)


@pytest.mark.parametrize(
    "sentence",
    [
        "Parenthesized letters fold to `(a)`, because NFKC and UTS #39 define them that way. "
        "`the` written in `U+24AF U+24A3 U+24A0` becomes `(t)(h)(e)`, so a word filter after the "
        "fold does not match it. `has_anomalies` reports `compat_fold`.",
        "Regional indicators have no compatibility mapping and no confusable row. `canonicalize`, "
        "`search_key` and `llm_guardrail` keep them, `rag_ingest` deletes them, and "
        "`has_anomalies` is False.",
        "Turned letters such as `U+0250` and `U+0287` are distinct letters with no decomposition. "
        "They are kept, and a transliterating surface may give a different letter. A text "
        "reversed as well as turned has no recoverable form.",
    ],
    ids=["parenthesized", "regional", "turned"],
)
def test_the_limitations_page_says_what_each_style_does(sentence: str) -> None:
    assert sentence in " ".join(LIMITATIONS.read_text(encoding="utf-8").split())


@pytest.mark.parametrize("name", ["parenthesized letters", "regional indicators", "turned letters"])
def test_the_corpus_table_names_each_style(name: str) -> None:
    page = (ROOT / "docs/security/adversarial-corpora.md").read_text(encoding="utf-8")
    assert f"| `{name}` |" in page


# --- The seam guide and the upgrade note (#1157, #1139) --------------------------

RUSSIAN = "\u043f\u0440\u0438\u0432\u0435\u0442"


def test_the_seam_section_says_non_latin_input_is_a_wrong_function_case() -> None:
    assert (
        "Non-Latin text is one such case. `canonicalize`, `llm_guardrail` and "
        "`strip_obfuscation` fold letters that have a Latin look-alike and keep the others, so "
        "a clean Russian or Hebrew word usually comes back as a mix that reports `mixed_script` "
        "or `bidi_mixed`. Use `rag_ingest` to romanize it, or leave it alone if it goes straight "
        "to a multilingual model."
    ) in " ".join((ROOT / "docs/user-guide/anomaly-detection.md").read_text("utf-8").split())


def test_the_llm_guide_shows_a_word_that_folds_partly() -> None:
    page = (ROOT / "docs/user-guide/llm-pipelines.md").read_text(encoding="utf-8")
    assert disarm.canonicalize(RUSSIAN) in page
    assert '"\\u043f\\u0440\\u0438\\u0432\\u0435\\u0442"' in page or RUSSIAN in page


def test_a_partly_folded_word_is_what_the_seam_check_sees() -> None:
    folded = disarm.canonicalize(RUSSIAN)
    assert not disarm.has_anomalies(RUSSIAN)
    assert folded != RUSSIAN
    assert not folded.isascii()
    assert disarm.has_anomalies(folded)
    assert not disarm.has_anomalies(disarm.get_pipeline("rag_ingest")(RUSSIAN))


def _changelog_section(version: str) -> str:
    """One release's section, flat. The 0.18.0 sentence below is in two of them, so a check of
    the whole file passes with no edit to the note (#1139)."""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    start = text.index(f"\n## [{version}]")
    return " ".join(text[start : text.index("\n## [", start + 1)].split())


PROFILES_MOVED_IN_0_18_0 = (
    "The profiles move too, and the fixture does not track them: `llm_guardrail` and "
    "`ml_corpus_normalize` on all 105, `normalize_web_input` on the 68, and `search_index`, "
    "`library_catalog_key_eu`, `rag_ingest` and `scholarly_cyrillic_iso9` on 44. So do "
    "`normalize_user_input` and `security_clean`, on the 68. If you stored a key built with "
    "`search_index` or `library_catalog_key_eu` from text that can hold a character new in "
    "Unicode 18, recompute it."
)


def test_the_0_18_0_note_names_the_profiles_that_moved() -> None:
    assert PROFILES_MOVED_IN_0_18_0 in _changelog_section("0.18.0")


def test_the_0_19_0_notes_say_the_0_18_0_note_was_short() -> None:
    assert PROFILES_MOVED_IN_0_18_0 in _changelog_section("0.19.0")


def test_the_reserved_code_point_note_says_which_profiles_moved() -> None:
    """The fixture's README asks this of any note that moves a key (#1139). Measured from the
    0.18.0 wheel on the 3,738 code points, alone, after `a`, before U+0301, after `a` + U+0301
    and between two letters, and every context agrees."""
    assert (
        "`code_context`, `llm_guardrail`, `ml_corpus_normalize` and `normalize_web_input` move on "
        "all 3,738, and so do `normalize_user_input` and `security_clean`. `search_index`, "
        "`library_catalog_key_eu`, `rag_ingest` and `scholarly_cyrillic_iso9` move on none, "
        "because each one removed them already, so a key built with one of those does not move."
    ) in _changelog_section("0.19.0")


def test_the_fixture_readme_says_what_the_counter_speaks_for() -> None:
    flat = " ".join(
        (ROOT / "tests/fixtures/key_stability/README.md").read_text(encoding="utf-8").split()
    )
    assert "`KEY_SCHEMA_VERSION` speaks for the eight functions this fixture tracks" in flat
    assert "not for a profile" in flat


def test_a_profile_moved_on_the_change_the_note_describes() -> None:
    assert disarm.get_pipeline("normalize_web_input")("a\u209db") == "awb"
    assert disarm.canonicalize("\u209d") == "w"


# --- Named boundaries a reader looks for (#1159, #1167, #1168) -----------------

_SENTENCE = "the quick brown fox"


def _flat(relative: str) -> str:
    return " ".join((ROOT / relative).read_text(encoding="utf-8").split())


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
        for line in (ROOT / "benchmarks/meta/README.md").read_text(encoding="utf-8").splitlines()
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
