"""Suites anchored to a corpus released alongside a paper.

Nine papers drove 0.15.0 findings. None of their corpora is vendored here: each
suite locates the released data through an environment variable (or the shared
cache) and reports SKIPPED without it. That is deliberate — copying an attack
corpus into this repository would make it disarm's corpus, and a corpus disarm
owns is a corpus disarm can be tuned against.

**Expected shape.** A suite reads JSONL (one object per line) or TSV with a
header. It needs a text column; a clean/reference column turns on recovery
scoring. Column names are matched case-insensitively from ``TEXT_COLUMNS`` /
``CLEAN_COLUMNS``, so most upstream releases load without conversion.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterator
from pathlib import Path

from .. import damage
from ..base import CACHE, SuiteBase, add, artifact, record
from ..fetch import Source
from ..protocol import Availability, Family, Outcome, Provenance

TEXT_COLUMNS = ("text", "perturbed", "adversarial", "attack", "suffix", "input", "body", "prompt")
CLEAN_COLUMNS = ("clean", "original", "reference", "label", "benign", "source")


def _rows(path: Path, limit: int | None) -> Iterator[tuple[str, str | None]]:
    """Yield ``(text, clean)`` from a JSONL or delimited release file."""
    n = 0
    if path.suffix.lower() in (".jsonl", ".ndjson", ".json"):
        with open(path, encoding="utf-8", errors="replace") as f:
            first = f.read(1)
            f.seek(0)
            records = json.load(f) if first == "[" else (json.loads(ln) for ln in f if ln.strip())
            for rec in records:
                if not isinstance(rec, dict):
                    continue
                text = _pick(rec, TEXT_COLUMNS)
                if not text:
                    continue
                yield text, _pick(rec, CLEAN_COLUMNS)
                n += 1
                if limit is not None and n >= limit:
                    return
        return
    delim = "\t" if path.suffix.lower() in (".tsv", ".tab") else ","
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.DictReader(f, delimiter=delim):
            text = _pick(row, TEXT_COLUMNS)
            if not text:
                continue
            yield text, _pick(row, CLEAN_COLUMNS)
            n += 1
            if limit is not None and n >= limit:
                return


def _pick(row: dict[str, object], names: tuple[str, ...]) -> str | None:
    lowered = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        val = lowered.get(name)
        if isinstance(val, str) and val.strip():
            return val
    return None


class AttackCorpusSuite(SuiteBase):
    """Score an external attack corpus for detection and recovery.

    Two questions, kept apart because 0.15.0 showed them answering differently:
    does disarm *see* the perturbation (detectors), and does it *undo* it (XMR
    against the canonicalized clean text, the same comparison
    ``adversarial_eval`` uses).
    """

    family = Family.ACADEMIC
    availability = Availability.MANUAL
    #: Every tool that rewrites text can be scored on an attack corpus, so these
    #: are the suites a cross-tool column is worth most on: "30% recovered" only
    #: means something beside what anything else recovers.
    MULTI_SUBJECT = True
    #: Filenames the suite will accept from the cache directory.
    filenames: tuple[str, ...] = ()

    def rows(self, path: Path, limit: int | None) -> list[tuple[str, str | None]]:
        """Load the corpus. Overridden where a release is not flat."""
        return list(_rows(path, limit))

    def locate(self) -> Path | None:
        candidates = [CACHE / self.name / n for n in self.filenames]
        candidates += [CACHE / n for n in self.filenames]
        return self.provisioned() or artifact(*candidates, env=self.env_var)

    def measure(self, outcome: Outcome, limit: int | None) -> None:

        path = self.locate()
        assert path is not None
        rows = self.rows(path, limit)
        outcome.population = len(rows)
        if not rows:
            add(outcome, "rows", 0)
            return

        det = self.detect()
        surface_map = self.transforms()
        record(
            outcome,
            domain=f"{len(rows)} rows of {self.provenance.citation}",
            predicates=[*sorted(surface_map), *sorted(det)],
            text_columns=list(TEXT_COLUMNS),
            clean_columns=list(CLEAN_COLUMNS),
            recovery_metric="exact match after applying the same surface to both sides",
            corruption_metric=(
                "the corpus's own clean column is, by its author's definition, "
                "text needing no repair; anything a surface does to it is cost"
            ),
        )
        detected = {name: 0 for name in det}
        xmr = {name: 0 for name in surface_map}
        altered = {name: 0 for name in surface_map}
        labelled = 0
        non_ascii = 0

        for text, clean in rows:
            if any(ord(c) > 0x7F for c in text):
                non_ascii += 1
            for name, fn in det.items():
                try:
                    if fn(text):
                        detected[name] += 1
                except Exception:  # noqa: BLE001
                    continue
            has_clean = clean is not None
            if has_clean:
                labelled += 1
            for surface, transform in surface_map.items():
                try:
                    out = transform(text)
                except Exception:  # noqa: BLE001
                    continue
                if out != text:
                    altered[surface] += 1
                # A recovery only counts if something survived: mapping both
                # sides to the empty string is deletion, not recovery.
                if clean is not None and out and out == transform(clean):
                    xmr[surface] += 1

        # The other direction, using the corpus's own ground truth: whatever a
        # surface does to the clean side is pure cost, and a tool can only look
        # good on recovery by destroying if this stays invisible.
        clean_rows = [c for _t, c in rows if c]
        if clean_rows:
            # Key builders collapse by contract, so scoring them as corruption
            # would charge a library for having them — the same exclusion
            # corruption-cost already makes.
            collapsing = set(self.subject.keys()) if self.subject else set()
            text_only, _keys = damage.split_by_intent(surface_map, collapsing)
            clean_damage = damage.per_surface(text_only or surface_map, clean_rows)
            worst_name, worst_damage = damage.worst(clean_damage)
            gentle_name, gentle_damage = damage.gentlest(clean_damage)

        n = len(rows)
        add(outcome, "rows", n, unit="rows")
        add(
            outcome,
            "non_ascii_rows",
            non_ascii,
            of=n,
            detail="rows carrying any non-ASCII code point",
        )
        add(
            outcome,
            "detected_any",
            sum(1 for v in detected.values() if v),
            of=len(det),
            detail="detector surfaces that fire on at least one row",
        )
        add(
            outcome,
            "rows_detected_by_best_detector",
            max(detected.values(), default=0),
            of=n,
            higher_is_better=True,
            detail="the single detector that sees the most rows",
        )
        best_xmr = max(xmr.values()) if labelled else 0
        add(
            outcome,
            "xmr_best_surface",
            best_xmr,
            of=labelled or None,
            higher_is_better=True,
            detail="best exact-match recovery across all 19 surfaces",
        )
        add(
            outcome,
            "rows_altered_by_most_active_surface",
            max(altered.values(), default=0),
            of=n,
            detail="rewritten whether or not anything was detected",
        )
        if clean_rows:
            add(
                outcome,
                "clean_rows_corrupted",
                worst_damage.altered,
                of=len(clean_rows),
                higher_is_better=False,
                detail=f"`{worst_name}` rewrites the corpus's own clean text",
            )
            add(
                outcome,
                "clean_rows_destroyed",
                worst_damage.destroyed,
                of=len(clean_rows),
                higher_is_better=False,
                detail="clean text reduced to nothing",
            )
            add(
                outcome,
                "clean_retention",
                worst_damage.retention,
                of=1.0,
                unit="ratio",
                higher_is_better=True,
                detail=f"clean-text characters surviving `{worst_name}`",
            )
            add(
                outcome,
                "clean_rows_corrupted_gentlest",
                gentle_damage.altered,
                of=len(clean_rows),
                higher_is_better=False,
                detail=f"`{gentle_name}` — the least destructive surface on offer",
            )
        outcome.extra = {
            "detected": detected,
            "xmr": xmr,
            "altered": altered,
            "labelled_rows": labelled,
        }


class BadCharacters(AttackCorpusSuite):
    name = "bad-characters"
    availability = Availability.NETWORK
    env_var = "DISARM_META_BAD_CHARACTERS"
    filenames = ("bad_characters.jsonl", "bad_characters.tsv", "bad_characters.csv")
    SOURCES = (
        Source(
            url="https://raw.githubusercontent.com/nickboucher/imperceptible/main"
            "/results/adversarial-examples.json",
            filename="bad-characters.json",
            licence="MIT",
            note="the authors' released adversarial examples; each row carries the "
            "perturbed `adv_example` beside the original `input`",
        ),
    )

    def _rows_from_nested(self, path: Path, limit: int | None) -> Iterator[tuple[str, str | None]]:
        """The release nests experiment -> budget -> row id -> record.

        Not the flat shape the generic loader expects, and flattening it here
        rather than converting the file keeps the artifact byte-identical to what
        the authors published.
        """
        import json as _json

        blob = _json.loads(path.read_text(encoding="utf-8"))
        seen = 0
        for experiment in blob.values():
            if not isinstance(experiment, dict):
                continue
            for budget in experiment.values():
                if not isinstance(budget, dict):
                    continue
                for row in budget.values():
                    if not isinstance(row, dict):
                        continue
                    text = row.get("adv_example")
                    clean = row.get("input")
                    if not isinstance(text, str) or not text.strip():
                        continue
                    yield text, (clean if isinstance(clean, str) else None)
                    seen += 1
                    if limit is not None and seen >= limit:
                        return

    def rows(self, path: Path, limit: int | None) -> list[tuple[str, str | None]]:
        if path.name == "bad-characters.json":
            return list(self._rows_from_nested(path, limit))
        return list(_rows(path, limit))

    summary = "Boucher et al.'s four imperceptible-perturbation classes, scored for XMR."
    provenance = Provenance(
        origin="Boucher, Shumailov, Anderson & Papernot",
        citation="arXiv:2106.09898v2 — Bad Characters: Imperceptible NLP Attacks",
        url="https://arxiv.org/abs/2106.09898v2",
        version="v2",
        licence="see upstream repository",
        issues=(739, 740, 741, 732),
        finding=(
            "#739/#740: XMR was 0/10 on all fourteen surfaces for the reordering and "
            "deletion classes while detection was 10/10. The gap is recovery, not "
            "blindness — disarm keeps logical order and the attack is about display "
            "order."
        ),
        notes=(
            "Detection and recovery are scored separately because this corpus is "
            "where they diverge hardest."
        ),
    )


class SpecialCharAttack(AttackCorpusSuite):
    name = "special-char-attack"
    env_var = "DISARM_META_SPECIAL_CHAR"
    filenames = ("special_char_attack.jsonl", "special_char_attack.csv")
    summary = "591 variants across 15 structural-perturbation subtypes."
    provenance = Provenance(
        origin="arXiv:2508.14070v1",
        citation="arXiv:2508.14070v1 §3 Structural perturbations",
        url="https://arxiv.org/abs/2508.14070",
        version="v1",
        licence="see upstream release",
        issues=(720, 722, 724, 726, 729, 732),
        finding=(
            "#726: `!` is both a WRAP character and a leet substitute, so `!gn0r3` "
            "screened clean while `1gn0r3` was caught. #724: one enclosing mark per "
            "base character sat below every threshold."
        ),
        notes="Word fragmentation, leet substitution, enclosing marks, encoding subtypes.",
    )


class GCGSuffixes(AttackCorpusSuite):
    name = "gcg-suffixes"
    availability = Availability.CREDENTIALED
    env_var = "DISARM_META_GCG"
    filenames = ("gcg_evaluated_data.jsonl", "gcg-evaluated-data.csv")
    summary = "1,683 released GCG jailbreak suffixes: detection vs incidental rewriting."
    provenance = Provenance(
        origin="Ben-Tov, Geva & Sharif",
        citation="arXiv:2506.12880v2 / HuggingFace MatanBT/gcg-evaluated-data",
        url="https://arxiv.org/abs/2506.12880v2",
        version="v2",
        licence="MIT (upstream dataset)",
        issues=(743, 742),
        finding=(
            "#743: 0 of 1,683 detected, 0% non-ASCII, and 54.1% rewritten anyway. "
            "50% of the Llama-3.1 split carried a literal delimiter spelling, all "
            "broken by the pipe fold; 2.6% of the Gemma split carried one, all "
            "surviving intact."
        ),
        notes=(
            "The useful result here is a negative: the suffixes are valid ASCII, so "
            "detection is structurally zero and any rewriting is incidental."
        ),
    )


class GAversary(AttackCorpusSuite):
    name = "gaversary-word-substitution"
    env_var = "DISARM_META_GAVERSARY"
    filenames = ("gaversary_tables_5_9.tsv", "gaversary.jsonl")
    summary = "The 20 published word-substitution adversarial texts (Tables 5-9)."
    provenance = Provenance(
        origin="Singh, Brownlee & Elawady",
        citation="arXiv:2606.27215v1 — GAversary",
        url="https://arxiv.org/abs/2606.27215",
        version="v1",
        licence="see paper",
        issues=(754, 757, 758),
        finding=(
            "#758: 0/15 recovered and 0 findings on 20/20 — the family is named "
            "nowhere, on a page whose own evidence base is SST-2 / AG-News / BERT."
        ),
        notes=(
            "The family disarm is structurally blind to: substitution happens at "
            "the word level in valid ASCII, so no character-level signal exists."
        ),
    )


class SmishingRobustness(AttackCorpusSuite):
    name = "smishing-robustness"
    env_var = "DISARM_META_SMISHING"
    filenames = ("smishing_attacks.tsv", "smishing.jsonl")
    summary = "Three smishing attack classes from the adversarial-robustness study."
    provenance = Provenance(
        origin="Chiuseni, Bahizire, Hama & Ndibwile",
        citation="arXiv:2608.12889v1 — Adversarial Robustness in SMS phishing detection",
        url="https://arxiv.org/abs/2608.12889",
        version="v1",
        licence="see paper",
        issues=(750, 752, 755),
        finding=(
            "#752: one leet substitute inside a segmented word defeated both anomaly "
            "branches — `p.a.s.s.w.0.r.d` screened clean while each half was caught "
            "on its own."
        ),
        notes="Segmentation by visible separators, leet substitution, and their combination.",
    )


class XOXOCodeContext(AttackCorpusSuite):
    name = "xoxo-code-context"
    env_var = "DISARM_META_XOXO"
    filenames = ("xoxo_snippets.jsonl", "xoxo.tsv")
    summary = "Source code as untrusted LLM context — does a surface return source code?"
    provenance = Provenance(
        origin="Štorek et al.",
        citation="arXiv:2503.14281v4 — XOXO",
        url="https://arxiv.org/abs/2503.14281",
        version="v4",
        licence="see paper",
        issues=(744, 745, 746),
        finding=(
            "#745: over a 465-file tree, all eleven presets and both LLM profiles "
            "collapsed 465/465 files to one line. normalize_confusables kept the "
            "lines and still broke 287/287 Python files on the three ASCII TR39 rows."
        ),
        notes=(
            "Scored on line structure as much as on content: collapse_whitespace is "
            "the last step of every preset, and #433 decided that deliberately."
        ),
    )


class ESTIAgentState(AttackCorpusSuite):
    name = "esti-agent-state"
    env_var = "DISARM_META_ESTI"
    filenames = ("esti_state_records.jsonl", "esti.tsv")
    summary = "Serialized agent state / tool-result records as a third channel."
    provenance = Provenance(
        origin="Liu et al.",
        citation="arXiv:2608.16806v2 — ESTI",
        url="https://arxiv.org/abs/2608.16806v2",
        version="v2",
        licence="see paper",
        issues=(748,),
        finding=(
            "#748: 13/13 surfaces collapsed a 3-record block to one line, 6/13 broke "
            "the JSON on the U+0022 row, and 7/13 destroyed a pipe-delimited "
            "objectId. strip_log_injection, the record-boundary primitive, is in "
            "0 of 7 profiles."
        ),
        notes=(
            "Record shape S_t = <O_t, R_t, Q_t, F_t> with real iTHOR objectIds "
            "(<Type>|<x>|<y>|<z>). Every failure is silent: the output stays "
            "well-formed text."
        ),
    )


class BackdoorTrigger(AttackCorpusSuite):
    name = "backdoor-trigger-reach"
    env_var = "DISARM_META_BACKDOOR"
    filenames = ("backdoor_triggers.tsv", "backdoor.jsonl")
    summary = "Model-as-sink: how many Unicode spellings a fold merges onto one trigger."
    provenance = Provenance(
        origin="Wei et al.",
        citation="arXiv:2608.24354v1 — Not All Tokens Are Equal",
        url="https://arxiv.org/abs/2608.24354",
        version="v1",
        licence="see paper",
        issues=(753,),
        finding=(
            "#753: 36,838 single-edit spellings of one trigger folded onto it, and "
            "74.9% of them were silent. THREAT_MODEL had no entry for a model as "
            "the sink."
        ),
        notes=(
            "A many-to-one fold widens a poisoned trigger's reach rather than "
            "narrowing it — the one place where normalizing is the attack surface."
        ),
    )


class CanonicalizationObligation(AttackCorpusSuite):
    name = "canonicalization-obligation"
    env_var = "DISARM_META_CANON_OBLIGATION"
    filenames = ("canonicalization_cases.tsv", "canon_obligation.jsonl")
    summary = "Composition canonicity vs value canonicity (§7.3) over composite objects."
    provenance = Provenance(
        origin="arXiv:2608.06508v1",
        citation="arXiv:2608.06508v1 §7.3",
        url="https://arxiv.org/abs/2608.06508",
        version="v1",
        licence="see paper",
        issues=(725, 733, 787),
        finding=(
            "#787: four surfaces gave a different key for field-wise-then-joined "
            'than for joined-then-normalized. #725: five surfaces rewrite `|`, `"` '
            "and backtick, documented only in a Rust comment."
        ),
        notes=(
            "A composite is canonical only if the composition is uniquely "
            "decomposable AND each value is canonical. disarm gets the second."
        ),
    )


class NonStandardUnicodeSets(AttackCorpusSuite):
    name = "nonstandard-unicode-sets"
    env_var = "DISARM_META_NONSTANDARD"
    filenames = ("nonstandard_unicode_sets.tsv", "nonstandard_unicode_sets.jsonl")
    summary = "38 non-standard character sets scored against 15 models by the paper itself."
    provenance = Provenance(
        origin="Daniel & Pal",
        citation="arXiv:2405.14490v1 — Impact of Non-Standard Unicode Characters on "
        "Security and Comprehension in LLMs",
        url="https://arxiv.org/abs/2405.14490",
        version="v1",
        licence="see paper",
        issues=(815, 816, 732),
        finding=(
            "#816: 30/37 sets recovered by at least one surface but only 7/37 "
            "flagged by has_anomalies, and 5 neither recovered nor detected. "
            "#815: 385 code points that read as Latin letters have no path to "
            "ASCII, so `ᴄᴀɴ ʏᴏᴜ` half-folds to `cᴀn you` and screens clean."
        ),
        notes=(
            "The one corpus here whose paper prescribes disarm's job without "
            "knowing disarm exists: §10 recommends mapping non-standard characters "
            "to their standard counterparts for conversational LLMs. Every row "
            "carries a measured attack-effectiveness prior (models compromised out "
            "of 15) rather than a uniform weight per subtype."
        ),
    )


SUITES = [
    BadCharacters(),
    NonStandardUnicodeSets(),
    SpecialCharAttack(),
    GCGSuffixes(),
    GAversary(),
    SmishingRobustness(),
    XOXOCodeContext(),
    ESTIAgentState(),
    BackdoorTrigger(),
    CanonicalizationObligation(),
]
