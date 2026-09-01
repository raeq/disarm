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
