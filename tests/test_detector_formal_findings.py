"""Findings of the Lean model of the anomaly detector, in ``formal/lean/Detection``.

Each class below is one finding, reproduced on the library before it was fixed:

* **Finding 1**: ``canonicalize``, ``strip_bidi`` and ``strip_format`` deleted the
  deprecated format controls ``U+206A``-``U+206F`` and the interlinear annotation
  characters ``U+FFF9``-``U+FFFB`` from inside a word while the detector reported clean.
  The set lived only in the bidi strip. Its secondary finding is the 66 noncharacters,
  which ``canonicalize`` deletes and nothing reported.
* **Finding 2**: the #741 number-run rule tested only the first ``RLM``/``ALM`` in the
  token, so a doubled mark defeated it.
* **Finding 3**: canonically equivalent spellings got different verdicts, and the
  unreported one was usually NFC.
* **Finding 4**: ``confusable`` fired on ordinary Latin orthography (``Fran\u00e7ais``)
  that the guide says is spared.

Every assertion marked as a regression fails on the ``main`` these fixes were written
against. Escapes throughout, per #802: most of these characters render as nothing.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pytest

import disarm

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "docs" / "user-guide" / "anomaly-detection.md"

DEPRECATED_OR_ANNOTATION = [chr(c) for c in [*range(0x206A, 0x2070), *range(0xFFF9, 0xFFFC)]]

NONCHARACTERS = [
    chr(c)
    for c in [
        *range(0xFDD0, 0xFDF0),
        *(plane << 16 | low for plane in range(17) for low in (0xFFFE, 0xFFFF)),
    ]
]


def _cp(ch: str) -> str:
    return f"U+{ord(ch):04X}"


class TestFinding1DeprecatedFormatControls:
    @pytest.mark.parametrize("ch", DEPRECATED_OR_ANNOTATION, ids=_cp)
    def test_it_is_deleted_by_the_strips(self, ch: str) -> None:
        split = f"pay{ch}pal"
        assert disarm.strip_bidi(split) == "paypal"
        assert disarm.strip_format(split) == "paypal"
        assert disarm.canonicalize(split) == "paypal"

    @pytest.mark.parametrize("ch", DEPRECATED_OR_ANNOTATION, ids=_cp)
    def test_it_is_reported_inside_a_word(self, ch: str) -> None:
        """Regression: clean on ``main``."""
        report = disarm.inspect_anomalies(f"pay{ch}pal")
        assert report.kinds == ["invisible"]
        assert report.findings[0].detail == _cp(ch)

    def test_it_is_not_a_bidi_control(self) -> None:
        """They are format characters, not UAX #9 controls: the census stays twelve."""
        assert not any(disarm.has_bidi_control(ch) for ch in DEPRECATED_OR_ANNOTATION)


class TestFinding1Noncharacters:
    def test_there_are_66(self) -> None:
        assert len(NONCHARACTERS) == 66
        assert all(unicodedata.category(ch) == "Cn" for ch in NONCHARACTERS)

    @pytest.mark.parametrize("ch", NONCHARACTERS, ids=_cp)
    def test_canonicalize_deletes_it_and_the_detector_reports_it(self, ch: str) -> None:
        """Regression: clean on ``main``. One is enough, as for a tag character."""
        assert disarm.canonicalize(f"pay{ch}pal") == "paypal"
        for text in (f"pay{ch}pal", ch, f"12{ch}34"):
            report = disarm.inspect_anomalies(text)
            assert report.kinds == ["invisible"], text.encode("unicode_escape")
            assert report.findings[0].detail == f"{_cp(ch)} \u00d71"

    def test_the_replacement_character_is_not_one(self) -> None:
        assert not disarm.has_anomalies("pay\ufffdpal")


def test_what_canonicalize_deletes_from_a_word_is_reported_or_a_documented_spare() -> None:
    """Finding 1 as the property rather than the list, over every scalar.

    Regression: on ``main`` this also lists ``U+206A``-``U+206F``, ``U+FFF9``-``U+FFFB``
    and the 66 noncharacters. What remains is what the guide documents as spared: the
    soft hyphen and CGJ (legitimate between letters), ``LRM``/``RLM`` (ordinary in
    right-to-left text), a lone variation selector (emoji presentation) and a single
    Private Use Area code point (an icon-font glyph).
    """

    def spared(cp: int) -> bool:
        return (
            cp in (0x00AD, 0x034F, 0x200E, 0x200F)
            or 0xFE00 <= cp <= 0xFE0F
            or 0xE0100 <= cp <= 0xE01EF
            or 0xE000 <= cp <= 0xF8FF
            or 0xF0000 <= cp <= 0xFFFFD
            or 0x100000 <= cp <= 0x10FFFD
        )

    canonicalize, has_anomalies = disarm.canonicalize, disarm.has_anomalies
    missed = [
        _cp(chr(cp))
        for cp in range(0x110000)
        if not 0xD800 <= cp <= 0xDFFF
        and not spared(cp)
        and canonicalize(f"pay{chr(cp)}pal") == "paypal"
        and not has_anomalies(f"pay{chr(cp)}pal")
    ]
    assert missed == []


class TestFinding2DoubledRtlMark:
    @pytest.mark.parametrize(
        "text",
        [
            "Transfer \u200f\u200f100 200 300 to Bob",
            "acct \u061c\u061c4321-9876",
            "acct \u200f\u061c4321-9876",
            "acct a\u200f,\u200f4321-9876",
        ],
    )
    def test_every_mark_is_tested(self, text: str) -> None:
        """Regression: clean on ``main``, which tested only the first mark."""
        assert disarm.inspect_anomalies(text).kinds == ["bidi"]

    def test_the_single_mark_still_fires(self) -> None:
        assert disarm.inspect_anomalies("Transfer \u200f100 200 300 to Bob").kinds == ["bidi"]

    @pytest.mark.parametrize("text", ["hello\u200f\u200fworld", "acct \u200f\u200fa4321"])
    def test_marks_not_before_a_number_run_are_still_spared(self, text: str) -> None:
        assert not disarm.has_anomalies(text)


#: The README's counterexamples, with the kinds both spellings must now report.
CANONICAL_PAIRS = [
    ("\u00e9t\u00e9\u2067", ["bidi"]),
    ("\u00e9\u200d\u00e9", ["invisible"]),
    ("\u00e0\u00e9\u200f1", ["bidi"]),
    ("\u00e9\u2067", ["bidi"]),
    ("Fran\u00e7ais", []),
    ("ch\u1ec9", []),
]


class TestFinding3CanonicalEquivalence:
    @pytest.mark.parametrize(("text", "kinds"), CANONICAL_PAIRS)
    def test_nfc_and_nfd_get_one_verdict(self, text: str, kinds: list[str]) -> None:
        """Regression: every pair split on ``main``."""
        nfc = unicodedata.normalize("NFC", text)
        nfd = unicodedata.normalize("NFD", text)
        assert nfc != nfd
        assert disarm.inspect_anomalies(nfc).kinds == kinds
        assert disarm.inspect_anomalies(nfd).kinds == kinds

    def test_a_canonical_singleton_is_its_target(self) -> None:
        """``U+212A KELVIN SIGN`` is canonically ``K``: no normal form keeps it, and it
        is not a disguise of the letter it is equivalent to."""
        assert unicodedata.normalize("NFD", "\u212aey") == "Key"
        assert disarm.inspect_anomalies("\u212aey").kinds == []

    def test_a_lexicon_matches_either_spelling(self) -> None:
        words = {"caf\u00e9"}
        assert disarm.inspect_anomalies("c4f\u00e9", words).kinds == ["leet"]
        assert disarm.inspect_anomalies("c4fe\u0301", words).kinds == ["leet"]

    def test_the_normalization_active_scalars_in_the_models_contexts(self) -> None:
        """The binding path of the Rust sweep in ``tests/exhaustive_anomalies.rs``.

        Every scalar with a canonical decomposition or a nonzero combining class, alone
        and in the seven contexts of the model's ``scripts/sweep_nf.py``.
        """
        contexts = [
            ("", ""),
            ("pay", "pal"),
            ("a", ""),
            ("\u00e9", "\u00e9"),
            ("", "\u2066"),
            ("\u00e9t\u00e9", "\u2067x"),
            ("\u00e9", "\u200d\u00e9"),
            ("\u00e0\u00e9", "\u200f1"),
        ]
        active = [
            chr(cp)
            for cp in range(0x110000)
            if not 0xD800 <= cp <= 0xDFFF
            and (
                unicodedata.decomposition(chr(cp)).split(" ")[0][:1] not in ("", "<")
                or unicodedata.combining(chr(cp))
            )
        ]
        assert len(active) > 2_000
        split = []
        for ch in active:
            for pre, post in contexts:
                s = pre + ch + post
                a = disarm.inspect_anomalies(unicodedata.normalize("NFC", s)).kinds
                b = disarm.inspect_anomalies(unicodedata.normalize("NFD", s)).kinds
                if a != b:
                    split.append((s.encode("unicode_escape"), a, b))
        assert split == []


#: Latin letters with a confusable fold that only drops the accent.
ACCENT_ONLY = [
    "Fran\u00e7ais",
    "gar\u00e7on",
    "T\u00fcrk\u00e7e",
    "a\u00e7\u00e3o",
    "ch\u1ec9",
    "\u00c7a",
]
#: Latin letters the fold changes in shape, with the source the finding names.
SHAPE = [
    ("K\u00f8benhavn", "\u00f8"),
    ("\u0141\u00f3d\u017a", "\u0141"),
    ("\u0111\u01b0\u1eddng", "\u0111"),
    ("\u01feslo", "\u01fe"),
    ("\u00d8slo", "\u00d8"),
    ("g\u0131thub", "\u0131"),
]


def _latin_letters_the_fold_reaches() -> list[str]:
    return [
        chr(cp)
        for cp in range(0x80, 0x110000)
        if unicodedata.category(chr(cp)) in ("Ll", "Lu", "Lt")
        and [s.value for s in disarm.detect_scripts(chr(cp))] == ["Latin"]
        and "confusable" in disarm.inspect_anomalies(f"ab{chr(cp)}cd").kinds
    ]


class TestFinding4AccentedLatin:
    @pytest.mark.parametrize("word", ACCENT_ONLY)
    def test_an_accent_the_fold_drops_is_spared(self, word: str) -> None:
        """Regression: ``confusable`` on ``main``."""
        assert disarm.inspect_anomalies(word).kinds == []

    @pytest.mark.parametrize("word", ["caf\u00e9", "na\u00efve", "stra\u00dfe"])
    def test_the_guides_examples_are_spared(self, word: str) -> None:
        assert disarm.inspect_anomalies(word).kinds == []

    @pytest.mark.parametrize(("word", "source"), SHAPE)
    def test_a_letter_the_fold_changes_in_shape_still_reports(self, word: str, source: str) -> None:
        """The fold is deliberate (``tests/integration_unmapped_confusables.rs``): the
        guide now says which Latin letters it reaches rather than the detector going
        quiet on them."""
        report = disarm.inspect_anomalies(word)
        assert report.kinds == ["confusable"]
        assert report.findings[0].detail.startswith(source)

    def test_the_folds_themselves_are_unchanged(self) -> None:
        """The detector changed, not the fold: ``canonicalize`` still folds all of them."""
        assert disarm.normalize_confusables("\u00e7") == "c"
        assert disarm.normalize_confusables("\u00c7") == "C"
        assert disarm.normalize_confusables("\u01fe") == "O"
        assert disarm.normalize_confusables("\u00f8") == "o"

    def test_no_letter_the_fold_reaches_is_an_accent_only_fold(self) -> None:
        """Anchored to the data rather than the examples: no Latin letter still reported
        decomposes to the letter it folds to plus marks."""
        for ch in _latin_letters_the_fold_reaches():
            detail = disarm.inspect_anomalies(f"ab{ch}cd").findings[0].detail
            target = detail.split(" folds to ", 1)[1]
            assert not unicodedata.normalize("NFD", ch).startswith(target), _cp(ch)

    def test_the_guide_states_the_count(self) -> None:
        """The guide says how many Latin letters the fold reaches. Measured here, so a
        table refresh that changes it fails until the sentence is corrected."""
        reached = _latin_letters_the_fold_reaches()
        undecomposed = [ch for ch in reached if unicodedata.normalize("NFD", ch) == ch]
        page = GUIDE.read_text(encoding="utf-8")
        match = re.search(r"reaches \*\*(\d+) Latin letters\*\*", page)
        assert match, "the confusable row no longer states which Latin letters the fold reaches"
        assert int(match.group(1)) == len(reached)
        match = re.search(r"(\d+) of them have no decomposition", page)
        assert match and int(match.group(1)) == len(undecomposed)
