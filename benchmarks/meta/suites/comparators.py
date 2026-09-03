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

from ..base import CACHE, DATA, SuiteBase, add, artifact, record
from ..fetch import Source
from ..protocol import Availability, Family, Outcome, Provenance
from ..subjects import Capability, Job, Role


class ConfusableBenchV1(SuiteBase):
    name = "confusable-bench-v1"
    family = Family.COMPARATOR
    availability = Availability.NETWORK
    env_var = "DISARM_META_CONFUSABLE_BENCH"
    SOURCES = (
        Source(
            url="https://raw.githubusercontent.com/paultendo/namespace-guard/main"
            "/docs/data/confusable-bench.v1.json",
            filename="confusable-bench.v1.json",
            licence="MIT",
            note="140 rows: 120 malicious, 20 benign controls",
        ),
    )
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
        return self.provisioned() or artifact(
            CACHE / "confusable-bench.v1.json",
            DATA / "confusable-bench.v1.json",
            env=self.env_var,
        )

    @staticmethod
    def _is_malicious(row: dict[str, object]) -> bool:
        """Use the corpus's own `label`; fall back to threatClass.

        The publisher labels every row explicitly (120 malicious, 20 benign).
        Inferring it from `threatClass` instead would be this harness deciding
        what counts as an attack in somebody else's benchmark.
        """
        label = str(row.get("label", "")).lower()
        if label in ("malicious", "benign"):
            return label == "malicious"
        return str(row.get("threatClass", "")).lower() not in ("control", "benign", "")

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

        is_malicious = self._is_malicious

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
    SOURCES = (
        Source(
            url="https://raw.githubusercontent.com/paultendo/confusable-vision/main"
            "/data/output/confusable-weights-v2.json",
            filename="confusable-vision.json",
            licence="CC-BY-4.0 (datasets); repository licence unspecified",
            note="the exact file data/confusables_supplement.tsv cites as its "
            "provenance — 4,174 pairs, v2026-03-02",
        ),
    )
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
        return self.provisioned() or artifact(
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
            # The published shape is {"meta": {...}, "edges": [...]}; each edge
            # carries `source`, `target` and a measured `danger` score.
            records = (
                blob if isinstance(blob, list) else blob.get("edges") or blob.get("pairs") or []
            )
            for rec in records:
                if not isinstance(rec, dict):
                    continue
                src = rec.get("source") or rec.get("from") or rec.get("a")  # noqa: E501
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

        # unmapped_confusables() is a frozenset of single-character strings.
        # Iterating it with `for c, *_ in ...` unpacks each string and only
        # happens to work while every member is one character long.
        unmapped: set[str] = set(disarm.unmapped_confusables() or ())
        reached = flagged = 0
        gaps_not_named = named_but_covered = uncovered = 0
        for src, tgt, _score in pairs:
            covered = disarm.canonicalize(src) == disarm.canonicalize(tgt)
            listed = src in unmapped
            if covered:
                reached += 1
                if listed:
                    named_but_covered += 1
            else:
                uncovered += 1
                if not listed:
                    gaps_not_named += 1
            if disarm.is_confusable(src):
                flagged += 1
        n = len(pairs)
        add(outcome, "pairs", n, unit="pairs")
        add(outcome, "collide_in_canonicalize", reached, of=n, higher_is_better=True)
        add(outcome, "flagged_by_is_confusable", flagged, of=n, higher_is_better=True)
        # The old form counted pairs *listed* as unmapped and scored higher as
        # better, so the only way to reach 100% was to map nothing: covering a
        # pair removed it from the gap list and lowered the score. Between 0.14.1
        # and 0.15.0 the list went 4,384 -> 4,330 with 54 leaving and **none
        # joining** — pure coverage gain, reported as a 21.8% -> 19.1% loss.
        # These two ask instead whether the gap list is *accurate*, and neither
        # can be improved by refusing to map anything.
        add(
            outcome,
            "gaps_not_named",
            gaps_not_named,
            of=uncovered or None,
            higher_is_better=False,
            detail="pairs the fold misses that unmapped_confusables() does not "
            "list — a blind spot in the introspection itself",
        )
        add(
            outcome,
            "named_but_covered",
            named_but_covered,
            of=reached or None,
            higher_is_better=False,
            detail="listed as a gap and in fact covered — a stale entry",
        )


class UntraceTechniques(SuiteBase):
    name = "untrace-techniques"
    family = Family.COMPARATOR
    availability = Availability.MANUAL
    env_var = "DISARM_META_UNTRACE"
    SOURCES = (
        Source(
            url="https://codeload.github.com/juriku/untrace/tar.gz/refs/heads/main",
            filename="untrace",
            licence="MIT",
            kind="tar.gz",
            member="untrace-main/testdata",
            note="the rival's own test corpus — its technique taxonomy, not ours",
        ),
    )
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
        return self.provisioned() or artifact(CACHE / "untrace_techniques.tsv", env=self.env_var)

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        import disarm

        from ..base import detectors

        path = self.locate()
        assert path is not None
        probes: list[tuple[str, str]] = []
        if path.is_dir():
            # untrace's own case tree: testdata/cases/<technique>/in/<file>.
            # The directory name IS the technique label, which is the point —
            # the taxonomy is theirs, not ours, and disarm's detector cannot
            # nominate the techniques it is blind to.
            cases = path / "cases" if (path / "cases").is_dir() else path
            for case in sorted(d for d in cases.iterdir() if d.is_dir()):
                for f in sorted(case.rglob("*")):
                    if not f.is_file() or f.suffix.lower() in _BINARY_SUFFIXES:
                        continue
                    try:
                        text = f.read_text(encoding="utf-8")
                    except (UnicodeDecodeError, OSError):
                        continue
                    if text.strip():
                        probes.append((case.name, text))
                        break
        else:
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


#: Fixtures untrace ships that are not text probes.
_BINARY_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".epub", ".docx", ".woff", ".ico"}
)


def _safe(fn: Callable[[str], object], text: str) -> bool:
    try:
        return bool(fn(text))
    except Exception:  # noqa: BLE001
        return False


class WeaponizingUnicode(SuiteBase):
    name = "weaponizing-unicode"
    JOB = Job.CONFUSABLE_FOLD
    family = Family.COMPARATOR
    availability = Availability.NETWORK
    MULTI_SUBJECT = True
    REQUIRES_ANY = (Capability.DETECT, Capability.TRANSFORM)
    env_var = "DISARM_META_WEAPONIZING"
    summary = "Homoglyph candidates a neural model found, not a table or a human."
    provenance = Provenance(
        origin="Perry Deng & Cooper Linsky",
        citation="arXiv:2010.04382 — Weaponizing Unicodes with Deep Learning: "
        "Identifying Homoglyphs with Weakly Labeled Data",
        url="https://github.com/PerryXDeng/weaponizing_unicode",
        version="new_predicted_homoglyphs.txt, 8,452 code points",
        licence="MIT",
        issues=(40, 791, 738),
        finding=(
            "New in this registry — no prior disarm issue rests on it. It is the "
            "third independent way of deciding what a homoglyph is: UTS #39 is a "
            "curated committee table, confusable-vision is measured by rendering "
            "and comparing glyphs, and this is a triplet-loss model trained on "
            "weakly labelled font renderings. Where the three disagree is where "
            "the coverage question is actually open."
        ),
        notes=(
            "Weak labels, so a miss is not automatically an error — the set is a "
            "model's candidates rather than ground truth, and the paper says so. "
            "It is a code-point SET, not source->target pairs, which is why this "
            "scores detection rather than folding. The 12.4% Private Use tail is "
            "excluded from the scored denominator: a tool that strips PUA handles "
            "those for a reason that has nothing to do with confusability, and "
            "crediting it would repeat the mistake retention made with format "
            "characters."
        ),
    )

    SOURCES = (
        Source(
            url="https://raw.githubusercontent.com/PerryXDeng/weaponizing_unicode"
            "/master/new_predicted_homoglyphs.txt",
            filename="weaponizing-unicode-homoglyphs.txt",
            licence="MIT",
            note="one `U+hex, decimal` per line; the model's predicted homoglyphs",
        ),
    )

    def locate(self) -> Path | None:
        return self.provisioned() or artifact(
            CACHE / "weaponizing-unicode-homoglyphs.txt", env=self.env_var
        )

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        import unicodedata

        from ..base import thin

        path = self.locate()
        assert path is not None
        codepoints: list[int] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            head = line.split(",", 1)[0].strip()
            if not head.upper().startswith("U+"):
                continue
            try:
                codepoints.append(int(head[2:], 16))
            except ValueError:
                continue
        codepoints = thin(sorted(set(codepoints)), limit)
        outcome.population = len(codepoints)
        if not codepoints:
            add(outcome, "codepoints", 0)
            return

        def category(cp: int) -> str:
            try:
                return unicodedata.category(chr(cp))
            except ValueError:
                return "Cs"

        private_use = [cp for cp in codepoints if category(cp) == "Co"]
        scored = [cp for cp in codepoints if category(cp) not in ("Co", "Cn", "Cs")]

        det = self.detect()
        surfaces = (
            self.subject.role(Role.SANITIZER, job=self.JOB) if self.subject is not None else {}
        )
        record(
            outcome,
            domain=f"{len(scored)} assigned non-private-use candidates "
            f"of {len(codepoints)} in the released set",
            predicates=[*sorted(surfaces), *sorted(det)],
            excluded="Private Use, unassigned and surrogate code points",
            label_quality="weak — the paper trains on weakly labelled data",
        )

        add(outcome, "codepoints", len(codepoints), unit="codepoints")
        add(
            outcome,
            "private_use_excluded",
            len(private_use),
            of=len(codepoints),
            detail="stripping these is unrelated to confusability, so they are not "
            "scored — the artefact of a font-rendering method",
        )
        if det:
            flagged = sum(1 for cp in scored if any(_safe(fn, chr(cp)) for fn in det.values()))
            add(
                outcome,
                "flagged_by_a_detector",
                flagged,
                of=len(scored),
                higher_is_better=True,
                detail="the subject considers this candidate suspicious",
            )
        if surfaces:
            fn = next(iter(surfaces.values()))
            changed = sum(1 for cp in scored if _changed_by(fn, chr(cp)))
            add(
                outcome,
                "rewritten_by_the_sanitizer",
                changed,
                of=len(scored),
                detail="the declared sanitizer alters it — a census, because a "
                "model's weak label is not authority that it should",
            )


def _changed_by(fn: Callable[[str], str], ch: str) -> bool:
    try:
        return fn(f"aa{ch}bb") != f"aa{ch}bb"
    except Exception:  # noqa: BLE001
        return False


class ReverseCaptcha(SuiteBase):
    name = "reverse-captcha"
    JOB = Job.PROMPT_HYGIENE
    family = Family.ACADEMIC
    availability = Availability.NETWORK
    MULTI_SUBJECT = True
    REQUIRES_ANY = (Capability.DETECT, Capability.TRANSFORM)
    env_var = "DISARM_META_REVERSE_CAPTCHA"
    summary = "Invisible zero-width instructions hidden in prompts, with benign controls."
    provenance = Provenance(
        origin="canonicalmg",
        citation="arXiv:2603.00164 — Reverse CAPTCHA: Evaluating LLM "
        "Susceptibility to Invisible Unicode Instruction Injection",
        url="https://github.com/canonicalmg/reverse-captcha-eval",
        version="scripts/prompts.json — 50 cases, 5 schemes",
        licence="MIT (declared in the README, not as a LICENSE file)",
        issues=(742, 743, 748, 700),
        finding=(
            "The channel #742 and #748 describe, with a released corpus: a "
            "zero-width payload encoding an instruction the model obeys and the "
            "reader never sees. Each case carries the answer a clean model gives "
            "and the answer a compromised one gives, so the attack has ground "
            "truth rather than a judgement call."
        ),
        notes=(
            "Four attack schemes of ten (zero-width unhinted, hint-aware, "
            "hint-codepoints, hint-full) plus ten benign controls, so false "
            "positives are defined by the corpus author rather than by disarm. "
            "Removing the payload is only half the job — a sanitizer that also "
            "mangles the visible question has not helped, so the visible text is "
            "scored beside the removal."
        ),
    )

    SOURCES = (
        Source(
            url="https://raw.githubusercontent.com/canonicalmg/reverse-captcha-eval"
            "/main/scripts/prompts.json",
            filename="reverse-captcha-prompts.json",
            licence="MIT",
            note="50 cases: 40 zero-width injections across four schemes, 10 benign controls",
        ),
    )

    #: Carriers the corpus uses to encode a hidden instruction.
    INVISIBLE = frozenset({0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF})

    def locate(self) -> Path | None:
        return self.provisioned() or artifact(
            CACHE / "reverse-captcha-prompts.json", env=self.env_var
        )

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        path = self.locate()
        assert path is not None
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            rows = rows.get("cases") or rows.get("prompts") or []
        if limit is not None:
            rows = rows[:limit]
        outcome.population = len(rows)
        if not rows:
            add(outcome, "cases", 0)
            return

        attacks = [r for r in rows if r.get("scheme") != "control"]
        controls = [r for r in rows if r.get("scheme") == "control"]
        det = self.detect()
        surfaces = (
            self.subject.role(Role.SANITIZER, job=self.JOB) if self.subject is not None else {}
        )
        record(
            outcome,
            domain=f"{len(attacks)} zero-width injections and {len(controls)} controls",
            predicates=[*sorted(surfaces), *sorted(det)],
            carriers=sorted(f"U+{c:04X}" for c in self.INVISIBLE),
            removal_means="no carrier code point survives in the output",
        )

        def carriers_in(text: str) -> int:
            return sum(1 for c in text if ord(c) in self.INVISIBLE)

        def visible(text: str) -> str:
            return "".join(c for c in text if ord(c) not in self.INVISIBLE)

        add(outcome, "cases", len(rows), unit="cases")
        add(outcome, "attack_cases", len(attacks), of=len(rows))
        add(outcome, "control_cases", len(controls), of=len(rows))

        if det:
            caught = sum(1 for r in attacks if any(_safe(fn, r["prompt"]) for fn in det.values()))
            add(
                outcome,
                "attacks_detected",
                caught,
                of=len(attacks) or None,
                higher_is_better=True,
                detail="some detector fires on a prompt carrying a hidden instruction",
            )
            if controls:
                fp = sum(1 for r in controls if any(_safe(fn, r["prompt"]) for fn in det.values()))
                add(
                    outcome,
                    "controls_false_positive",
                    fp,
                    of=len(controls),
                    higher_is_better=False,
                    detail="fires on a benign control — the corpus author's "
                    "definition of a false positive, not ours",
                )

        if surfaces and attacks:
            fn = next(iter(surfaces.values()))
            removed = intact = 0
            for r in attacks:
                out = _apply_text(fn, r["prompt"])
                if carriers_in(out) == 0:
                    removed += 1
                if visible(out) == visible(r["prompt"]):
                    intact += 1
            add(
                outcome,
                "payload_removed",
                removed,
                of=len(attacks),
                higher_is_better=True,
                detail="no carrier code point survives the declared sanitizer",
            )
            add(
                outcome,
                "visible_text_intact",
                intact,
                of=len(attacks),
                higher_is_better=True,
                detail="the question a human reads is unchanged — removing the "
                "payload while mangling the prompt is not a win",
            )


def _apply_text(fn: Callable[[str], str], text: str) -> str:
    try:
        return fn(text)
    except Exception:  # noqa: BLE001
        return text


SUITES = [
    ConfusableBenchV1(),
    ConfusableVision(),
    UntraceTechniques(),
    WeaponizingUnicode(),
    ReverseCaptcha(),
]
