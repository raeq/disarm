"""#745/#754/#760/#761 — the guide pages say what the library does.

Each correction here replaced a claim that was true of *something* and not of the thing
it was written next to: `normalize_confusables` described as NFKC-first when it is
NFC-first, `ml_normalize` recommended for Hindi as the lever that "preserves the script"
while it deletes the vowel signs, a destructive-scripts warning that stops at the Indic
scripts, and a tokenizer page that never mentions source code.

A doc correction that nothing measures is a doc correction with a shelf life.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

import disarm

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "docs" / "user-guide"
LLM = GUIDE / "llm-pipelines.md"
TOKENIZER = GUIDE / "tokenizer-preprocessing.md"

#: Sweep bound, matching the figure published on the page.
SWEEP_END = 0x30000


def test_normalize_confusables_is_not_nfkc_first() -> None:
    """#760 — the claim the page used to make, as an assertion that it is false.

    `²` is the cheap witness: NFKC gives `2`, the confusable table has no entry, and the
    two functions the page names behave differently on it.
    """
    assert disarm.normalize_confusables("²") == "²", (
        "normalize_confusables now folds a compatibility form the table does not name; "
        "the #760 warning on llm-pipelines.md needs rewriting, not deleting"
    )
    assert disarm.strip_obfuscation("²") == "2", "strip_obfuscation is no longer NFKC-first"
    assert disarm.canonicalize("²") == "2", "canonicalize is no longer NFKC-first"


def test_the_published_share_of_compatibility_forms_is_right() -> None:
    """#760 — the 4,965 / 3,722 / 75.0% figures, derived from the bundled UCD.

    Deliberately measured with `disarm.normalize`, not `unicodedata`: the interpreter
    ships UCD 15.1.0 and disarm ships 17.0.0, and the counts differ.
    """
    changed = [
        ch
        for cp in range(0x20, SWEEP_END)
        if not 0xD800 <= cp <= 0xDFFF
        for ch in (chr(cp),)
        if disarm.normalize(ch, form="NFKC") != ch
    ]
    unchanged = [ch for ch in changed if disarm.normalize_confusables(ch) == ch]
    page = LLM.read_text(encoding="utf-8")
    assert f"**{len(changed):,}**" in page, (
        f"the page's NFKC-changing total is stale; measured {len(changed):,}"
    )
    assert f"**{len(unchanged):,} unchanged" in page, (
        f"the page's unchanged total is stale; measured {len(unchanged):,}"
    )


@pytest.mark.parametrize(
    ("word", "expected", "script"),
    [
        ("हिन्दी", "हनद", "Devanagari"),
        ("मराठी", "मरठ", "Devanagari"),
        ("မြန်မာ", "မနမ", "Myanmar"),
        ("বাংলা", "বল", "Bengali"),
    ],
)
def test_ml_normalize_still_deletes_the_abugida_vowels(
    word: str, expected: str, script: str
) -> None:
    """#754 — the examples on the page, run.

    If any of these starts round-tripping, `ml_normalize` has been fixed and the section
    is now wrong in the other direction, which is the failure worth catching.
    """
    assert disarm.ml_normalize(word) == expected, f"{script}: the #754 section is stale"


@pytest.mark.parametrize("word", ["ภาษาไทย", "Привет"])
def test_the_scripts_the_page_calls_unaffected_are_unaffected(word: str) -> None:
    """#754 — the exception is half the page's opening sentence, so it is asserted too."""
    assert disarm.ml_normalize(word) == word.lower()


def test_the_per_script_deletion_table_is_right() -> None:
    """#754 — every row of the published table, over assigned code points."""
    blocks = {
        "Myanmar": (0x1000, 0x109F),
        "Devanagari": (0x0900, 0x097F),
        "Sinhala": (0x0D80, 0x0DFF),
        "Bengali": (0x0980, 0x09FF),
        "Tamil": (0x0B80, 0x0BFF),
        "Thai": (0x0E00, 0x0E7F),
    }
    page = TOKENIZER.read_text(encoding="utf-8")
    for name, (start, end) in blocks.items():
        assigned = [
            chr(cp) for cp in range(start, end + 1) if unicodedata.category(chr(cp)) != "Cn"
        ]
        deleted = sum(1 for ch in assigned if disarm.ml_normalize(ch) == "")
        row = next(line for line in page.splitlines() if line.startswith(f"| {name} |"))
        published = [int(cell.strip()) for cell in row.split("|")[2:4]]
        assert published == [deleted, len(assigned)], (
            f"{name}: page says {published}, measured [{deleted}, {len(assigned)}]"
        )


@pytest.mark.parametrize(
    ("word", "expected", "why"),
    [
        ("かばん", "かはん", "the dakuten is voicing, not decoration"),
        ("ばら", "はら", "ba/ha is a different word"),
        ("Чайковский", "Чаиковскии", "й is a letter of the alphabet"),
        ("ёлка", "елка", "ё is a letter of the alphabet"),
    ],
)
def test_strip_accents_is_destructive_beyond_the_indic_scripts(
    word: str, expected: str, why: str
) -> None:
    """#761 — the two script families the old "Indic scripts" warning sent a reader past."""
    assert disarm.strip_accents(word) == expected, why


def test_code_context_round_trips_source_and_the_others_do_not() -> None:
    """#745 — the 149-of-155 claim, and the class of exception behind the other six.

    Asserted as a floor: adding source files to the repository should not fail the page.
    """
    files = [
        path
        for pattern in ("python/**/*.py", "tests/**/*.py")
        for path in ROOT.glob(pattern)
        if path.stat().st_size < 200_000
    ][:300]
    assert len(files) > 50, "the sample collapsed; this test is no longer measuring anything"

    code = disarm.get_pipeline("code_context")
    kept = [
        p for p in files if code(p.read_text(encoding="utf-8")) == p.read_text(encoding="utf-8")
    ]
    assert len(kept) / len(files) > 0.90, (
        f"code_context now round-trips {len(kept)}/{len(files)} source files; the page "
        "says it is the structure-preserving entry point"
    )
    for name in ("canonicalize", "strip_format"):
        fn = getattr(disarm, name)
        assert not any(
            fn(p.read_text(encoding="utf-8")) == p.read_text(encoding="utf-8") for p in files
        ), f"{name} now round-trips a source file; the page says none of them do"


def test_the_zwj_exception_is_real() -> None:
    """#745 — the caveat the page adds, since it is the reason for the other six files."""
    # Escapes throughout: #802's gate exempts a ZWJ *between two literal pictographs*,
    # and these pictographs are themselves escaped, so a literal joiner here reads as
    # smuggling to it. The string the test builds is identical either way.
    literal = 'X = "\U0001f468\u200d\U0001f469\u200d\U0001f467"\n'
    out = disarm.get_pipeline("code_context")(literal)
    assert out != literal, "the ZWJ caveat on llm-pipelines.md is no longer true"
    assert "\u200d" not in out
    assert out.count("\n") == literal.count("\n"), "line structure must still be preserved"
