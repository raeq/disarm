"""Third-party labelled benchmarks and rival implementations.

The strongest external evidence available: somebody else built the benchmark,
labelled the rows, and published both. A labelled benchmark is the only place in
this harness where precision and recall mean anything, because it is the only
place where a *false positive* is defined by someone other than disarm.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from ..base import CACHE, DATA, SuiteBase, add, artifact
from ..protocol import Availability, Family, Outcome, Provenance


class ConfusableBenchV1(SuiteBase):
    name = "confusable-bench-v1"
    family = Family.COMPARATOR
    availability = Availability.NETWORK
    env_var = "DISARM_META_CONFUSABLE_BENCH"
    summary = "140 labelled identifier rows: precision and recall per policy."
    provenance = Provenance(
        origin="Paul Wood FRSA (@paultendo) — namespace-guard",
        citation="confusable-bench.v1 (docs/data/confusable-bench.v1.json)",
        url="https://paultendo.github.io/posts/unicode-identifier-threat-model/",
        version="v1 — 120 malicious, 20 benign",
        licence="MIT",
        issues=(736, 737, 732),
        finding=(
            "#736: no single surface exceeds R=0.550. The result disarm actually "
            "reaches — P=1.000 R=0.983 — is a three-surface composition "
            "(lexicon OR is_confusable OR key collision) that no documentation page "
            "names, so a caller cannot arrive at it from the docs."
        ),
        notes=(
            "The only labelled benchmark in the registry, and the only one where a "
            "false positive is defined externally: 20 benign controls decide that, "
            "not disarm. Rows carry `identifier`, `protect`, `category` and "
            "`threatClass`; the `protect` column asks the set-shaped question "
            "find_key_collisions is built for, so predicates and key builders are "
            "scored on the same rows."
        ),
    )

    def locate(self) -> Path | None:
        return artifact(
            CACHE / "confusable-bench.v1.json",
            DATA / "confusable-bench.v1.json",
            env=self.env_var,
        )

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        import disarm

        path = self.locate()
        assert path is not None
        blob = json.loads(path.read_text(encoding="utf-8"))
        rows: list[dict[str, object]] = (
            blob if isinstance(blob, list) else blob.get("rows", blob.get("cases", []))
        )
        if limit is not None:
            rows = rows[:limit]
        outcome.population = len(rows)
        if not rows:
            add(outcome, "rows", 0)
            return

        def is_malicious(row: dict[str, object]) -> bool:
            klass = str(row.get("threatClass", "")).lower()
            return klass not in ("control", "benign", "")

        def collides(builder: Callable[[str], str], row: dict[str, object]) -> bool:
            ident = str(row.get("identifier", ""))
            raw = row.get("protect") or []
            if isinstance(raw, str):
                protect = [raw]
            elif isinstance(raw, (list, tuple, set, frozenset)):
                protect = [str(x) for x in raw]
            else:
                protect = []
            key = builder(ident)
            return any(builder(p) == key and p != ident for p in protect)

        policies: dict[str, Callable[[dict[str, object]], bool]] = {
            "has_anomalies": lambda r: disarm.has_anomalies(str(r.get("identifier", ""))),
            "is_confusable": lambda r: bool(disarm.is_confusable(str(r.get("identifier", "")))),
            "is_mixed_script": lambda r: disarm.is_mixed_script(str(r.get("identifier", ""))),
            "catalog_key_collision": lambda r: collides(disarm.catalog_key, r),
            "canonicalize_strict_collision": lambda r: collides(disarm.canonicalize_strict, r),
        }
        # The composition #736 measures: the union is the only policy that reaches
        # the published headline, and it is a union no page names.
        policies["union_confusable_or_collision"] = lambda r: (
            bool(disarm.is_confusable(str(r.get("identifier", ""))))
            or collides(disarm.catalog_key, r)
            or collides(disarm.canonicalize_strict, r)
        )

        malicious = sum(1 for r in rows if is_malicious(r))
        benign = len(rows) - malicious
        add(outcome, "rows", len(rows), unit="rows")
        add(outcome, "malicious", malicious, of=len(rows))
        add(outcome, "benign_controls", benign, of=len(rows))

        scores: dict[str, dict[str, float]] = {}
        for name, policy in policies.items():
            tp = fp = fn = tn = 0
            for row in rows:
                try:
                    flagged = policy(row)
                except Exception:  # noqa: BLE001
                    flagged = False
                if is_malicious(row):
                    tp, fn = (tp + 1, fn) if flagged else (tp, fn + 1)
                else:
                    fp, tn = (fp + 1, tn) if flagged else (fp, tn + 1)
            precision = tp / (tp + fp) if (tp + fp) else 1.0
            recall = tp / (tp + fn) if (tp + fn) else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
            scores[name] = {
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }
            add(outcome, f"recall_{name}", recall, of=1.0, unit="ratio", higher_is_better=True)
            add(
                outcome, f"precision_{name}", precision, of=1.0, unit="ratio", higher_is_better=True
            )
        best = max(scores.items(), key=lambda kv: kv[1]["f1"])
        add(
            outcome,
            "best_f1",
            best[1]["f1"],
            of=1.0,
            unit="ratio",
            higher_is_better=True,
            detail=f"policy `{best[0]}`",
        )
        outcome.extra = {"scores": scores}


class ConfusableVision(SuiteBase):
    name = "confusable-vision"
    family = Family.COMPARATOR
    availability = Availability.NETWORK
    env_var = "DISARM_META_CONFUSABLE_VISION"
    summary = "Measured visual-confusability pairs: how many does any disarm surface reach?"
    provenance = Provenance(
        origin="Paul Wood FRSA (@paultendo) — confusable-vision",
        citation="confusable-weights / RaySpace measured datasets",
        url="https://paultendo.github.io/",
        version="operator-selected tranche",
        licence="CC-BY-4.0 (datasets), MIT (code)",
        issues=(738, 336, 342),
        finding=(
            "#738: data/confusables_supplement.tsv is pinned to one 2026-03-02 "
            "tranche carved to Greek/Cyrillic (14 rows). Four further measured sets "
            "have shipped since, and the highest-scoring pairs in them are absent "
            "from every disarm surface — including the coverage denominator, so the "
            "introspection cannot report them as missing."
        ),
        notes=(
            "This is disarm's own upstream, not an outside critique: 14 rows of the "
            "shipped supplement come from this instrument. The suite measures the "
            "gap between the pinned tranche and whatever the operator supplies. "
            "Expects TSV or JSON pairs with a source, a target and a score."
        ),
    )

    def locate(self) -> Path | None:
        return artifact(
            CACHE / "confusable-vision.json",
            CACHE / "confusable-vision.tsv",
            env=self.env_var,
        )

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        import disarm

        path = self.locate()
        assert path is not None
        pairs: list[tuple[str, str, float]] = []
        if path.suffix == ".json":
            blob = json.loads(path.read_text(encoding="utf-8"))
            records = blob if isinstance(blob, list) else blob.get("pairs", [])
            for rec in records:
                if not isinstance(rec, dict):
                    continue
                src = rec.get("source") or rec.get("from") or rec.get("a")
                tgt = rec.get("target") or rec.get("to") or rec.get("b")
                if isinstance(src, str) and isinstance(tgt, str):
                    score_raw = rec.get("score", rec.get("danger", 0)) or 0
                    pairs.append((src, tgt, float(score_raw)))
        else:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip() or line.startswith("#"):
                    continue
                cols = line.split("\t")
                if len(cols) >= 2:
                    score = float(cols[2]) if len(cols) > 2 and cols[2] else 0.0
                    pairs.append((cols[0], cols[1], score))
        if limit is not None:
            pairs = pairs[:limit]
        outcome.population = len(pairs)
        if not pairs:
            add(outcome, "pairs", 0)
            return

        reached = flagged = in_denominator = 0
        # unmapped_confusables() is a frozenset of single-character strings.
        # Iterating it with `for c, *_ in ...` unpacks each string and only
        # happens to work while every member is one character long.
        unmapped: set[str] = set(disarm.unmapped_confusables() or ())
        for src, tgt, _score in pairs:
            if disarm.canonicalize(src) == disarm.canonicalize(tgt):
                reached += 1
            if disarm.is_confusable(src):
                flagged += 1
            if src in unmapped:
                in_denominator += 1
        n = len(pairs)
        add(outcome, "pairs", n, unit="pairs")
        add(outcome, "collide_in_canonicalize", reached, of=n, higher_is_better=True)
        add(outcome, "flagged_by_is_confusable", flagged, of=n, higher_is_better=True)
        add(
            outcome,
            "visible_to_coverage_introspection",
            in_denominator,
            of=n,
            higher_is_better=True,
            detail="present in unmapped_confusables(), so a gap report can name it",
        )


class UntraceTechniques(SuiteBase):
    name = "untrace-techniques"
    family = Family.COMPARATOR
    availability = Availability.MANUAL
    env_var = "DISARM_META_UNTRACE"
    summary = "A rival detector's technique list: which does disarm report, and which decode?"
    provenance = Provenance(
        origin="juriku",
        citation="untrace (successor to hidden-characters-detector)",
        url="https://github.com/juriku/untrace",
        version="operator-selected checkout",
        licence="see upstream repository",
        issues=(700, 701, 702, 703, 704, 705, 706),
        finding=(
            "#701: disarm strips the three ASCII-smuggling carriers and never says "
            "what a run spells. Presence and decode are different strengths of "
            "evidence — an invisible character can arrive by accident, and a run "
            "that decodes to readable text cannot."
        ),
        notes=(
            "The comparison is against a technique taxonomy somebody else wrote, "
            "which is the point: disarm's own detector cannot nominate the "
            "techniques it is blind to. Expects one probe per line as "
            "`technique<TAB>text`."
        ),
    )

    def locate(self) -> Path | None:
        return artifact(CACHE / "untrace_techniques.tsv", env=self.env_var)

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        import disarm

        from ..base import detectors

        path = self.locate()
        assert path is not None
        probes: list[tuple[str, str]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            technique, _, text = line.partition("\t")
            if text:
                probes.append((technique.strip(), text))
        if limit is not None:
            probes = probes[:limit]
        outcome.population = len(probes)
        if not probes:
            add(outcome, "techniques", 0)
            return

        det = detectors()
        reported = removed = 0
        silent: list[str] = []
        for technique, text in probes:
            hit = any(_safe(fn, text) for fn in det.values())
            if hit:
                reported += 1
            else:
                silent.append(technique)
            if disarm.strip_obfuscation(text) != text:
                removed += 1
        n = len(probes)
        add(outcome, "techniques", n, unit="probes")
        add(outcome, "reported_by_any_detector", reported, of=n, higher_is_better=True)
        add(
            outcome,
            "altered_by_strip_obfuscation",
            removed,
            of=n,
            detail="removed — which is not the same as reported",
        )
        add(outcome, "silent", n - reported, of=n, higher_is_better=False)
        outcome.extra = {"silent_techniques": sorted(set(silent))}


def _safe(fn: Callable[[str], object], text: str) -> bool:
    try:
        return bool(fn(text))
    except Exception:  # noqa: BLE001
        return False


SUITES = [ConfusableBenchV1(), ConfusableVision(), UntraceTechniques()]
