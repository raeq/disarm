"""Third-party labelled benchmarks and rival implementations.

The strongest external evidence available: somebody else built the benchmark,
labelled the rows, and published both. A labelled benchmark is the only place in
this harness where precision and recall mean anything, because it is the only
place where a *false positive* is defined by someone other than disarm.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import NamedTuple

from ..base import CACHE, DATA, SuiteBase, add, artifact, detectors, record, thin
from ..fetch import Source
from ..protocol import Availability, Family, Outcome, Provenance
from ..subjects import Capability, Job, Role
from .practitioner import tree_digest


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

        def _protect(row: dict[str, object]) -> list[str]:
            raw = row.get("protect") or []
            if isinstance(raw, str):
                return [raw]
            if isinstance(raw, (list, tuple, set, frozenset)):
                return [str(x) for x in raw]
            return []

        def collides(builder: Callable[[str], str], row: dict[str, object]) -> bool:
            ident = str(row.get("identifier", ""))
            protect = _protect(row)
            key = builder(ident)
            return any(builder(p) == key and p != ident for p in protect)

        policies: dict[str, Callable[[dict[str, object]], bool]] = {
            "has_anomalies": lambda r: disarm.has_anomalies(str(r.get("identifier", ""))),
            "is_confusable": lambda r: bool(disarm.is_confusable(str(r.get("identifier", "")))),
            "is_mixed_script": lambda r: disarm.is_mixed_script(str(r.get("identifier", ""))),
            "catalog_key_collision": lambda r: collides(disarm.catalog_key, r),
            "canonicalize_strict_collision": lambda r: collides(disarm.canonicalize_strict, r),
            # Both landed after this suite was written, and both are surfaces a
            # registry would actually reach for (#650, #894). `skeleton_key` under
            # `tr39` is the spoof key; `nearest_match` measures the ASCII-edit class
            # no confusable table should fold, which is where the corpus's residual
            # rows live. Scoring them moves the *run*, never the `finding` above:
            # that field records what the 0.15.0 cycle measured, and the distance
            # between it and today is the report's most useful column.
            "skeleton_key_collision": lambda r: collides(disarm.skeleton_key, r),
            "skeleton_key_tr39_collision": lambda r: collides(
                lambda s: disarm.skeleton_key(s, digit_policy="tr39"), r
            ),
            "nearest_match_1": lambda r: (
                disarm.nearest_match(str(r.get("identifier", "")), _protect(r), max_distance=1)
                is not None
            ),
        }
        # The composition #736 measures: the union is the only policy that reaches
        # the published headline, and it is a union no page names.
        policies["union_confusable_or_collision"] = lambda r: (
            bool(disarm.is_confusable(str(r.get("identifier", ""))))
            or collides(disarm.catalog_key, r)
            or collides(disarm.canonicalize_strict, r)
        )
        # The two-call composition, scored beside it: the fold sees the Unicode class
        # and the edit distance sees the ASCII class, and neither sees the other's.
        policies["union_confusable_or_nearest_match"] = lambda r: (
            bool(disarm.is_confusable(str(r.get("identifier", ""))))
            or disarm.nearest_match(str(r.get("identifier", "")), _protect(r), max_distance=1)
            is not None
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
            licence="CC-BY-4.0 (datasets), MIT (code)",
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


_UNTRACE_COMMIT = "5cc75c3af73e53dda14eee6918e91f956c73ac61"

#: A run with one of these prints what untrace prints by default. `--fail` moves the
#: exit code and leaves the report alone.
_UNTRACE_PLAIN_ARGS = frozenset({"", ".", "--fail ."})
#: The last line of a text report, which holds how many files the run scanned.
_UNTRACE_TAIL = re.compile(r"(?:found: .*? of|clean:) (\d+) file")
#: What each line of a report gives its file, the strongest first. A file takes the first
#: it earned. A line about metadata gives nothing, so a file named for metadata alone is
#: clean: `legitimate-authors` is one.
_UNTRACE_MARKS = (
    ("payload", re.compile(r"\s*!! hidden payload ")),
    ("hidden", re.compile(r"\s*\d+:\d+\s+detected\s.*\(hidden\)\s*$")),
    ("mixed_script", re.compile(r"\s*\d+:\d+\s+mixed-script\s")),
    ("typographic", re.compile(r"\s*\d+:\d+\s+detected\s.*\(typographic\)\s*$")),
)
#: Each class, and whether `has_anomalies` firing on it is better. Typography is not a
#: hidden character and not clean either, so it counts and has no direction.
_UNTRACE_DIRECTIONS: dict[str, bool | None] = {
    "payload": True,
    "hidden": True,
    "mixed_script": True,
    "typographic": None,
    "clean": False,
}


class _UntraceFile(NamedTuple):
    #: `case/path`. A file name is the only part of the corpus a report may print.
    name: str
    #: A key of `_UNTRACE_DIRECTIONS`, or None where the run gave no verdict.
    label: str | None
    text: str


class UntraceTechniques(SuiteBase):
    name = "untrace-techniques"
    family = Family.COMPARATOR
    availability = Availability.MANUAL
    env_var = "DISARM_META_UNTRACE"
    SOURCES = (
        Source(
            url=f"https://codeload.github.com/juriku/untrace/tar.gz/{_UNTRACE_COMMIT}",
            filename="untrace",
            licence="MIT",
            kind="tar.gz",
            member=f"untrace-{_UNTRACE_COMMIT}/testdata",
            note="the rival's own test inputs and the reports it expects for them",
        ),
    )
    #: Of the extracted `testdata`, as `practitioner.tree_digest` computes it.
    TREE_SHA256 = "d417d4610381cd41d82f721909282bdbe91bf93f05dea6a99293ac9f1e4eef9f"
    summary = (
        "A rival detector's expected reports label its test inputs: what does disarm report, "
        "and what does it fire on that the rival calls clean?"
    )
    provenance = Provenance(
        origin="juriku",
        citation="untrace (successor to hidden-characters-detector)",
        url="https://github.com/juriku/untrace",
        version=f"commit {_UNTRACE_COMMIT[:12]}, testdata/cases",
        licence="MIT",
        issues=(700, 701, 702, 703, 704, 705, 706, 1204),
        finding=(
            "#701: disarm strips the three ASCII-smuggling carriers and never says "
            "what a run spells. Presence and decode are different strengths of "
            "evidence — an invisible character can arrive by accident, and a run "
            "that decodes to readable text cannot."
        ),
        notes=(
            "The cases are regression fixtures for untrace's command line, not a list of "
            "techniques, and some are clean by name. So each text file under a case's `in/` "
            "takes its label from the expected report of a run with no flag that changes it. "
            "A file the run may have ignored has no verdict, and it does not count as clean. "
            "`has_anomalies` reports apart from the primitives, since `is_confusable` firing "
            "on a Russian file says nothing about a hidden character. The name stays so "
            "that the row in a baseline still joins."
        ),
    )

    def locate(self) -> Path | None:
        return self.provisioned()

    def available(self) -> tuple[bool, str]:
        ready, reason = super().available()
        if not ready:
            return ready, reason
        root = self.locate()
        assert root is not None
        digest = tree_digest(root)
        if digest != self.TREE_SHA256:
            return False, f"tree digest {digest[:16]} is not the pinned {self.TREE_SHA256[:16]}"
        return True, ""

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        import disarm

        path = self.locate()
        assert path is not None
        cases, left_out, files = _untrace_files(path / "cases")
        by_class = {label: [f for f in files if f.label == label] for label in _UNTRACE_DIRECTIONS}
        by_class = {
            label: [chosen[i] for i in thin(list(range(len(chosen))), limit)]
            for label, chosen in by_class.items()
        }
        scored = [f for chosen in by_class.values() for f in chosen]
        positives = [f for label in ("payload", "hidden", "mixed_script") for f in by_class[label]]
        clean = by_class["clean"]

        def score(fires: Callable[[str], bool]) -> float:
            """True positives less false positives, each as a rate, so firing always earns 0."""
            caught = sum(_safe(fires, f.text) for f in positives) / max(len(positives), 1)
            raised = sum(_safe(fires, f.text) for f in clean) / max(len(clean), 1)
            return round(caught - raised, 4)

        always, never = score(lambda _text: True), score(lambda _text: False)
        if always > never:
            raise ValueError(
                f"{self.name}: a detector that always fires scored {always:g} and one that "
                f"never does {never:g}, so no number from this corpus is reported"
            )

        surfaces = dict(detectors())
        has_anomalies = surfaces.pop("has_anomalies")
        outcome.population = len(scored)
        record(
            outcome,
            domain=f"{len(scored)} text files with a verdict, from {cases - left_out} cases",
            predicates=["has_anomalies", *surfaces],
            commit=_UNTRACE_COMMIT,
        )
        add(outcome, "cases", cases, unit="cases")
        add(
            outcome,
            "cases_left_out",
            left_out,
            of=cases,
            unit="cases",
            detail="no run with a text report and no flag that changes what it reports",
        )
        add(outcome, "files", len(files), unit="files")
        add(
            outcome,
            "files_without_verdict",
            sum(f.label is None for f in files),
            of=len(files),
            unit="files",
            detail="the run may have ignored it by path, config or directive",
        )
        silent: list[str] = []
        raised: list[str] = []
        for label, direction in _UNTRACE_DIRECTIONS.items():
            chosen = by_class[label]
            fired = [f for f in chosen if _safe(has_anomalies, f.text)]
            add(
                outcome,
                f"has_anomalies_on_{label}",
                len(fired),
                of=len(chosen),
                unit="files",
                higher_is_better=direction,
            )
            add(
                outcome,
                f"primitives_on_{label}",
                sum(any(_safe(fn, f.text) for fn in surfaces.values()) for f in chosen),
                of=len(chosen),
                unit="files",
                # Firing on a clean file is wrong for any detector. On any other class a
                # primitive may fire for a reason that has nothing to do with the class.
                higher_is_better=False if label == "clean" else None,
            )
            if direction is True:
                silent += [f.name for f in chosen if f not in fired]
            elif direction is False:
                raised += [f.name for f in fired]
        add(
            outcome,
            "has_anomalies_tpr_minus_fpr",
            score(has_anomalies),
            higher_is_better=True,
            detail="reports caught less false positives, each as a rate",
        )
        add(
            outcome,
            "control_always_fires",
            always,
            detail="the same score for a detector that always fires; must not beat never firing",
        )
        add(
            outcome,
            "altered_by_strip_obfuscation",
            sum(disarm.strip_obfuscation(f.text).split() != f.text.split() for f in scored),
            of=len(scored),
            unit="files",
            detail="beyond whitespace, so the folds of printable ASCII count; rewritten is not reported",
        )
        outcome.extra = {"silent_on": sorted(silent), "false_positives": sorted(raised)}


#: Fixtures untrace ships that are not text probes.
_BINARY_SUFFIXES = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".pdf",
        ".zip",
        ".epub",
        ".docx",
        ".woff",
        ".ico",
        ".webp",
        ".tiff",
        ".tif",
        ".pyc",
    }
)


def _untrace_report(case: Path) -> list[str] | None:
    """The expected report of the first run with no flag that changes it, as lines."""
    for run in (case, *sorted(p for p in (case / "runs").glob("*") if p.is_dir())):
        want = run / "want.txt"
        if not want.is_file():
            continue
        args = run / "args"
        flags = args.read_text(encoding="utf-8", errors="replace").strip() if args.is_file() else ""
        if flags not in _UNTRACE_PLAIN_ARGS:
            continue
        lines = want.read_text(encoding="utf-8", errors="replace").splitlines()
        if lines and _UNTRACE_TAIL.match(lines[-1]):
            return lines
    return None


def _untrace_named(lines: Sequence[str]) -> dict[str, str]:
    """Each file a report names, with the strongest class its lines give it."""
    earned: dict[str, set[str]] = {}
    current: set[str] | None = None
    for line in lines[:-1]:
        if not line.strip():
            continue
        if not line.startswith(" "):
            current = earned.setdefault(line.strip(), set())
        elif current is not None:
            current.update(label for label, mark in _UNTRACE_MARKS if mark.match(line))
    return {
        name: next((label for label, _ in _UNTRACE_MARKS if label in marks), "clean")
        for name, marks in earned.items()
    }


def _untrace_files(cases: Path) -> tuple[int, int, list[_UntraceFile]]:
    """How many cases, how many have no usable report, and every text file of the rest.

    An unnamed file is clean only where the run read it and nothing told the run to look
    away. The report does not say which files it skipped, so a run that scanned fewer
    files than exist leaves every unnamed file without a verdict. A case's config and a
    file's own directive turn reporting off in the same way.
    """
    dirs = sorted(d for d in cases.iterdir() if d.is_dir())
    files: list[_UntraceFile] = []
    left_out = 0
    for case in dirs:
        lines = _untrace_report(case)
        if lines is None:
            left_out += 1
            continue
        named = _untrace_named(lines)
        inputs = case / "in"
        present = sorted(p for p in inputs.rglob("*") if p.is_file())
        tail = _UNTRACE_TAIL.match(lines[-1])
        assert tail is not None
        looked_away = int(tail.group(1)) != len(present) or (inputs / ".untrace.json").is_file()
        for path in present:
            if path.suffix.lower() in _BINARY_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if not text.strip():
                continue
            relative = path.relative_to(inputs).as_posix()
            label = named.get(relative)
            if label is None and not looked_away and "untrace:ignore" not in text:
                label = "clean"
            files.append(_UntraceFile(f"{case.name}/{relative}", label, text))
    return len(dirs), left_out, files


def _safe(fn: Callable[[str], object], text: str) -> bool:
    try:
        return bool(fn(text))
    except Exception:  # noqa: BLE001
        return False


def uts39_rows(path: Path) -> dict[int, tuple[int, ...]]:
    """`confusables.txt` as source -> prototype sequence, from the normative file."""
    rows: dict[int, tuple[int, ...]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("#") or ";" not in line:
            continue
        src, tgt = line.split(";")[:2]
        try:
            rows[int(src.strip(), 16)] = tuple(int(x, 16) for x in tgt.split())
        except ValueError:
            continue
    return rows


def _script_of(cp: int) -> str:
    import unicodedata

    return unicodedata.name(chr(cp), "?").split(" ")[0]


def uts39_prototype_sources(
    codepoints: Sequence[int], rows: Mapping[int, tuple[int, ...]]
) -> list[int]:
    """The code points whose UTS #39 prototype is one code point in another script.

    2,103 rows of `confusables.txt` map a source to a *sequence* — `ᄄ → ᄃᄃ`,
    `ᐎ → ·Δ` — and most of those stay inside one script. They are typesetting
    decompositions, and a detector that fires on a lone Hangul jamo because of
    one is reporting a false positive as coverage (#957, on the other side).
    The security-relevant overlap is the single-code-point, cross-script rows,
    so that is the denominator the directed measurement uses.
    """
    return [
        cp
        for cp in codepoints
        if cp in rows and len(rows[cp]) == 1 and _script_of(rows[cp][0]) != _script_of(cp)
    ]


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
            "characters.\n\n"
            "What is directed, and what is not (#977). `flagged_by_a_detector` "
            "over the whole set is a census: 7,277 of the 7,402 candidates are "
            "not UTS #39 sources at all — Hangul syllables that resemble other "
            "Hangul syllables, box-drawing, dominoes — and of the 586 that are, "
            "547 have a multi-code-point prototype in their own script. A key "
            "that rewarded flagging those crowned a detector for reporting a "
            "lone Hangul jamo. The one directed measurement is "
            "`uts39_prototype_detected`: the candidates whose UTS #39 prototype "
            "is a single code point in another script, read from the normative "
            "`confusables.txt` and never from a disarm table, and how many of "
            "them the subject's detectors flag. Its detail names the misses, "
            "which is the disagreement this suite was registered to surface."
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
        table = artifact(DATA / "confusables.txt", env="DISARM_META_CONFUSABLES")
        rows = uts39_rows(table) if table is not None else {}
        sources = [cp for cp in scored if cp in rows]
        prototypes = uts39_prototype_sources(scored, rows)
        if det:
            flagged = sum(1 for cp in scored if any(_safe(fn, chr(cp)) for fn in det.values()))
            add(
                outcome,
                "flagged_by_a_detector",
                flagged,
                of=len(scored),
                detail="a census: the subject considers this candidate suspicious, and "
                "a weak label cannot say whether it should (#977)",
            )
        if rows:
            add(
                outcome,
                "uts39_sources",
                len(sources),
                of=len(scored),
                detail="candidates that are UTS #39 confusable sources, any row",
            )
            add(
                outcome,
                "uts39_prototype_sources",
                len(prototypes),
                of=len(sources),
                detail="sources whose prototype is one code point in another script — "
                "the security-relevant overlap",
            )
            if det:
                hit = [cp for cp in prototypes if any(_safe(fn, chr(cp)) for fn in det.values())]
                hit_set = set(hit)
                missed = [cp for cp in prototypes if cp not in hit_set]
                names = ", ".join(
                    f"U+{cp:04X} {unicodedata.name(chr(cp), '?')} → U+{rows[cp][0]:04X}"
                    for cp in missed[:40]
                )
                add(
                    outcome,
                    "uts39_prototype_detected",
                    len(hit),
                    of=len(prototypes),
                    higher_is_better=True,
                    detail=("misses: " + names) if missed else "every prototype source is flagged",
                )
        else:
            outcome.extra = {
                **dict(outcome.extra),
                "uts39": "confusables.txt not found; set $DISARM_META_CONFUSABLES",
            }
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
