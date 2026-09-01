"""Suites anchored to a normative table somebody else publishes.

Unicode Consortium (UTS #39, UTS #46, UTS #51, UAX #9, UAX #29, the UCD), the
IETF (RFC 5892), ICANN (the Latin second-level LGR) and CLDR. These are the
strongest kind of external benchmark available here: the table *defines* the
right answer, so a disagreement is a finding rather than an opinion.

Every suite reads the table and reports a census. None of them edits a table,
and none carries a vector of its own.
"""

from __future__ import annotations

import sys
import unicodedata
from collections import Counter
from pathlib import Path

from ..base import DATA, FIXTURES, SuiteBase, add, artifact, thin
from ..protocol import Availability, Family, Outcome, Provenance

_MAX_CP = sys.maxunicode + 1


# --------------------------------------------------------------------------
# UTS #39


class UTS39ConfusableCoverage(SuiteBase):
    name = "uts39-confusables"
    family = Family.NORMATIVE
    availability = Availability.VENDORED
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
        import disarm

        path = self.locate()
        assert path is not None
        sources: set[int] = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            head = line.split(";", 1)[0].strip()
            try:
                sources.add(int(head, 16))
            except ValueError:
                continue
        ordered = thin(sorted(sources), limit)
        sources = set(ordered)
        outcome.population = len(sources)

        folded = unchanged = 0
        rtl_unreached = 0
        for cp in sources:
            ch = chr(cp)
            if disarm.strip_obfuscation(ch) != ch:
                folded += 1
            else:
                unchanged += 1
                if unicodedata.bidirectional(ch) in ("R", "AL"):
                    rtl_unreached += 1
        add(outcome, "sources", len(sources), unit="codepoints")
        add(
            outcome,
            "folded",
            folded,
            of=len(sources),
            higher_is_better=True,
            detail="strip_obfuscation changes the code point",
        )
        add(
            outcome,
            "unreached",
            unchanged,
            of=len(sources),
            higher_is_better=False,
            detail="in UTS #39 and unchanged — addressable, route via #40",
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
        finding=(
            "#777: unimplemented at 0.14.1 — `1٢۳４५` reported clean, and ASCII mixed "
            "with any of the other 75 numbering systems was one script to "
            "is_mixed_script."
        ),
        notes="Numbering systems are grouped by the decimal-zero of each Nd run.",
    )

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
        finding=(
            "#776: applied in inspect_anomalies only — `例え` was clean to the "
            "detector, mixed-script to is_mixed_script, and suspicious as a hostname."
        ),
        notes=(
            "Augmented sets fold Hani into Hanb/Jpan/Kore and Hira/Kana into Jpan; "
            "the benchmark is surface agreement, and the table decides who is right."
        ),
    )

    #: Script-mixture probes whose correct verdict UTS #39 §5.1 fixes: each is a
    #: single augmented script, so none of them is mixed-script.
    SINGLE_AUGMENTED = ("例え", "カタカナ漢字", "한글漢字", "漢字ひらがな")

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        import disarm

        probes = list(self.SINGLE_AUGMENTED)[: limit or None]
        outcome.population = len(probes)
        disagreements = 0
        by_surface: Counter[str] = Counter()
        for text in probes:
            verdicts = {
                "is_mixed_script": disarm.is_mixed_script(text),
                "inspect_anomalies": "mixed_script" in disarm.inspect_anomalies(text).kinds,
                "is_suspicious_hostname": disarm.is_suspicious_hostname(f"{text}.example")[0],
            }
            for surface, flagged in verdicts.items():
                if flagged:
                    by_surface[surface] += 1
            if len(set(verdicts.values())) > 1:
                disagreements += 1
        add(outcome, "probes", len(probes), unit="strings")
        add(
            outcome,
            "surface_disagreements",
            disagreements,
            of=len(probes),
            higher_is_better=False,
            detail="the three surfaces do not return one verdict",
        )
        for surface in ("is_mixed_script", "inspect_anomalies", "is_suspicious_hostname"):
            add(
                outcome,
                f"flagged_by_{surface}",
                by_surface[surface],
                of=len(probes),
                detail="a single augmented script should not be mixed",
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

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        import disarm

        rtl = [
            cp
            for cp in range(_MAX_CP)
            if unicodedata.category(chr(cp)) != "Cn"
            and unicodedata.bidirectional(chr(cp)) in ("R", "AL")
        ]
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
    summary = "Visible within-word joiners (Pd + Pc): is a fragmented word detected?"
    provenance = Provenance(
        origin="Unicode Consortium",
        citation="UAX #29 / General_Category Pd, Pc",
        url="https://www.unicode.org/reports/tr29/",
        version="derived",
        licence="Unicode License v3",
        issues=(750, 752, 755, 804),
        finding=(
            "#750: the segmentation branch recognised three separators, so 16 of the "
            "36 within-word joiners were silent on both paths and U+2010 disagreed "
            "with U+002D."
        ),
        notes="The invisible-carrier twin of this class has a full out-of-scope entry.",
    )

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        import disarm

        joiners = [cp for cp in range(_MAX_CP) if unicodedata.category(chr(cp)) in ("Pd", "Pc")]
        joiners = thin(joiners, limit)
        outcome.population = len(joiners)

        detected = recovered = 0
        for cp in joiners:
            fragmented = f"pass{chr(cp)}word"
            if disarm.has_anomalies(fragmented):
                detected += 1
            if disarm.strip_obfuscation(fragmented) == "password":
                recovered += 1
        add(outcome, "joiners", len(joiners), unit="codepoints")
        add(
            outcome,
            "detected",
            detected,
            of=len(joiners),
            higher_is_better=True,
            detail="has_anomalies flags the fragmented word",
        )
        add(
            outcome,
            "recovered",
            recovered,
            of=len(joiners),
            higher_is_better=True,
            detail="strip_obfuscation rejoins it",
        )


class DefaultIgnorableCasefold(SuiteBase):
    name = "ucd-toNFKC-casefold"
    family = Family.NORMATIVE
    availability = Availability.NETWORK
    env_var = "DISARM_META_DERIVEDCORE"
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


class ICANNLatinLGR(SuiteBase):
    name = "icann-lgr-latin"
    family = Family.NORMATIVE
    availability = Availability.NETWORK
    env_var = "DISARM_META_ICANN_LGR"
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
            "identical; canonicalize collided 2 of them."
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
        import re

        import disarm

        path = self.locate()
        assert path is not None
        text = path.read_text(encoding="utf-8", errors="replace")
        # Variant pairs appear as "U+XXXX" pairs on a blocked-variant row in the
        # published LGR, and as two hex columns in the vendored TSV extract.
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
            for row in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S):
                cps = re.findall(r"U\+([0-9A-Fa-f]{4,6})", row)
                if len(cps) >= 2 and "blocked" in row.lower():
                    pairs.append((int(cps[0], 16), int(cps[1], 16)))
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
        import disarm

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

        closed = 0
        intra_script_only = 0
        for target in keys:
            members = classes[target]
            folded = {disarm.canonicalize(m) for m in members}
            if len(folded) == 1 and disarm.canonicalize(target) in folded:
                closed += 1
            # A class with no ASCII-reachable member is the shape #848 describes:
            # nothing in it can act as a fold target for the rest.
            if not any(disarm.canonicalize(m).isascii() for m in [*members, target]):
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


SUITES = [
    UTS39ConfusableCoverage(),
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
