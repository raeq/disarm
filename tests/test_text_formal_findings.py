"""Findings of the Lean model of the text primitives, in ``formal/lean/Text``.

Each class below is one finding of that model's README, reproduced on the library before it
was fixed (``formal/lean/Text/scripts/repro.py``):

* **Z1**: a class-0 combining mark between two runs of one mark reset the count, in
  ``is_zalgo``, ``strip_zalgo``, the key builders' repeat-dropper and the ``duplicate_mark``
  detector, so a base could carry any number of stacked marks.
* **Z2**: ``strip_zalgo`` kept one negation overlay beyond the cap (#749) and ``is_zalgo``
  counted it, so the cap's output was still zalgo at the same threshold.
* **Z3**: the docstrings capped marks "per base character"; the code caps them per combining
  class on one base.
* **W1**: a cluster opening with a zero-width ``Grapheme_Cluster_Break=Prepend`` measured 0.
* **W2**: a stray ``U+FE0F`` after a base that is not an emoji made it 2 columns.
* **C1**, **C2**: ``is_case_fold_stable`` and ``fold_case`` described against the host's
  ``str``, and the toolchain dependence called latent.
* **D1**-**D3**: ``strip_zero_width_chars``' "exactly" 10 code points, the Default_Ignorable
  code points ``canonicalize`` keeps, and ``fold_punctuation``'s incomplete classes.

Every assertion marked as a regression fails on the ``main`` these fixes were written
against. Escapes throughout, per #802: several of these characters render as nothing.
"""

from __future__ import annotations

import inspect
import itertools
import re
import unicodedata
from pathlib import Path

import pytest

import disarm

ROOT = Path(__file__).resolve().parent.parent
LIMITATIONS = ROOT / "docs" / "limitations.md"
PROVENANCE = ROOT / "docs" / "provenance.md"

ACUTE = "\u0301"
BELOW = "\u0316"
OVERLAY = "\u0334"

#: Class-0 combining marks used as separators: CGJ, the Mongolian free variation
#: selectors and the Khmer inherent vowels (all render as nothing, and ``canonicalize``
#: keeps the last six), a visible Thai vowel sign, and the Cyrillic millions sign.
SEPARATORS = [
    "\u034f",
    "\u180b",
    "\u180c",
    "\u180d",
    "\u180f",
    "\u17b4",
    "\u17b5",
    "\u0e31",
    "\u0489",
]


def _cp(ch: str) -> str:
    return "+".join(f"U+{ord(c):04X}" for c in ch)


def _count(text: str, mark: str) -> int:
    return unicodedata.normalize("NFD", text).count(mark)


def _marks(text: str) -> int:
    return sum(1 for c in unicodedata.normalize("NFD", text) if unicodedata.category(c)[0] == "M")


class TestZ1ClassZeroMarkDoesNotResetTheCount:
    @pytest.mark.parametrize("sep", SEPARATORS, ids=_cp)
    def test_a_split_stack_is_zalgo(self, sep: str) -> None:
        """Regression: ``False`` on ``main``, and ``strip_zalgo`` kept all six."""
        split = "a" + ACUTE * 3 + sep + ACUTE * 3
        assert unicodedata.combining(sep) == 0 and unicodedata.category(sep)[0] == "M"
        assert disarm.is_zalgo(split)
        stripped = disarm.strip_zalgo(split)
        assert _count(stripped, ACUTE) == 3
        assert sep in stripped, "the separator is a mark the cap keeps"

    @pytest.mark.parametrize("sep", SEPARATORS, ids=_cp)
    def test_any_number_of_runs_is_one_stack(self, sep: str) -> None:
        text = "a" + (ACUTE * 3 + sep) * 10
        assert disarm.is_zalgo(text)
        assert _count(disarm.strip_zalgo(text), ACUTE) == 3

    def test_every_class_zero_mark(self) -> None:
        """The sweep behind the finding: every class-0 mark the host knows, as a separator.

        On ``main`` 1,493 of the 1,496 at UCD 14.0 hid the stack.
        """
        missed = []
        for cp in range(0x110000):
            ch = chr(cp)
            if unicodedata.category(ch)[0] != "M" or unicodedata.combining(ch) != 0:
                continue
            split = "a" + ACUTE * 3 + ch + ACUTE * 3
            if not disarm.is_zalgo(split) or _count(disarm.strip_zalgo(split), ACUTE) != 3:
                missed.append(_cp(ch))
        assert not missed, missed

    def test_the_minimal_counterexample(self) -> None:
        """``z1_minimal`` in ``Findings.lean``: two acutes on one base at ``max_marks=1``."""
        text = "a" + ACUTE + "\u0e31" + ACUTE
        assert disarm.is_zalgo(text, threshold=1)
        assert disarm.strip_zalgo(text, max_marks=1) == "\u00e1\u0e31"

    def test_a_non_mark_still_starts_a_new_base(self) -> None:
        assert not disarm.is_zalgo("a" + ACUTE * 3 + "b" + ACUTE * 3)
        assert not disarm.is_zalgo("a" + ACUTE * 3 + "\u200b" + ACUTE * 3)

    @pytest.mark.parametrize("sep", ["\u180b", "\u1ce1", "\u20dd", "\U0001cf00", "\u0e31"], ids=_cp)
    def test_the_keys_reduce_the_stack_like_one_run(self, sep: str) -> None:
        """Regression: the README's measurement. ``canonicalize`` kept six acutes for every
        separator, ``canonicalize_strict`` for the ``Inherited`` ones and ``sort_key`` for all
        but ``U+180B``; ``a`` + eight acutes keys to one."""
        text = "a" + (ACUTE * 3 + sep) * 6
        fns = [disarm.canonicalize, disarm.canonicalize_strict, disarm.sort_key]
        if sep == "\u0e31":
            # `sort_key` transliterates the Thai vowel sign to a letter, which is a base of
            # its own, so there each acute sits on a different base: no stack to reduce.
            fns.remove(disarm.sort_key)
        for fn in fns:
            assert _count(fn(text), ACUTE) == _count(fn("a" + ACUTE * 8), ACUTE) == 1, fn.__name__

    def test_canonicalize_keeps_the_invisible_separator_but_not_the_stack(self) -> None:
        """Regression: ``canonicalize`` kept 20 acutes on one letter."""
        text = "a" + (ACUTE + "\u180b") * 20
        out = disarm.canonicalize(text)
        assert _count(out, ACUTE) == 1
        assert "\u180b" in out

    def test_a_repeat_across_a_class_zero_mark_is_dropped(self) -> None:
        """The #835 repeat-dropper, which reset at a class-0 mark too."""
        assert disarm.canonicalize("a" + ACUTE + "\u034f" + ACUTE) == "\u00e1"
        assert disarm.sort_key("a" + ACUTE + "\u180b" + ACUTE) == "\u00e1"
        # Two bases carrying one acute each is not a repeat.
        assert _count(disarm.canonicalize("a" + ACUTE + "b" + ACUTE), ACUTE) == 2

    def test_the_detector_reports_the_stack(self) -> None:
        """Regression: the token reported ``mixed_script`` alone."""
        report = disarm.inspect_anomalies("a" + (ACUTE + "\u180b") * 20)
        assert report.kinds[0] == "zalgo", report.kinds

    def test_the_detector_reports_the_repeat(self) -> None:
        """Regression: clean on ``main``."""
        report = disarm.inspect_anomalies("ba" + ACUTE + "\u034f" + ACUTE + "d")
        assert report.kinds == ["duplicate_mark"], report.kinds

    @pytest.mark.parametrize(
        "text",
        [
            "\u1019\u103c\u102d\u102f\u1037",  # Burmese, #842
            "\u0e01\u0e31\u0e49",  # Thai
            "\u0915\u094d\u0937\u094d\u0923",  # Devanagari
            "\u05d0\u05b8\u05c1\u0591",  # pointed and cantillated Hebrew, #788
            "Vi\u1ec7t Nam",
        ],
        ids=["burmese", "thai", "devanagari", "hebrew", "vietnamese"],
    )
    def test_ordinary_text_is_still_ordinary(self, text: str) -> None:
        assert not disarm.is_zalgo(text)
        assert _marks(disarm.strip_zalgo(text)) == _marks(text)


class TestZ2StripZalgoOutputIsNotZalgo:
    def test_the_negation_overlay_is_not_counted(self) -> None:
        """Regression: ``True`` on ``main``."""
        out = disarm.strip_zalgo("=" + "\u0338" * 4)
        assert _count(out, "\u0338") == 4, "one stroke kept beyond the cap, then three"
        assert not disarm.is_zalgo(out)

    def test_max_marks_zero_keeps_the_stroke_and_threshold_zero_agrees(self) -> None:
        """Regression: ``is_zalgo("\u2260", threshold=0)`` was ``True``."""
        assert disarm.strip_zalgo("\u2260", max_marks=0) == "\u2260"
        assert not disarm.is_zalgo("\u2260", threshold=0)

    def test_only_the_first_overlay_on_a_symbol_is_exempt(self) -> None:
        assert disarm.is_zalgo("=\u0338\u0338", threshold=0)
        assert disarm.is_zalgo("a\u0338", threshold=0), "strikethrough on a letter counts"
        assert disarm.strip_zalgo("a\u0338", max_marks=0) == "a"

    def test_the_pairing_holds_exhaustively(self) -> None:
        """Every word up to length 4 over the shapes that broke it, at thresholds 0 to 3:
        the cap's output is never zalgo, and the cap removes nothing from text that is not.
        """
        alphabet = ["a", "=", ACUTE, BELOW, OVERLAY, "\u0338", "\u20d2", "\u034f", "\u0e31"]
        for n in range(5):
            for word in itertools.product(alphabet, repeat=n):
                text = "".join(word)
                for k in range(4):
                    out = disarm.strip_zalgo(text, max_marks=k)
                    assert not disarm.is_zalgo(out, threshold=k), (ascii(text), k)
                    if not disarm.is_zalgo(text, threshold=k):
                        assert _marks(out) == _marks(text), (ascii(text), k)


class TestZ3PerClassNotPerBase:
    def test_a_base_carries_the_cap_of_each_class(self) -> None:
        text = "a" + ACUTE * 3 + BELOW * 3 + OVERLAY * 3
        assert not disarm.is_zalgo(text)
        assert _marks(disarm.strip_zalgo(text)) == 9

    @pytest.mark.parametrize("fn", [disarm.is_zalgo, disarm.strip_zalgo], ids=lambda f: f.__name__)
    def test_the_docstring_says_so(self, fn) -> None:
        """Regression: "per base character" and "consecutive" on ``main``."""
        doc = inspect.getdoc(fn) or ""
        assert "combining class" in doc
        assert "consecutive" not in doc
        assert "per base character" not in doc


class TestW1PrependDoesNotHideItsBase:
    #: The thirteen zero-width ``Prepend`` scalars.
    ZERO_WIDTH_PREPEND = [
        *map(chr, range(0x0600, 0x0606)),
        "\u06dd",
        "\u070f",
        "\u0890",
        "\u0891",
        "\u08e2",
        "\U000110bd",
        "\U000110cd",
    ]

    def test_the_readme_examples(self) -> None:
        """Regression: ``0 2 0 2`` on ``main``."""
        assert disarm.terminal_width("\u0600" + "1") == 1
        assert disarm.terminal_width("\u0600" + "123") == 3
        assert disarm.terminal_width(("\u0600" + "A") * 100) == 100
        assert disarm.terminal_width("\u0600 ok") == 3

    @pytest.mark.parametrize("prefix", ZERO_WIDTH_PREPEND, ids=_cp)
    def test_each_zero_width_prepend(self, prefix: str) -> None:
        assert disarm.grapheme_len(prefix + "7") == 1, "one cluster, by GB9b"
        assert disarm.terminal_width(prefix + "7") == 1
        assert disarm.grapheme_width(prefix + "\u4e00") == 2
        assert disarm.grapheme_width(prefix) == 0

    def test_every_prepend_cluster_takes_a_cell(self) -> None:
        """Every scalar the segmenter attaches to the letter after it, measured with one."""
        prepend = [
            chr(cp)
            for cp in range(0x110000)
            if not 0xD800 <= cp <= 0xDFFF and disarm.grapheme_len(chr(cp) + "a") == 1
        ]
        assert len(prepend) >= 27
        assert set(self.ZERO_WIDTH_PREPEND) <= set(prepend)
        assert all(disarm.terminal_width(p + "a") >= 1 for p in prepend)
        zero = [p for p in prepend if disarm.terminal_width(p) == 0]
        assert sorted(zero) == sorted(self.ZERO_WIDTH_PREPEND)

    def test_limitations_no_longer_says_the_separator_always_starts_a_cluster(self) -> None:
        text = LIMITATIONS.read_text(encoding="utf-8")
        assert "always starts a fresh cluster regardless" not in text
        assert disarm.grapheme_len("\u0600 ok") == 3


class TestW2StrayVs16:
    def test_a_stray_vs16_is_ignored_like_a_stray_vs15(self) -> None:
        """Regression: ``2 1 6`` on ``main``."""
        assert disarm.grapheme_width("a\ufe0f") == 1
        assert disarm.grapheme_width("a\ufe0e") == 1
        assert disarm.terminal_width("a\ufe0fb\ufe0fc\ufe0f") == 3
        assert disarm.grapheme_width("\u4e00\ufe0f") == 2, "a wide base keeps its own width"

    @pytest.mark.parametrize(
        "cluster",
        ["\u263a\ufe0f", "\u00a9\ufe0f", "1\ufe0f", "1\ufe0f\u20e3", "\u2764\ufe0f"],
        ids=_cp,
    )
    def test_an_emoji_base_still_takes_emoji_presentation(self, cluster: str) -> None:
        assert disarm.grapheme_width(cluster) == 2


class TestC1C2CaseFoldDocs:
    def test_is_case_fold_stable_does_not_claim_the_hosts_lower(self) -> None:
        """Regression: "Answers ``fold_case(text) == text.lower()``" on ``main``."""
        doc = inspect.getdoc(disarm.is_case_fold_stable) or ""
        assert "Answers ``fold_case(text) == text.lower()``" not in doc
        assert "neither is your Python's" in doc
        assert "U+A7CE" in doc

    def test_fold_case_names_the_unicode_version_of_its_equivalence(self) -> None:
        doc = inspect.getdoc(disarm.fold_case) or ""
        assert "Equivalent to ``str.casefold()`` on a Python whose ``unicodedata``" in doc

    def test_the_toolchain_dependence_is_not_called_latent(self) -> None:
        """Regression: "latent rather than live" in ``docs/provenance.md``."""
        text = PROVENANCE.read_text(encoding="utf-8")
        assert "latent rather than live" not in text
        assert "The divergence is live." in text

    def test_fold_case_is_the_bundled_table(self) -> None:
        """The table is pinned at Unicode 16.0: a Unicode 17 capital is left alone,
        whatever the host or the toolchain lowercases it to."""
        assert disarm.fold_case("\ua7ce") == "\ua7ce"
        assert disarm.fold_case("\u1c89") == "\u1c8a"


class TestD1ZeroWidthSet:
    def test_the_docstring_lists_exactly_the_set_removed(self) -> None:
        """Regression: the docstring said "exactly" 10 code points; 22 are removed."""
        doc = inspect.getdoc(disarm.strip_zero_width_chars) or ""
        listed: set[int] = set()
        for lo, hi in re.findall(r"^- ``U\+([0-9A-F]+)``(?:\u2013``U\+([0-9A-F]+)``)?", doc, re.M):
            listed.update(range(int(lo, 16), int(hi or lo, 16) + 1))
        removed = {
            cp
            for cp in range(0x110000)
            if not 0xD800 <= cp <= 0xDFFF
            and disarm.strip_zero_width_chars("a" + chr(cp) + "b") == "ab"
        }
        assert len(removed) == 22
        assert listed == removed


class TestD2DefaultIgnorablesCanonicalizeKeeps:
    KEPT = ["\u17b4", "\u17b5", "\u180b", "\u180c", "\u180d", "\u180f"]
    REMOVED_BY_813 = [*map(chr, range(0x1BCA0, 0x1BCA4)), *map(chr, range(0x1D173, 0x1D17B))]

    @pytest.mark.parametrize("ch", KEPT, ids=_cp)
    def test_the_six_are_kept(self, ch: str) -> None:
        assert ch in disarm.canonicalize("a" + ch + "b")

    @pytest.mark.parametrize("ch", REMOVED_BY_813, ids=_cp)
    def test_the_813_formats_are_removed(self, ch: str) -> None:
        """Regression (docs): ``limitations.md`` listed these as kept."""
        assert disarm.canonicalize("a" + ch + "b") == "ab"

    def test_the_page_says_six(self) -> None:
        text = LIMITATIONS.read_text(encoding="utf-8")
        assert "The 18 it keeps" not in text
        assert "The 6 it keeps" in text
        assert "It removes **399** of\nthe 405" in text


class TestD3FoldPunctuationClasses:
    @pytest.mark.parametrize(
        ("source", "folded"),
        [
            ("\u1680", " "),
            ("\u201b", "'"),
            ("\u201f", '"'),
            ("\u2035", "'"),
            ("\u2036", '"'),
            ("\u2034", "'''"),
            ("\u2037", "'''"),
        ],
        ids=lambda v: _cp(v) if v and not v.isascii() else repr(v),
    )
    def test_the_members_left_out(self, source: str, folded: str) -> None:
        """Regression: each was returned unchanged on ``main``."""
        assert disarm.fold_punctuation("a" + source + "b") == "a" + folded + "b"

    def test_every_space_separator(self) -> None:
        spaces = [
            chr(cp)
            for cp in range(0x110000)
            if unicodedata.category(chr(cp)) == "Zs" and chr(cp) != " "
        ]
        assert "\u1680" in spaces
        for ch in spaces:
            assert disarm.fold_punctuation(ch) == " ", _cp(ch)

    def test_every_prime(self) -> None:
        for cp in range(0x2032, 0x2038):
            out = disarm.fold_punctuation(chr(cp))
            assert out and set(out) <= {"'", '"'}, _cp(chr(cp))

    def test_idempotent_and_ascii(self) -> None:
        text = "".join(chr(cp) for cp in [0x1680, 0x201B, 0x201F, *range(0x2032, 0x2038)])
        once = disarm.fold_punctuation(text)
        assert once.isascii()
        assert disarm.fold_punctuation(once) == once
