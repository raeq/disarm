"""Self-referential sweeps — registered, excluded from every headline figure.

These reproduce real 0.15.0 findings, and they are **not benchmarks**. The
distinction is not where the input comes from (the code-point domain is the UCD,
which is external) but whether an outside authority decides the right answer.
For everything here, disarm is both the thing measured and the only oracle for
what the measurement should be, so a number moving proves nothing on its own.

They are kept because dropping them would leave the 0.15.0 record with a hole,
and because they are the sweeps most likely to catch a silent regression between
releases. :attr:`Provenance.external` is ``False`` on all of them; the runner
excludes them unless ``--include-introspective`` is passed, and the report never
folds them into an external score.
"""

from __future__ import annotations

import sys
import unicodedata

from ..base import SuiteBase, add, surfaces, thin
from ..protocol import Availability, Family, Outcome, Provenance

_MAX_CP = sys.maxunicode + 1


def _domain(limit: int | None) -> list[int]:
    """Assigned code points, thinned by even stride rather than truncated."""
    assigned = [cp for cp in range(_MAX_CP) if unicodedata.category(chr(cp)) != "Cn"]
    return thin(assigned, limit)


class FixedPointCensus(SuiteBase):
    name = "fixed-point-census"
    family = Family.INTROSPECTIVE
    availability = Availability.DERIVED
    summary = "Which presets and profiles are not fixed points: f(f(x)) != f(x)."
    provenance = Provenance(
        origin="disarm (self-referential)",
        citation="raeq/disarm#723, #751",
        url="https://github.com/raeq/disarm/issues/723",
        version="derived over the assigned code-point domain",
        licence="n/a",
        external=False,
        issues=(723, 751, 834),
        finding=(
            "#723: strip_obfuscation is not a fixed point — `ы` folds to `ƅi` — and "
            "the exhaustive idempotence gate tests the one function that iterates. "
            "#751: three of seven profiles are not fixed points either, and "
            "llm_guardrail leaves an unfolded homoglyph in its single-pass output."
        ),
        notes=(
            "An idempotence fix picks a fixed point, and picking the wrong one is a "
            "silent behaviour change — which is why this is worth re-running and "
            "not worth scoring."
        ),
    )

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        domain = _domain(limit)
        outcome.population = len(domain)
        surface_map = surfaces()
        unstable = {name: 0 for name in surface_map}
        for cp in domain:
            ch = chr(cp)
            for name, fn in surface_map.items():
                try:
                    once = fn(ch)
                    if fn(once) != once:
                        unstable[name] += 1
                except Exception:  # noqa: BLE001
                    continue
        n = len(domain)
        add(outcome, "codepoints", n, unit="codepoints")
        add(
            outcome,
            "surfaces_not_fixed_point",
            sum(1 for v in unstable.values() if v),
            of=len(surface_map),
            higher_is_better=False,
        )
        add(outcome, "worst_surface_unstable", max(unstable.values()), of=n, higher_is_better=False)
        outcome.extra = {"unstable_by_surface": {k: v for k, v in unstable.items() if v}}


class ASCIIProducingSteps(SuiteBase):
    name = "ascii-producing-steps"
    family = Family.INTROSPECTIVE
    availability = Availability.DERIVED
    summary = "Code points that gain ASCII punctuation, split by which step produced it."
    provenance = Provenance(
        origin="disarm (self-referential)",
        citation="raeq/disarm#719",
        url="https://github.com/raeq/disarm/issues/719",
        version="derived",
        licence="n/a",
        external=False,
        issues=(719, 721, 747),
        reproduces=(
            "confusable-fold-delimiter-census.py — an explicit PUNCT set (`-` and "
            "`_` excluded as unreserved), NFKC-membership attribution, and the "
            "carrier probe has_anomalies('ord' + c + 'end')."
        ),
        finding=(
            "#719: 493 code points gain ASCII punctuation — 261 from NFKC, 232 from "
            "the fold. 174 of the fold's 232 screen clean, and 76 of those produce "
            "`: = % & ? # / \\`."
        ),
        notes=(
            "canonicalize emits ASCII from two steps and only the NFKC half has a "
            "detector. The split is the whole point: the step that lacks a detector "
            "is the one the audit exists to find. U+00BD is the trap — its NFKC "
            "contains U+2044, so the ASCII `/` arrives one step later."
        ),
    )

    #: The census's own punctuation set. `-` and `_` are deliberately absent:
    #: both are unreserved in RFC 3986 and load-bearing in no grammar here, and
    #: including them moves every number in the table.
    PUNCT = ":=&?#%/\\.,;\"'<>|()[]{}@+*!$~^`"
    #: The subset that separates fields or introduces an escape.
    STRUCTURAL = set(":=%&?#/\\")

    REPRO_EXPECTED = {
        "emits_ascii_punctuation": 493,
        "nfkc_is_the_source": 261,
        "fold_is_the_only_source": 232,
        "fold_only_and_clean": 174,
        "fold_only_clean_and_structural": 76,
    }

    def reproduce(self) -> dict[str, float]:
        # confusable-fold-delimiter-census.py, method for method. The sweep in
        # measure() below used a looser punctuation test (anything ASCII, not
        # alphanumeric, not space), a bare has_anomalies(ch) probe and an
        # assigned-only domain. Each of those moves the split, and together they
        # reported the fold at 253 against the census's 232 — a difference in
        # method that reads as a change in behaviour.
        import disarm

        punct = set(self.PUNCT)
        rows = []
        for cp in range(_MAX_CP):
            if 0xD800 <= cp <= 0xDFFF:
                continue
            ch = chr(cp)
            if ch in punct:
                continue
            got = set(disarm.canonicalize(ch)) & punct
            if got:
                rows.append((ch, got))

        fold_only = [
            (ch, got) for ch, got in rows if not set(unicodedata.normalize("NFKC", ch)) & punct
        ]
        clean = [(ch, got) for ch, got in fold_only if not disarm.has_anomalies("ord" + ch + "end")]
        structural = [(ch, got) for ch, got in clean if got & self.STRUCTURAL]
        return {
            "emits_ascii_punctuation": len(rows),
            "nfkc_is_the_source": len(rows) - len(fold_only),
            "fold_is_the_only_source": len(fold_only),
            "fold_only_and_clean": len(clean),
            "fold_only_clean_and_structural": len(structural),
        }

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        import disarm

        domain = _domain(limit)
        outcome.population = len(domain)
        via_nfkc = via_fold = 0
        dangerous_unreported = 0
        for cp in domain:
            ch = chr(cp)
            if ch.isascii():
                continue
            out = disarm.canonicalize(ch)
            gained = set(out) & set(self.PUNCT)
            if not gained:
                continue
            nfkc = disarm.normalize(ch, form="NFKC")
            if any(c in nfkc for c in gained):
                via_nfkc += 1
            else:
                via_fold += 1
                if gained & self.STRUCTURAL and not disarm.has_anomalies("ord" + ch + "end"):
                    dangerous_unreported += 1
        add(outcome, "codepoints", len(domain), unit="codepoints")
        add(outcome, "ascii_via_nfkc", via_nfkc, detail="reported as compat_fold")
        add(
            outcome,
            "ascii_via_confusable_fold",
            via_fold,
            higher_is_better=False,
            detail="no detector rule covers this step",
        )
        add(
            outcome,
            "dangerous_and_clean",
            dangerous_unreported,
            of=via_fold,
            higher_is_better=False,
            detail="produces sink-relevant punctuation and screens clean",
        )


class KeyBuilderCollisions(SuiteBase):
    name = "key-builder-collisions"
    family = Family.INTROSPECTIVE
    availability = Availability.DERIVED
    summary = "Which classes each key builder merges, and which evade all three."
    provenance = Provenance(
        origin="disarm (self-referential)",
        citation="raeq/disarm#805, #806, #807, #643",
        url="https://github.com/raeq/disarm/issues/805",
        version="derived",
        licence="n/a",
        external=False,
        issues=(805, 806, 807, 643),
        finding=(
            "#805: noncharacters evade all three key builders, and #774 removed the "
            "accidental signal that had been covering it. #806: the key-stability "
            "corpus has zero noncharacters and zero soft hyphens, so the gate "
            "cannot see the classes most likely to drift."
        ),
        notes=(
            "A drift gate that does not contain a class cannot report that class "
            "moving — the gate and the thing it guards must not share a blind spot."
        ),
    )

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        import disarm

        builders = {
            "search_key": disarm.search_key,
            "catalog_key": disarm.catalog_key,
            "sort_key": disarm.sort_key,
        }
        # Classes that ought to vanish from a key: they carry no identity.
        noncharacters = [cp for cp in range(0xFDD0, 0xFDF0)]
        noncharacters += [(plane << 16) | low for plane in range(17) for low in (0xFFFE, 0xFFFF)]
        invisibles = [0x00AD, 0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x180E, 0x2800, 0x1680]
        probes = thin(noncharacters + invisibles, limit)
        outcome.population = len(probes)

        evades_all = 0
        per_builder = {name: 0 for name in builders}
        for cp in probes:
            base = "word"
            spiked = f"wo{chr(cp)}rd"
            merged_anywhere = False
            for name, fn in builders.items():
                try:
                    if fn(spiked) == fn(base):
                        per_builder[name] += 1
                        merged_anywhere = True
                except Exception:  # noqa: BLE001
                    continue
            if not merged_anywhere:
                evades_all += 1
        add(outcome, "probes", len(probes), unit="codepoints")
        add(
            outcome,
            "evades_all_builders",
            evades_all,
            of=len(probes),
            higher_is_better=False,
            detail="an identity-free code point that changes every key",
        )
        for name, hits in per_builder.items():
            add(outcome, f"merged_by_{name}", hits, of=len(probes), higher_is_better=True)


class SurfaceAgreement(SuiteBase):
    name = "surface-agreement"
    family = Family.INTROSPECTIVE
    availability = Availability.DERIVED
    summary = "Where normalize_confusables and the presets give different answers."
    provenance = Provenance(
        origin="disarm (self-referential)",
        citation="raeq/disarm#834",
        url="https://github.com/raeq/disarm/issues/834",
        version="derived",
        licence="n/a",
        external=False,
        issues=(834, 760, 787),
        finding=(
            "#834: normalize_confusables and every preset disagree on 68 code "
            'points — `normalize_confusables("ſ")` is `"f"` and '
            '`canonicalize("ſ")` is `"s"` — and nothing documents it. #760: '
            "3,655 of 4,928 compatibility forms pass through normalize_confusables "
            "unchanged, while llm-pipelines.md calls it NFKC-first."
        ),
        notes="Neither answer is wrong in isolation; the undocumented split is.",
    )

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        import disarm

        domain = _domain(limit)
        outcome.population = len(domain)
        disagree = 0
        for cp in domain:
            ch = chr(cp)
            if disarm.normalize_confusables(ch) != disarm.canonicalize(ch):
                disagree += 1
        add(outcome, "codepoints", len(domain), unit="codepoints")
        add(
            outcome,
            "normalize_confusables_vs_canonicalize",
            disagree,
            of=len(domain),
            higher_is_better=None,
            detail="the two folds land on different output",
        )


SUITES = [
    FixedPointCensus(),
    ASCIIProducingSteps(),
    KeyBuilderCollisions(),
    SurfaceAgreement(),
]
