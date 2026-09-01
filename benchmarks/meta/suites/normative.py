"""Suites anchored to a normative table somebody else publishes.

Unicode Consortium (UTS #39, UTS #46, UTS #51, UAX #9, UAX #29, the UCD), the
IETF (RFC 5892), ICANN (the Latin second-level LGR) and CLDR. These are the
strongest kind of external benchmark available here: the table *defines* the
right answer, so a disagreement is a finding rather than an opinion.

Every suite reads the table and reports a census. None of them edits a table,
and none carries a vector of its own.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from .. import damage
from ..base import DATA, FIXTURES, SuiteBase, add, artifact, record, thin
from ..fetch import Source
from ..protocol import Availability, Family, Outcome, Provenance
from ..subjects import Capability

_MAX_CP = sys.maxunicode + 1


def _apply(fn: Callable[[str], str], text: str) -> str:
    """Run one surface, treating a refusal as "left unchanged"."""
    try:
        return fn(text)
    except Exception:  # noqa: BLE001 - a surface may reject some input
        return text


def _changed(fn: Callable[[str], str], text: str) -> bool:
    return _apply(fn, text) != text


def _fires(fn: Callable[[str], bool], text: str) -> bool:
    """Run one detector; a refusal counts as "did not fire"."""
    try:
        return bool(fn(text))
    except Exception:  # noqa: BLE001 - a detector may reject some input
        return False


def _word_joiners() -> list[int]:
    """General categories Pd and Pc — every code point that renders as a
    within-word joiner, and the denominator the published census uses."""
    return [cp for cp in range(_MAX_CP) if unicodedata.category(chr(cp)) in ("Pd", "Pc")]


def _strong_rtl() -> list[int]:
    """Assigned code points with Bidi_Class R or AL, surrogates excluded.

    The exact domain ``bidi_class_sweep.py`` sweeps, so the reproduction and the
    wider measurement below cannot silently disagree about the denominator.
    """
    return [
        cp
        for cp in range(_MAX_CP)
        if not (0xD800 <= cp <= 0xDFFF)
        and unicodedata.category(chr(cp)) != "Cn"
        and unicodedata.bidirectional(chr(cp)) in ("R", "AL")
    ]


# --------------------------------------------------------------------------
# UTS #39


class UTS39ConfusableCoverage(SuiteBase):
    name = "uts39-confusables"
    family = Family.NORMATIVE
    availability = Availability.VENDORED
    MULTI_SUBJECT = True
    summary = "How much of UTS #39 confusables.txt does the shipped fold actually reach?"
    provenance = Provenance(
        origin="Unicode Consortium",
        citation="UTS #39 confusables.txt",
        url="https://www.unicode.org/Public/security/latest/confusables.txt",
        version="17.0.0 (vendored at data/confusables.txt)",
        licence="Unicode License v3",
        issues=(715, 791, 801, 831),
        finding=(
            "#791: whole equivalence classes are dropped when no member is in the "
            "target script, and 948 of the 1,007 strong-RTL sources were among them. "
            "#715: 16 upstream Cherokee sources were dropped, including the one "
            "CVE-2026-17084 emits from U+13A0."
        ),
        notes=(
            "The upstream source set, not disarm's bundled subset: a code point in "
            "the standard but unmapped counts as an addressable miss."
        ),
    )

    def locate(self) -> Path | None:
        return artifact(DATA / "confusables.txt", env="DISARM_META_CONFUSABLES")

    def measure(self, outcome: Outcome, limit: int | None) -> None:

        path = self.locate()
        assert path is not None
        pairs: dict[int, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            cols = [c.strip() for c in line.split(";")]
            if len(cols) < 2 or not cols[0] or not cols[1]:
                continue
            try:
                source = int(cols[0], 16)
                target = "".join(chr(int(h, 16)) for h in cols[1].split())
            except ValueError:
                continue
            pairs[source] = target
        ordered = thin(sorted(pairs), limit)
        outcome.population = len(ordered)

        surface_map = self.transforms()
        record(
            outcome,
            domain=f"{len(ordered)} UTS #39 source->target pairs",
            predicates=sorted(surface_map),
            reached_if=(
                "some surface maps the source and its UTS #39 target to one "
                "NON-EMPTY form; deleting both sides is not coverage"
            ),
            changed_if="some surface merely alters the source",
            note=(
                "'changed' is not a fair cross-tool score: a transliterator "
                "rewrites nearly every non-ASCII code point and would read as "
                "near-total coverage while landing nowhere near the target."
            ),
        )
        folded = unchanged = 0
        rtl_unreached = 0
        altered_only = 0
        for cp in ordered:
            ch, target = chr(cp), pairs[cp]
            # damage.collides requires a non-empty shared form, which is what
            # stops a delete-everything tool scoring 100% here.
            if damage.collides(surface_map.values(), ch, target):
                folded += 1
            else:
                unchanged += 1
                if any(_changed(fn, ch) for fn in surface_map.values()):
                    altered_only += 1
                if unicodedata.bidirectional(ch) in ("R", "AL"):
                    rtl_unreached += 1
        n = len(ordered)
        add(outcome, "sources", n, unit="pairs")
        add(
            outcome,
            "folded",
            folded,
            of=n,
            higher_is_better=True,
            detail="source and its UTS #39 target land on one form",
        )
        add(
            outcome,
            "unreached",
            unchanged,
            of=n,
            higher_is_better=False,
            detail="source and target still differ — addressable, route via #40",
        )
        add(
            outcome,
            "altered_but_not_onto_target",
            altered_only,
            of=unchanged,
            higher_is_better=False,
            detail="rewritten, and still not equal to the target: motion without coverage",
        )
        add(
            outcome,
            "unreached_strong_rtl",
            rtl_unreached,
            of=unchanged,
            detail="Bidi_Class R/AL among the unreached (#791, #792)",
        )


class UTS39MixedNumbers(SuiteBase):
    name = "uts39-mixed-numbers"
    family = Family.NORMATIVE
    availability = Availability.DERIVED
    summary = "UTS #39 §5.3: are digits from two numbering systems reported as mixed?"
    provenance = Provenance(
        origin="Unicode Consortium",
        citation="UTS #39 §5.3 Mixed Numbers",
        url="https://www.unicode.org/reports/tr39/#Mixed_Numbers",
        version="derived from the running interpreter's UCD",
        licence="Unicode License v3",
        issues=(777,),
        reproduces=(
            "mixed_number_probe.py — the seven labelled cases, scored on whether "
            "any surface reports a multi-system identifier."
        ),
        finding=(
            "#777: unimplemented at 0.14.1 — `1٢۳４५` reported clean, and ASCII mixed "
            "with any of the other 75 numbering systems was one script to "
            "is_mixed_script."
        ),
        notes="Numbering systems are grouped by the decimal-zero of each Nd run.",
    )

    #: The published probe's own cases: (text, carries a mix).
    CASES = (
        ("2024", False),
        ("٢٠٢٤", False),
        ("२०२४", False),
        ("1٢", True),
        ("٢५", True),
        ("1٢۳４५", True),
        ("acct-1٢3", True),
    )

    #: From executing mixed_number_probe.py on a v0.14.1 build. Counting
    #: is_mixed_script as a hit would give 3 and mean nothing: Arabic-Indic plus
    #: Devanagari is a genuine script mix, so that surface fires for an unrelated
    #: reason. The claim under test is that no surface names the numbers rule.
    REPRO_EXPECTED = {
        "cases": 7,
        "mixed_numbers_kind_reported": 0,
        "pure_digit_mixes_flagged": 0,
    }

    def reproduce(self) -> dict[str, float]:
        import disarm

        named = flagged = 0
        for text, mixed in self.CASES:
            if not mixed:
                continue
            if any("number" in kind for kind in disarm.inspect_anomalies(text).kinds):
                named += 1
            # The three all-digit mixes; "acct-1٢3" is excluded because it
            # carries Latin letters and so has a script signal of its own.
            if text.isdigit() and disarm.has_anomalies(text):
                flagged += 1
        return {
            "cases": len(self.CASES),
            "mixed_numbers_kind_reported": named,
            "pure_digit_mixes_flagged": flagged,
        }

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        import disarm

        # Group Nd code points into numbering systems: a system is a run of ten
        # starting at a code point whose numeric value is 0.
        zeros = [
            cp
            for cp in range(_MAX_CP)
            if unicodedata.category(chr(cp)) == "Nd" and unicodedata.decimal(chr(cp), -1) == 0
        ]
        ascii_zero = 0x30
        others = [z for z in zeros if z != ascii_zero]
        others = thin(others, limit)
        outcome.population = len(others)

        flagged_pairwise = 0
        flagged_with_ascii = 0
        for z in others:
            foreign = "".join(chr(z + d) for d in range(3))
            mixed_with_ascii = "1" + foreign
            if disarm.is_mixed_script(mixed_with_ascii) or disarm.has_anomalies(mixed_with_ascii):
                flagged_with_ascii += 1
            other = next((o for o in others if o != z), None)
            if other is not None:
                pair = foreign + "".join(chr(other + d) for d in range(3))
                if disarm.is_mixed_script(pair) or disarm.has_anomalies(pair):
                    flagged_pairwise += 1
        add(outcome, "numbering_systems", len(others), unit="systems")
        add(
            outcome,
            "ascii_mixed_flagged",
            flagged_with_ascii,
            of=len(others),
            higher_is_better=True,
            detail="ASCII digit + one other system reported",
        )
        add(
            outcome,
            "pairwise_mixed_flagged",
            flagged_pairwise,
            of=len(others),
            higher_is_better=True,
            detail="two non-ASCII systems reported",
        )


class UTS39AugmentedScripts(SuiteBase):
    name = "uts39-augmented-scripts"
    family = Family.NORMATIVE
    availability = Availability.DERIVED
    summary = "UTS #39 §5.1 augmented script sets: do the three mixed-script surfaces agree?"
    provenance = Provenance(
        origin="Unicode Consortium",
        citation="UTS #39 §5.1 Restriction-Level Detection",
        url="https://www.unicode.org/reports/tr39/#Restriction_Level_Detection",
        version="derived",
        licence="Unicode License v3",
        issues=(776,),
        reproduces=(
            "augmented_script_probe.py — six labelled cases, scored on the "
            "three-way disagreement between inspect_anomalies, is_mixed_script "
            "and HostnameAnalysis.mixed_script."
        ),
        finding=(
            "#776: applied in inspect_anomalies only — `例え` was clean to the "
            "detector, mixed-script to is_mixed_script, and suspicious as a hostname."
        ),
        notes=(
            "Augmented sets fold Hani into Hanb/Jpan/Kore and Hira/Kana into Jpan; "
            "the benchmark is surface agreement, and the table decides who is right."
        ),
    )

    #: The published probe's own cases, verbatim: (label, text, hostname). Five
    #: single augmented scripts and one genuine Cyrillic/Latin spoof as a
    #: positive control. These are not chosen here — inventing the probe strings
    #: would make this suite's verdict disarm's opinion rather than UTS #39's.
    CASES = (
        ("Japanese Han+Hiragana", "例え", "例え.テスト", False),
        ("Japanese Han+Katakana", "例テ", "例テ.com", False),
        ("Japanese Hira+Katakana", "ひらカタ", "ひらカタ.jp", False),
        ("Korean Hangul only", "실례", "실례.테스트", False),
        ("Chinese Han only", "例子", "例子.测试", False),
        ("SPOOF Cyrillic+Latin", "аpple", "аpple.com", True),
    )

    #: From executing augmented_script_probe.py on a v0.14.1 build: the three
    #: Japanese rows disagree, Korean/Chinese/spoof agree.
    REPRO_EXPECTED = {"cases": 6, "three_way_disagreements": 3}

    def reproduce(self) -> dict[str, float]:
        # augmented_script_probe.py. The gist reads HostnameAnalysis.mixed_script,
        # not is_suspicious_hostname()[0]; the latter is an overall verdict that
        # folds in several other rules, so it answers a different question.
        import disarm

        disagreements = 0
        for _label, text, host, _spoof in self.CASES:
            anomalous = "mixed_script" in disarm.inspect_anomalies(text).kinds
            mixed = disarm.is_mixed_script(text)
            _, analysis = disarm.is_suspicious_hostname(host)
            if anomalous != mixed or mixed != analysis.mixed_script:
                disagreements += 1
        return {"cases": len(self.CASES), "three_way_disagreements": disagreements}

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        import disarm

        cases = list(self.CASES)[: limit or None]
        outcome.population = len(cases)
        disagreements = wrong = 0
        by_surface: Counter[str] = Counter()
        for _label, text, host, spoof in cases:
            _, analysis = disarm.is_suspicious_hostname(host)
            verdicts = {
                "is_mixed_script": disarm.is_mixed_script(text),
                "inspect_anomalies": "mixed_script" in disarm.inspect_anomalies(text).kinds,
                "hostname_mixed_script": analysis.mixed_script,
            }
            for surface, flagged in verdicts.items():
                if flagged:
                    by_surface[surface] += 1
            if len(set(verdicts.values())) > 1:
                disagreements += 1
            # UTS #39 §5.1 fixes the right answer per case: a single augmented
            # script is not mixed, and the Cyrillic/Latin spoof is.
            if any(v is not spoof for v in verdicts.values()):
                wrong += 1
        add(outcome, "cases", len(cases), unit="strings")
        add(
            outcome,
            "surface_disagreements",
            disagreements,
            of=len(cases),
            higher_is_better=False,
            detail="the three surfaces do not return one verdict",
        )
        add(
            outcome,
            "disagrees_with_uts39",
            wrong,
            of=len(cases),
            higher_is_better=False,
            detail="at least one surface contradicts the augmented-set answer",
        )
        for surface in ("is_mixed_script", "inspect_anomalies", "hostname_mixed_script"):
            add(
                outcome,
                f"flagged_by_{surface}",
                by_surface[surface],
                of=len(cases),
                detail="only the Cyrillic/Latin spoof should be flagged",
            )


# --------------------------------------------------------------------------
# UCD


class UCDScriptTable(SuiteBase):
    name = "ucd-scripts"
    family = Family.NORMATIVE
    availability = Availability.VENDORED
    summary = "disarm's block-range script table against UCD Scripts.txt."
    provenance = Provenance(
        origin="Unicode Consortium",
        citation="UCD Scripts.txt",
        url="https://www.unicode.org/Public/UCD/latest/ucd/Scripts.txt",
        version="17.0.0 (vendored at tests/fixtures/ucd_script_ranges.tsv)",
        licence="Unicode License v3",
        issues=(774, 775, 819),
        finding=(
            "#819: the block table contradicted the UCD for 35 code points and "
            "declined 11,875 more. #774: 1,226 unassigned code points inherited a "
            "neighbouring block's script. #775: four core scripts were missing from "
            "the Script enum (160 code points)."
        ),
        notes="The fixture is restricted to the scripts src/scripts.rs curates.",
    )

    def locate(self) -> Path | None:
        return artifact(FIXTURES / "ucd_script_ranges.tsv", env="DISARM_META_UCD_SCRIPTS")

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        import disarm

        path = self.locate()
        assert path is not None
        expected: dict[int, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            start, end, script = int(parts[0], 16), int(parts[1], 16), parts[2]
            for cp in range(start, end + 1):
                expected[cp] = script
        keys = thin(sorted(expected), limit)
        items = [(cp, expected[cp]) for cp in keys]
        outcome.population = len(items)

        agree = contradict = silent = 0
        contradictions: Counter[str] = Counter()
        # The fixture covers ranges, and a range can contain unassigned code
        # points. Those are skipped, so `scored` — not the fixture size — is the
        # denominator; using the fixture size would leave the three outcomes
        # failing to sum to it.
        scored = 0
        for cp, script in items:
            ch = chr(cp)
            if unicodedata.category(ch) == "Cn":
                continue
            scored += 1
            got = [s.name.lower() for s in disarm.detect_scripts(ch)]
            if not got:
                silent += 1
            elif script.lower() in got:
                agree += 1
            else:
                contradict += 1
                contradictions[f"{script}->{','.join(got)}"] += 1
        add(
            outcome,
            "codepoints",
            len(items),
            unit="codepoints",
            detail="rows in the fixture, including unassigned",
        )
        add(
            outcome,
            "scored",
            scored,
            of=len(items),
            detail="assigned, and therefore actually compared",
        )
        add(outcome, "agree", agree, of=scored, higher_is_better=True)
        add(
            outcome,
            "contradict",
            contradict,
            of=scored,
            higher_is_better=False,
            detail="detect_scripts names a script the UCD does not",
        )
        add(
            outcome,
            "silent",
            silent,
            of=scored,
            higher_is_better=False,
            detail="detect_scripts returns nothing for an assigned code point",
        )
        outcome.extra = {"top_contradictions": contradictions.most_common(10)}


class UCDBidiClass(SuiteBase):
    name = "ucd-bidi-class"
    family = Family.NORMATIVE
    availability = Availability.DERIVED
    summary = "UAX #9 Bidi_Class R/AL coverage of has_bidi_conflict."
    provenance = Provenance(
        origin="Unicode Consortium",
        citation="UAX #9 / DerivedBidiClass.txt",
        url="https://www.unicode.org/reports/tr9/",
        version="derived from the running interpreter's UCD",
        licence="Unicode License v3",
        issues=(773, 741),
        reproduces=(
            "bidi_class_sweep.py — assigned Bidi_Class R/AL code points, and how "
            "many of them detect_scripts() resolves to no script at all."
        ),
        finding=(
            "#773: direction was resolved from a five-name script list, so 1,786 of "
            "3,018 assigned R/AL code points were neutral to has_bidi_conflict, "
            "including two entire Arabic blocks."
        ),
        notes=(
            "unicodedata.bidirectional is the authority; disarm resolves direction "
            "from a five-name script list, which is the thing under test."
        ),
    )

    REPRO_EXPECTED = {"assigned_r_al": 3018, "unscripted": 1786}

    def reproduce(self) -> dict[str, float]:
        # bidi_class_sweep.py: the finding is about direction *resolution*, so the
        # quantity is detect_scripts() == [] — not has_bidi_conflict, which is one
        # consumer of it. Measuring the consumer answers a different question.
        import disarm

        rtl = _strong_rtl()
        unscripted = [cp for cp in rtl if not disarm.detect_scripts(chr(cp))]
        return {"assigned_r_al": len(rtl), "unscripted": len(unscripted)}

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        import disarm

        rtl = _strong_rtl()
        rtl = thin(rtl, limit)
        outcome.population = len(rtl)

        seen = 0
        for cp in rtl:
            if disarm.has_bidi_conflict("hello" + chr(cp)):
                seen += 1
        add(outcome, "strong_rtl", len(rtl), unit="codepoints")
        add(
            outcome,
            "conflict_detected",
            seen,
            of=len(rtl),
            higher_is_better=True,
            detail="Latin + one strong-RTL code point reported as a conflict",
        )
        add(outcome, "neutral_to_disarm", len(rtl) - seen, of=len(rtl), higher_is_better=False)


class UAX29WordJoiners(SuiteBase):
    name = "uax29-word-joiners"
    family = Family.NORMATIVE
    availability = Availability.DERIVED
    # "Is a fragmented word detected, and is it rejoined" is a tool-neutral
    # question, so this became multi-subject as soon as a second detector
    # existed. The pinned reproduction still runs for disarm only.
    MULTI_SUBJECT = True
    # Two separable questions, so a tool with either capability can answer its
    # half. `confusable-homoglyphs` detects and does not transform; excluding it
    # would leave the detection question with one participant again.
    REQUIRES_ANY = (Capability.TRANSFORM, Capability.DETECT)
    summary = "Visible within-word joiners (Pd + Pc): is a fragmented word detected?"
    provenance = Provenance(
        origin="Unicode Consortium",
        citation="UAX #29 / General_Category Pd, Pc",
        url="https://www.unicode.org/reports/tr29/",
        version="derived",
        licence="Unicode License v3",
        issues=(750, 752, 755, 804),
        reproduces=(
            "segmentation-separator-census.py — the fully atomized lexicon word "
            "c<SEP>o<SEP>n...m for 'confirm', scored on the `segmentation` anomaly "
            "kind directly and after canonicalize."
        ),
        finding=(
            "#750: the segmentation branch recognised three separators, so 16 of the "
            "36 within-word joiners were silent on both paths and U+2010 disagreed "
            "with U+002D."
        ),
        notes="The invisible-carrier twin of this class has a full out-of-scope entry.",
    )

    #: From executing segmentation-separator-census.py on a v0.14.1 build, not
    #: from its docstring — that header says "Pd=26 Pc=10 total=36 (Unicode 16.0
    #: tables)" and the script prints Pd=27 Pc=10 total=37 under UCD 16.0.0. The
    #: header is a transcribed claim; the run is the derived one.
    REPRO_UCD = "16.0.0"
    REPRO_EXPECTED = {
        "joiners": 37,
        "segmentation_direct": 2,
        "segmentation_after_canonicalize": 16,
        "other_kind_never_segmentation": 4,
        "silent_both_paths": 17,
    }

    def reproduce(self) -> dict[str, float]:
        # segmentation-separator-census.py. Three things the gist does that the
        # sweep below does not: it atomizes the whole word, it passes a lexicon
        # (the `segmentation` branch is lexicon-gated), and it scores that one
        # anomaly kind rather than has_anomalies. Drop any of the three and the
        # number stops being the one #750 reports.
        import disarm

        word, lex = "confirm", {"confirm"}
        joiners = _word_joiners()
        direct = after = other = silent = 0
        for cp in joiners:
            token = chr(cp).join(word)
            kinds = disarm.inspect_anomalies(token, lex).kinds
            d = "segmentation" in kinds
            a = "segmentation" in disarm.inspect_anomalies(disarm.canonicalize(token), lex).kinds
            direct += d
            after += a
            # The census's buckets: "other" reports something that is never
            # segmentation on either path; "silent" reports nothing at all
            # directly and nothing after canonicalize. They are not complements.
            if kinds and not d and not a:
                other += 1
            if not kinds and not a:
                silent += 1
        return {
            "joiners": len(joiners),
            "segmentation_direct": direct,
            "segmentation_after_canonicalize": after,
            "other_kind_never_segmentation": other,
            "silent_both_paths": silent,
        }

    def measure(self, outcome: Outcome, limit: int | None) -> None:

        joiners = thin(_word_joiners(), limit)
        outcome.population = len(joiners)
        det = self.detect()
        surface_map = self.transforms()
        record(
            outcome,
            domain=f"{len(joiners)} Pd/Pc within-word joiners",
            predicates=[*sorted(surface_map), *sorted(det)],
            probe="pass<SEP>word, scored against 'password'",
        )

        detected = recovered = 0
        for cp in joiners:
            fragmented = f"pass{chr(cp)}word"
            if any(_fires(fn, fragmented) for fn in det.values()):
                detected += 1
            if any(_apply(fn, fragmented) == "password" for fn in surface_map.values()):
                recovered += 1
        add(outcome, "joiners", len(joiners), unit="codepoints")
        # Only report a half the subject can actually answer. A detector-only
        # tool scoring 0 for "recovered" would read as a failure rather than as
        # a question it was never asked.
        if det:
            add(
                outcome,
                "detected",
                detected,
                of=len(joiners),
                higher_is_better=True,
                detail="some detector of the subject flags the fragmented word",
            )
        if surface_map:
            add(
                outcome,
                "recovered",
                recovered,
                of=len(joiners),
                higher_is_better=True,
                detail="some surface of the subject rejoins it",
            )


class DefaultIgnorableCasefold(SuiteBase):
    name = "ucd-toNFKC-casefold"
    family = Family.NORMATIVE
    availability = Availability.NETWORK
    env_var = "DISARM_META_DERIVEDCORE"
    SOURCES = (
        Source(
            url="https://www.unicode.org/Public/UCD/latest/ucd/DerivedCoreProperties.txt",
            filename="DerivedCoreProperties.txt",
            licence="Unicode License v3",
            note="tracks `latest` deliberately — the drift is the point",
        ),
    )
    summary = "Do the primitives compose to toNFKC_Casefold? (Default_Ignorable survival)"
    provenance = Provenance(
        origin="Unicode Consortium",
        citation="UCD DerivedCoreProperties.txt (Default_Ignorable_Code_Point)",
        url="https://www.unicode.org/Public/UCD/latest/ucd/DerivedCoreProperties.txt",
        version="latest",
        licence="Unicode License v3",
        issues=(770,),
        finding=(
            "#770: all 405 assigned Default_Ignorable code points survived "
            "fold_case(normalize(s, form='NFKC')), so the primitives do not compose "
            "to toNFKC_Casefold."
        ),
        notes="unicodedata does not expose Default_Ignorable, so the table is fetched.",
    )

    def locate(self) -> Path | None:
        from ..base import CACHE

        return artifact(CACHE / "DerivedCoreProperties.txt", env=self.env_var)

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        import disarm

        path = self.locate()
        assert path is not None
        ignorable: list[int] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            head = line.split("#", 1)[0].strip()
            if not head or "Default_Ignorable_Code_Point" not in head:
                continue
            rng = head.split(";", 1)[0].strip()
            lo, _, hi = rng.partition("..")
            start = int(lo, 16)
            end = int(hi, 16) if hi else start
            ignorable.extend(range(start, end + 1))
        ignorable = thin([cp for cp in ignorable if unicodedata.category(chr(cp)) != "Cn"], limit)
        outcome.population = len(ignorable)

        survived = 0
        for cp in ignorable:
            ch = chr(cp)
            if ch in disarm.fold_case(disarm.normalize(ch, form="NFKC")):
                survived += 1
        add(outcome, "default_ignorable", len(ignorable), unit="codepoints")
        add(
            outcome,
            "survives_fold_of_nfkc",
            survived,
            of=len(ignorable),
            higher_is_better=False,
            detail="toNFKC_Casefold removes these; the composition does not",
        )


def _icann_blocked_homoglyphs(html_text: str) -> list[tuple[int, int]]:
    """Pairs ICANN blocks as visually identical, from its Variant Set tables.

    The repertoire table only names a set ("set 12"); the pairs live in a second
    table per set, so this is a join and not a single scan. Columns vary between
    sets (some carry Required Context), so Source and Target are taken from the
    two leading hex cells and the type and comment are matched by content.

    Admission is the same rule ``data/confusables_lgr.tsv`` documents: the mapping
    type is ``blocked`` **and** the Latin Generation Panel's own comment calls the
    glyphs homoglyphs or nearly identical. The 23 pairs commented "Required for
    use with Common LGR" are transitivity artefacts of running this LGR beside
    the Greek and Cyrillic ones, and folding them would strip legitimate
    diacritics.
    """
    import html as _html

    hex_cell = re.compile(r"^[0-9A-Fa-f]{4,6}$")
    out: list[tuple[int, int]] = []
    for block in re.findall(r"<tr[^>]*>(.*?)</tr>", html_text, re.S):
        cells = [
            " ".join(_html.unescape(re.sub(r"<[^>]+>", " ", c)).split())
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", block, re.S)
        ]
        if len(cells) < 4:
            continue
        codes = [c for c in cells if hex_cell.match(c)]
        if len(codes) < 2:
            continue
        lowered = [c.lower() for c in cells]
        if "blocked" not in lowered:
            continue
        comment = " ".join(lowered)
        if "homoglyph" not in comment and "nearly identical" not in comment:
            continue
        source, target = int(codes[0], 16), int(codes[1], 16)
        if source != target:
            out.append((source, target))
    return out


class ICANNLatinLGR(SuiteBase):
    name = "icann-lgr-latin"
    family = Family.NORMATIVE
    availability = Availability.NETWORK
    #: #831 counts 23 qualifying pairs; the parser recovers 21. The two it misses
    #: are not yet identified — most likely continuation rows, where a set table
    #: splits one mapping across two `<tr>`s with a bare arrow cell. Left visible
    #: rather than tuned away: a denominator that quietly disagrees with the issue
    #: it cites is the exact failure this harness exists to catch.
    EXPECTED_PAIRS = 23
    env_var = "DISARM_META_ICANN_LGR"
    SOURCES = (
        Source(
            url="https://www.icann.org/sites/default/files/packages/lgr/"
            "lgr-second-level-latin-script-25oct24-en.html",
            filename="lgr-second-level-latin.html",
            licence="ICANN publication terms",
            note="the published LGR itself, never data/confusables_lgr.tsv — the "
            "shipped fold was built from that file",
        ),
    )
    summary = "ICANN's Latin second-level LGR variant pairs vs disarm's key forms."
    provenance = Provenance(
        origin="ICANN",
        citation="Reference LGR for the Second Level, Latin script",
        url="https://www.icann.org/sites/default/files/packages/lgr/lgr-second-level-latin-script-25oct24-en.html",
        version="25 Oct 2024",
        licence="ICANN publication terms",
        issues=(831,),
        finding=(
            "#831: ICANN blocks 23 same-script Latin homoglyph pairs as visually "
            "identical; canonicalize collided 2 of them. Those pairs were then "
            "shipped as data/confusables_lgr.tsv, so a high collision rate here "
            "now is the fix having landed, not a coincidence."
        ),
        notes=(
            "Same-script Latin homoglyph pairs ICANN blocks as visually identical; "
            "TR39 does not list most of these code points as sources at all. The "
            "oracle must be ICANN's published LGR — data/confusables_lgr.tsv is "
            "disarm's extract of it and the shipped fold was built from that file, "
            "so it cannot also be the thing the fold is measured against."
        ),
    )

    def locate(self) -> Path | None:
        from ..base import CACHE

        # data/confusables_lgr.tsv is deliberately NOT a fallback. It is disarm's
        # own admission-filtered extract, and the fold was built from it, so
        # scoring the fold against it reports 100% by construction. A gate must
        # not be anchored to the thing it is gating; the oracle here is ICANN's
        # published LGR or nothing.
        return artifact(CACHE / "lgr-second-level-latin.html", env=self.env_var)

    def measure(self, outcome: Outcome, limit: int | None) -> None:

        import disarm

        path = self.locate()
        assert path is not None
        text = path.read_text(encoding="utf-8", errors="replace")
        pairs: list[tuple[int, int]] = []
        if path.suffix == ".tsv":
            # Vendored extract: hex source, literal target, weight, comment.
            for line in text.splitlines():
                if not line.strip() or line.startswith("#"):
                    continue
                cols = line.split("\t")
                if len(cols) < 2 or len(cols[1]) != 1:
                    continue
                try:
                    pairs.append((int(cols[0], 16), ord(cols[1])))
                except ValueError:
                    continue
        else:
            pairs = _icann_blocked_homoglyphs(text)
        if limit is not None:
            pairs = pairs[:limit]
        outcome.population = len(pairs)

        collide = 0
        for a, b in pairs:
            if disarm.catalog_key(chr(a)) == disarm.catalog_key(chr(b)):
                collide += 1
        add(outcome, "blocked_pairs", len(pairs), unit="pairs")
        add(
            outcome,
            "pairs_recovered_vs_issue",
            len(pairs),
            of=self.EXPECTED_PAIRS,
            higher_is_better=True,
            detail="#831 counts 23; a shortfall is a parser gap, not a result",
        )
        add(
            outcome,
            "collide_in_catalog_key",
            collide,
            of=len(pairs),
            higher_is_better=True,
            detail="ICANN calls them one label; disarm keys them the same",
        )


class CLDRNonEmojiNames(SuiteBase):
    name = "cldr-emoji-annotations"
    family = Family.NORMATIVE
    availability = Availability.VENDORED
    summary = "CLDR names applied to code points that are not Emoji (UTS #51)."
    provenance = Provenance(
        origin="Unicode CLDR",
        citation="CLDR annotations (en.xml, en_derived.xml) vs UTS #51 Emoji property",
        url="https://github.com/unicode-org/cldr/tree/main/common/annotations",
        version="vendored at data/cldr/",
        licence="Unicode License v3",
        issues=(757, 749),
        finding=(
            "#757: 371 non-emoji code points were named as English words, so "
            "`film’s` became `film right apostrophe s`; #614's precedence fix had "
            "reached only the security presets."
        ),
        notes=(
            "The annotation table does two unrelated jobs on one set of code points: "
            "it inserts spurious tokens (#757) and it is the only thing preserving "
            "the negation in U+2260 (#749). Narrowing one without fixing the other "
            "makes the negation inversion worse."
        ),
    )

    def locate(self) -> Path | None:
        return artifact(DATA / "cldr" / "en.xml", env="DISARM_META_CLDR")

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        import re

        import disarm

        path = self.locate()
        assert path is not None
        xml = path.read_text(encoding="utf-8", errors="replace")
        cps = {
            ord(m)
            for m in re.findall(r'<annotation cp="([^"]+)"[^>]*type="tts"', xml)
            if len(m) == 1
        }
        ordered = thin(sorted(cps), limit)
        outcome.population = len(ordered)

        glossed = 0
        for cp in ordered:
            ch = chr(cp)
            if disarm.ml_normalize(ch).strip() not in ("", ch):
                glossed += 1
        add(outcome, "annotated_codepoints", len(ordered), unit="codepoints")
        add(
            outcome,
            "glossed_by_ml_normalize",
            glossed,
            of=len(ordered),
            detail="a CLDR name reaches ml_normalize output as English words",
        )


class UTS39EquivalenceClasses(SuiteBase):
    name = "uts39-equivalence-classes"
    family = Family.NORMATIVE
    availability = Availability.VENDORED
    MULTI_SUBJECT = True
    summary = "Class closure: does every member of a UTS #39 class key the same?"
    provenance = Provenance(
        origin="Unicode Consortium",
        citation="UTS #39 confusables.txt equivalence classes",
        url="https://www.unicode.org/Public/security/latest/confusables.txt",
        version="17.0.0 (vendored at data/confusables.txt)",
        licence="Unicode License v3",
        issues=(848, 791, 836, 833),
        finding=(
            "#848: the generator is cross-script in both directions, so a class "
            "whose members are all in the target script is discarded by "
            "construction — TR39 puts keheh and kaf in one class with KAF as "
            "prototype, and canonicalize does not collide them, along with 548 "
            "other Arabic letter pairs. #791: 948 of 1,007 strong-RTL sources sit "
            "in classes with no target-script member."
        ),
        notes=(
            "The class, not the row, is the unit UTS #39 defines. A row-wise "
            "coverage number can be high while whole classes collapse to nothing, "
            "which is why this is scored separately from uts39-confusables."
        ),
    )

    def locate(self) -> Path | None:
        return artifact(DATA / "confusables.txt", env="DISARM_META_CONFUSABLES")

    def measure(self, outcome: Outcome, limit: int | None) -> None:

        path = self.locate()
        assert path is not None
        classes: dict[str, list[str]] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(";")]
            if len(parts) < 2 or not parts[0] or not parts[1]:
                continue
            try:
                source = chr(int(parts[0], 16))
                target = "".join(chr(int(h, 16)) for h in parts[1].split())
            except ValueError:
                continue
            classes.setdefault(target, []).append(source)

        ordered = sorted(classes)
        keys = [ordered[i] for i in thin(list(range(len(ordered))), limit)]
        outcome.population = len(keys)

        # The strongest surface the subject has, chosen per class: a tool is
        # credited with closing a class if any one of its surfaces does.
        surface_map = self.transforms()
        record(
            outcome,
            domain=f"{len(keys)} UTS #39 equivalence classes",
            predicates=sorted(surface_map),
            closed_if="one surface maps every member and the prototype to one form",
        )
        closed = 0
        intra_script_only = 0
        for target in keys:
            members = classes[target]
            everything = [*members, target]
            # One non-empty shared form. Collapsing the class to "" is deletion,
            # not closure, and scored the null baseline at 100% before this.
            if any(
                len(forms := {_apply(fn, m) for m in everything}) == 1 and next(iter(forms)) != ""
                for fn in surface_map.values()
            ):
                closed += 1
            if not any(_apply(fn, m).isascii() for fn in surface_map.values() for m in everything):
                intra_script_only += 1
        n = len(keys)
        add(outcome, "classes", n, unit="classes")
        add(
            outcome,
            "closed_under_canonicalize",
            closed,
            of=n,
            higher_is_better=True,
            detail="every member and the prototype land on one form",
        )
        add(
            outcome,
            "no_ascii_reachable_member",
            intra_script_only,
            of=n,
            higher_is_better=False,
            detail="no member can act as a fold target — discarded by construction",
        )


class CorruptionCost(SuiteBase):
    name = "corruption-cost"
    family = Family.NORMATIVE
    availability = Availability.DERIVED
    MULTI_SUBJECT = True
    summary = "The other direction: what the tool costs on text that needed nothing."
    provenance = Provenance(
        origin="Unicode Consortium",
        citation="UCD assigned code points (General_Category != Cn)",
        url="https://www.unicode.org/Public/UCD/latest/ucd/UnicodeData.txt",
        version="derived from the running interpreter's UCD",
        licence="Unicode License v3",
        issues=(759, 842, 754, 761, 745),
        finding=(
            "#759: benchmarks/adversarial_eval measures only recovery and is "
            "hardcoded to one entry point, so there is no clean-text cost metric "
            "behind 'what each entry point costs you'. #745: every preset "
            "collapsed 465/465 source files to one line — a cost no coverage "
            "number could show."
        ),
        notes=(
            "Every coverage metric in this registry has a degenerate solution: a "
            "tool that deletes all input folds every confusable onto its target "
            "and closes every equivalence class. This suite is the paired cost, "
            "and `null-baseline` is kept in the subject roster to prove it fires. "
            "Two domains: assigned code points inside a clean ASCII carrier, and "
            "pure-ASCII text that needs no repair at all — any change to the "
            "latter is cost with no possible benefit."
        ),
    )

    #: Coarse enough to stay sub-second; strided, so it spans the planes.
    STRIDE = 31

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        all_surfaces = self.transforms()
        # Key builders are many-to-one by contract: sort_key and catalog_key
        # exist so two spellings of one thing compare equal. Scoring them beside
        # a text normalizer would make a library look destructive for doing its
        # job — and would rank a tool with no key builder as the safer one.
        collapsing = set(self.subject.keys()) if self.subject else set()
        surface_map, key_map = damage.split_by_intent(all_surfaces, collapsing)

        codepoints = thin(damage.assigned_sample(self.STRIDE), limit)
        carried = damage.carried(codepoints)
        clean = damage.clean_ascii_corpus(min(limit or 1200, 1200))
        outcome.population = len(carried)
        record(
            outcome,
            domain=(
                f"{len(carried)} assigned code points in an ASCII carrier, plus "
                f"{len(clean)} pure-ASCII strings"
            ),
            predicates=sorted(surface_map),
            collapsing_surfaces_excluded=sorted(key_map),
            stride=self.STRIDE,
            carriers=list(damage.CARRIERS),
            degenerate_if="destruction > 50% or injectivity < 10%",
        )

        per = damage.per_surface(surface_map, carried)
        worst_name, worst = damage.worst(per)
        gentle_name, gentle = damage.gentlest(per)
        clean_per = damage.per_surface(surface_map, clean)
        cw_name, cw = damage.worst(clean_per)
        cg_name, cg = damage.gentlest(clean_per)

        add(outcome, "codepoints", len(carried), unit="strings")
        # Both ends, always. Either alone misrepresents.
        add(
            outcome,
            "destroyed_worst_surface",
            worst.destroyed,
            of=worst.inputs,
            higher_is_better=False,
            detail=f"`{worst_name}` — the costliest text surface on offer",
        )
        add(
            outcome,
            "destroyed_gentlest_surface",
            gentle.destroyed,
            of=gentle.inputs,
            higher_is_better=False,
            detail=f"`{gentle_name}` — the least costly text surface on offer",
        )
        add(
            outcome,
            "injectivity_worst_surface",
            worst.injectivity,
            of=1.0,
            unit="ratio",
            detail="distinct outputs per distinct input; low means merging, which "
            "is how a coverage score is faked — but see the collapsing row below",
        )
        add(
            outcome,
            "injectivity_gentlest_surface",
            gentle.injectivity,
            of=1.0,
            unit="ratio",
            detail=f"`{gentle_name}`",
        )
        add(
            outcome,
            "retention_worst_surface",
            worst.retention,
            of=1.0,
            unit="ratio",
            higher_is_better=True,
            detail=f"characters surviving `{worst_name}`",
        )
        add(
            outcome,
            "retention_gentlest_surface",
            gentle.retention,
            of=1.0,
            unit="ratio",
            higher_is_better=True,
            detail=f"characters surviving `{gentle_name}`",
        )
        add(
            outcome,
            "clean_ascii_altered_worst",
            cw.altered,
            of=cw.inputs,
            higher_is_better=False,
            detail=f"`{cw_name}` rewrites text with nothing to fix",
        )
        add(
            outcome,
            "clean_ascii_altered_gentlest",
            cg.altered,
            of=cg.inputs,
            higher_is_better=False,
            detail=f"`{cg_name}`",
        )
        add(
            outcome,
            "degenerate",
            1.0 if (worst.degenerate and gentle.degenerate) else 0.0,
            of=1.0,
            higher_is_better=False,
            detail="every text surface scores by destroying rather than resolving",
        )
        if key_map:
            key_damage = damage.per_surface(key_map, carried)
            _kn, kd = damage.worst(key_damage)
            add(
                outcome,
                "collapsing_surfaces",
                len(key_map),
                detail="key builders, excluded above: collapsing is their contract",
            )
            add(
                outcome,
                "key_injectivity",
                kd.injectivity,
                of=1.0,
                unit="ratio",
                detail="reported, not scored — a low number here is the feature",
            )
        outcome.extra = {
            "per_surface": {
                name: {
                    "destruction_rate": d.destruction_rate,
                    "alteration_rate": d.alteration_rate,
                    "injectivity": d.injectivity,
                    "retention": d.retention,
                }
                for name, d in sorted(per.items())
            },
            "collapsing_surfaces": sorted(key_map),
        }


SUITES = [
    UTS39ConfusableCoverage(),
    CorruptionCost(),
    UTS39EquivalenceClasses(),
    UTS39MixedNumbers(),
    UTS39AugmentedScripts(),
    UCDScriptTable(),
    UCDBidiClass(),
    UAX29WordJoiners(),
    DefaultIgnorableCasefold(),
    ICANNLatinLGR(),
    CLDRNonEmojiNames(),
]
