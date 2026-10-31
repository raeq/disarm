"""#1103: the 3,738 reserved `Default_Ignorable_Code_Point` code points.

They have no character yet, and a renderer that follows the property shows nothing for them,
so `pay` + `U+E0080` + `pal` is the shape of #813. They passed `strip_format`, `canonicalize`,
`canonicalize_strict`, `strip_obfuscation` and `llm_guardrail` untouched and reported clean.
`U+E01F0` follows directly on VS256, so the byte channel #413 closed in the selectors went
through moved up by 240 code points.

The decision is to follow the property, with no filter on assignment: a Unicode version that
assigns a character in one of these ranges changes nothing here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import disarm

ROOT = Path(__file__).resolve().parent.parent

RESERVED = [
    0x2065,
    *range(0xFFF0, 0xFFF9),
    *range(0xE0080, 0xE0100),
    *range(0xE01F0, 0xE1000),
]

#: The whole property, from `DerivedCoreProperties.txt`, as `src/hostname.rs` holds it.
DEFAULT_IGNORABLE = [
    0x00AD,
    0x034F,
    0x061C,
    *range(0x115F, 0x1161),
    *range(0x17B4, 0x17B6),
    *range(0x180B, 0x1810),
    *range(0x200B, 0x2010),
    *range(0x202A, 0x202F),
    *range(0x2060, 0x2070),
    0x3164,
    *range(0xFE00, 0xFE10),
    0xFEFF,
    0xFFA0,
    *range(0xFFF0, 0xFFF9),
    *range(0x1BCA0, 0x1BCA4),
    *range(0x1D173, 0x1D17B),
    *range(0xE0000, 0xE1000),
]

#: The six `canonicalize` keeps by decision: `docs/limitations.md`, #770.
KEPT_BY_CANONICALIZE = {0x17B4, 0x17B5, 0x180B, 0x180C, 0x180D, 0x180F}

#: What removes them. `transliterate`, `slugify`, `sanitize_filename` and the four ASCII
#: profiles removed them before this, and are not the subject.
SURFACES = {
    "strip_format": disarm.strip_format,
    "canonicalize": disarm.canonicalize,
    "canonicalize_strict": disarm.canonicalize_strict,
    "strip_obfuscation": disarm.strip_obfuscation,
    "search_key": disarm.search_key,
    "catalog_key": disarm.catalog_key,
    "sort_key": disarm.sort_key,
    "ml_normalize": disarm.ml_normalize,
    "strip_zero_width_chars": disarm.strip_zero_width_chars,
    **{f"profile:{name}": disarm.get_pipeline(name) for name in disarm.list_profiles()},
}

#: The primitives that take a different class, and the two that do not strip at all. They keep
#: `U+1D173` too, which is what "the same class" is measured against.
NOT_THEIR_JOB = {
    "normalize_confusables": disarm.normalize_confusables,
    "fold_case": disarm.fold_case,
    "strip_bidi": disarm.strip_bidi,
    "strip_tags": disarm.strip_tags,
    "strip_variation_selectors": disarm.strip_variation_selectors,
    "strip_noncharacters": disarm.strip_noncharacters,
    "strip_pua": disarm.strip_pua,
    "strip_control_chars": disarm.strip_control_chars,
}

BEAM = "\U0001d173"
SECRET = "".join(chr(0xE01F0 + byte) for byte in b"secret")


def test_the_class_is_the_size_the_issue_counts() -> None:
    assert len(RESERVED) == len(set(RESERVED)) == 3_738
    assert set(RESERVED) < set(DEFAULT_IGNORABLE)
    assert len(set(DEFAULT_IGNORABLE)) == 4_174


@pytest.mark.parametrize("name", sorted(SURFACES))
def test_every_surface_removes_every_one(name: str) -> None:
    surface = SURFACES[name]
    kept = [f"U+{cp:04X}" for cp in RESERVED if chr(cp) in surface(f"pay{chr(cp)}pal")]
    assert not kept, f"{name} keeps {len(kept)}: {kept[:5]}"


@pytest.mark.parametrize("name", sorted(NOT_THEIR_JOB))
def test_a_primitive_for_another_class_treats_them_as_it_treats_the_formats(name: str) -> None:
    surface = NOT_THEIR_JOB[name]
    assert BEAM in surface(f"pay{BEAM}pal"), f"{name} changed what it does to U+1D173"
    kept = [cp for cp in RESERVED if chr(cp) not in surface(f"pay{chr(cp)}pal")]
    assert not kept, f"{name} removes {len(kept)} of them and not U+1D173"


def test_every_one_is_reported_as_invisible() -> None:
    for template in ("pay{}pal", "hello{}", "{}hello"):
        wrong = {
            f"U+{cp:04X}": kinds
            for cp in RESERVED
            if (kinds := disarm.inspect_anomalies(template.format(chr(cp))).kinds) != ["invisible"]
        }
        assert not wrong, f"{template}: {len(wrong)}, {list(wrong.items())[:5]}"


def test_the_payload_is_gone_and_it_was_reported() -> None:
    """Both directions, as #1103 scope item 3 asks."""
    text = "hello" + SECRET
    assert disarm.canonicalize(text) == "hello"
    assert disarm.strip_format(text) == "hello"
    assert disarm.has_anomalies(text)
    assert disarm.inspect_anomalies(text).kinds == ["invisible"]
    assert not disarm.has_anomalies(disarm.canonicalize(text))


def test_the_channel_beside_the_selectors_now_behaves_like_them() -> None:
    selectors = "".join(chr(0xE0100 + byte) for byte in b"secret")
    assert disarm.canonicalize("hello" + selectors) == disarm.canonicalize("hello" + SECRET)
    assert disarm.has_anomalies("hello" + selectors)
    assert disarm.has_anomalies("hello" + SECRET)


def test_canonicalize_keeps_six_of_the_whole_property() -> None:
    kept = {cp for cp in DEFAULT_IGNORABLE if chr(cp) in disarm.canonicalize(f"a{chr(cp)}b")}
    assert kept == KEPT_BY_CANONICALIZE


@pytest.mark.parametrize("name", sorted(SURFACES))
@pytest.mark.parametrize("cp", [0x2065, 0xFFF0, 0xE0080, 0xE01F0, 0xE0FFF], ids=hex)
def test_removing_one_between_a_base_and_a_mark_is_a_fixed_point(name: str, cp: int) -> None:
    """A strip that joins `a` and U+0301 re-opens a composition an earlier step closed."""
    surface = SURFACES[name]
    for text in (f"a{chr(cp)}\u0301", f"\u0301{chr(cp)}\u0301", f"a\u0301{chr(cp)}\u0301"):
        once = surface(text)
        assert surface(once) == once, f"{name}: {text!a} -> {once!a} -> {surface(once)!a}"


def test_the_neighbours_keep_their_own_policy() -> None:
    """`strip_format` keeps VS16 after a base, and the tags and selectors are not this class."""
    assert disarm.strip_format("\u2764\ufe0f") == "\u2764\ufe0f"
    code = disarm.get_pipeline("code_context")
    assert code("a\U000e007fb") == "a\U000e007fb"
    assert code("a\U000e0100b") == "a\U000e0100b"
    assert code("a\U000e0080b") == "ab"
    assert code("a\U000e01f0b") == "ab"


def test_the_limitations_page_says_so() -> None:
    page = " ".join((ROOT / "docs" / "limitations.md").read_text(encoding="utf-8").split())
    assert "`U+2065`, `U+FFF0`–`U+FFF8`, `U+E0080`–`U+E00FF` and `U+E01F0`–`U+E0FFF`" in page
    assert "`canonicalize` keeps the same 6 of all 4,174" in page
