"""Suites wrapping the public spam / phishing / prose corpora.

Four of these already have adapters in :mod:`benchmarks.adversarial_eval`; this
module reuses them rather than reimplementing the loaders, so the corpus
definitions stay in one place and the #49 harness remains the thing that owns
them. The meta-harness adds the registry entry, the provenance record and the
consolidated report.

The fifth, a benign pre-1923 Gutenberg sample, is the false-positive axis: every
other corpus here can only record a hit, so a harness built from them alone
cannot see over-reach.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..base import CACHE, SuiteBase, add, artifact, record
from ..protocol import Availability, Family, Outcome, Provenance
from ..subjects import Role


def _altered(fn: Callable[[str], str], text: str) -> bool:
    """Did this surface change the text? A refusal counts as "no"."""
    try:
        return fn(text) != text
    except Exception:  # noqa: BLE001
        return False


class _RemovalSplitMixin:
    """Classify *how* each non-ASCII code point stopped being non-ASCII."""

    def _add_removal_split(self, outcome: Outcome, universe: set[int]) -> None:
        """``universe`` is every distinct non-ASCII code point the corpus holds.

        Not the survivors: a survivor never folds, which is the whole
        distinction being drawn.
        """
        from .. import damage

        subject = getattr(self, "subject", None)
        surfaces = subject.role(Role.SANITIZER) if subject is not None else {}
        if not surfaces or not universe:
            return
        fn = next(iter(surfaces.values()))
        counts = {"folded": 0, "deleted": 0, "named": 0, "survives": 0}
        for cp in sorted(universe):
            counts[damage.classify_removal(fn, chr(cp))] += 1
        total = len(universe)
        add(
            outcome,
            "folded_to_ascii",
            counts["folded"],
            of=total,
            higher_is_better=True,
            detail="replaced by one or two ASCII characters — an actual fold",
        )
        add(
            outcome,
            "deleted_outright",
            counts["deleted"],
            of=total,
            detail="removed with nothing in its place",
        )
        add(
            outcome,
            "named_as_words",
            counts["named"],
            of=total,
            higher_is_better=False,
            detail="replaced by a run of ASCII words — `—` to `em dash` (#757). "
            "Counted as coverage by the undifferentiated rate",
        )


class _AdversarialEvalSuite(_RemovalSplitMixin, SuiteBase):
    """Delegate to a ``benchmarks.adversarial_eval`` corpus adapter."""

    family = Family.DATASET
    corpus: str = ""
    default_limit: int | None = None
    #: Optional third-party packages the adapter imports. A missing one is a
    #: skip with an install hint, never an error — the corpus is not the problem.
    requires_modules: tuple[str, ...] = ()

    def _adapter(self) -> Any:
        from benchmarks.adversarial_eval.corpora import ADAPTERS

        return ADAPTERS[self.corpus]

    def available(self) -> tuple[bool, str]:
        try:
            adapter = self._adapter()
        except Exception as exc:  # noqa: BLE001
            return False, f"adapter unavailable: {exc}"
        if adapter.requires_credentials and not self._credentials_present():
            hint = f" Set ${self.env_var}." if self.env_var else ""
            return False, f"{self.corpus} needs credentials or manual data placement.{hint}"
        for module in self.requires_modules:
            try:
                __import__(module)
            except ImportError:
                return False, f"{self.corpus} needs the '{module}' package: pip install {module}"
        return True, ""

    def _credentials_present(self) -> bool:
        import os

        if self.env_var and os.environ.get(self.env_var):
            return True
        return Path(Path.home() / ".kaggle" / "kaggle.json").exists()

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        from benchmarks.adversarial_eval.metrics import evaluate

        adapter = self._adapter()
        effective = limit if limit is not None else self.default_limit
        # One extra pass to collect the distinct non-ASCII code points the corpus
        # actually contains. The removal split needs those, not the survivors —
        # a survivor never folds, which is the distinction being drawn.
        universe = {
            ord(c) for rec in adapter.load(limit=effective) for c in rec.text if ord(c) > 0x7F
        }
        # Score the DECLARED sanitizer, not the module's hardcoded
        # `strip_obfuscation` (#759). Without this the corpus metric and the
        # removal split below measure different surfaces, which is the same
        # asymmetry the coverage and cost axes had.
        # #903 landed the same capability on main with a better signature: a
        # dotted path rather than the callable this branch first passed, because
        # a callable does not survive being handed to a worker process. The
        # declared role gives the attribute name; the module comes from the
        # resolved surface, so this keeps working if a surface moves.
        declared = self.subject.role(Role.SANITIZER) if self.subject else {}
        name, fn = next(iter(declared.items()), (None, None))
        surface = f"{fn.__module__.split('.')[0]}.{name}" if fn is not None else None
        res = evaluate(
            adapter.load(limit=effective),
            corpus=adapter.name,
            labeled=adapter.labeled,
            processes=1 if (effective or 0) and effective <= 2000 else None,
            **({"transform": surface} if surface else {}),
        )
        outcome.population = res.n_rows
        add(outcome, "rows", res.n_rows, unit="rows")
        add(outcome, "perturbation_bearing", res.rows_with_nonascii, of=res.n_rows)
        # Deliberately NOT scored. "(before - after) / before" counts any way a
        # non-ASCII code point stops being non-ASCII, so folding, deleting and
        # *naming* all read the same. disarm 0.14.1 turned `—` into the words
        # "em dash" and this metric called it coverage; when #803 stopped that,
        # the rate fell 81.9% -> 78.8% and the benchmark reported the fix as a
        # regression. The split below is the scored form.
        add(
            outcome,
            "nonascii_removed",
            res.nonascii_before - res.nonascii_after,
            of=res.nonascii_before,
            detail="any way a non-ASCII code point stopped being one — folded, "
            "deleted or named. A census: it cannot tell the three apart",
        )
        self._add_removal_split(outcome, universe)
        add(
            outcome,
            "misses_principled",
            len(res.missed_principled),
            higher_is_better=False,
            detail="distinct survivors that ARE in UTS #39 — addressable, route via #40",
        )
        add(
            outcome,
            "misses_novel",
            len(res.missed_novel),
            detail="distinct survivors not in UTS #39 — out of scope",
        )
        if res.labeled:
            add(outcome, "xmr", res.xmr or 0.0, of=1.0, unit="ratio", higher_is_better=True)
            add(
                outcome,
                "line_exact",
                res.line_exact or 0.0,
                of=1.0,
                unit="ratio",
                higher_is_better=True,
            )
            add(
                outcome,
                "word_recovery",
                res.word_recovery or 0.0,
                of=1.0,
                unit="ratio",
                higher_is_better=True,
            )


class BitAbuse(_AdversarialEvalSuite):
    name = "bitabuse"
    corpus = "bitabuse"
    availability = Availability.NETWORK
    default_limit = 20000
    requires_modules = ("datasets",)
    summary = "Labelled perturbed→clean pairs — the only large recovery-scored corpus."
    provenance = Provenance(
        origin="AutoML / HuggingFace",
        citation="AutoML/bitabuse",
        url="https://huggingface.co/datasets/AutoML/bitabuse",
        version="325,580 rows (full corpus)",
        licence="see dataset card",
        issues=(49, 40),
        notes="Refreshed as a manual pre-release step; reports/bitabuse.md is canonical.",
    )


class YouTubeSpam(_AdversarialEvalSuite):
    name = "youtube-spam"
    corpus = "youtube-spam"
    availability = Availability.NETWORK
    summary = "UCI 380 comment spam — canonicalization stats and miss-mining, unlabelled."
    provenance = Provenance(
        origin="Alberto, Lochter & Almeida",
        citation="UCI Machine Learning Repository dataset 380",
        url="https://archive.ics.uci.edu/dataset/380/youtube+spam+collection",
        version="UCI archive release",
        licence="CC BY 4.0",
        issues=(49,),
    )


class TREC2007(_AdversarialEvalSuite):
    name = "trec-2007"
    corpus = "trec-2007"
    availability = Availability.CREDENTIALED
    env_var = "KAGGLE_KEY"
    requires_modules = ("kaggle",)
    summary = "TREC-2007 public spam corpus (Kaggle API)."
    provenance = Provenance(
        origin="TREC / imdeepmind",
        citation="imdeepmind/preprocessed-trec-2007-public-corpus-dataset",
        url="https://www.kaggle.com/datasets/imdeepmind/preprocessed-trec-2007-public-corpus-dataset",
        version="Kaggle release",
        licence="see dataset page",
        issues=(49,),
    )


class MeAJOR(_AdversarialEvalSuite):
    name = "meajor"
    corpus = "meajor"
    availability = Availability.MANUAL
    env_var = "ADVERSARIAL_EVAL_MEAJOR"
    summary = "MeAJOR phishing-email corpus."
    provenance = Provenance(
        origin="MeAJOR authors",
        citation="arXiv:2507.17978",
        url="https://arxiv.org/abs/2507.17978",
        version="paper release",
        licence="see paper",
        issues=(49,),
    )


class GutenbergBenign(SuiteBase):
    name = "gutenberg-benign"
    family = Family.DATASET
    availability = Availability.MANUAL
    MULTI_SUBJECT = True
    env_var = "DISARM_META_GUTENBERG"
    summary = "Benign pre-1923 prose: the false-positive axis every attack corpus lacks."
    provenance = Provenance(
        origin="Project Gutenberg",
        citation="Project Gutenberg (pre-1923, public domain)",
        url="https://www.gutenberg.org/",
        version="operator-selected passage sample",
        licence="public domain in the US",
        issues=(842, 754, 761, 788, 759),
        finding=(
            "#842: is_zalgo flagged 142 ordinary Burmese place names and strip_zalgo "
            "deleted a tone mark from each. #761: kana lost the dakuten and Cyrillic "
            "lost й and ё, neither named in the destructive-script warning."
        ),
        notes=(
            "A corpus that can only record a hit cannot record over-reach, so every "
            "other dataset here is blind to false positives by construction. This is "
            "the clean-text cost axis #759 says adversarial_eval lacks. One passage "
            "per line."
        ),
    )

    def locate(self) -> Path | None:
        return artifact(CACHE / "gutenberg_passages.txt", env=self.env_var)

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        path = self.locate()
        assert path is not None
        passages = [
            ln.strip()
            for ln in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if ln.strip()
        ]
        if limit is not None:
            passages = passages[:limit]
        outcome.population = len(passages)
        if not passages:
            add(outcome, "passages", 0)
            return

        det = self.detect()
        surface_map = self.transforms()
        record(
            outcome,
            domain=f"{len(passages)} public-domain prose passages",
            predicates=[*sorted(surface_map), *sorted(det)],
            cost_metric="a benign passage a detector flags, or a surface rewrites",
        )
        false_positives = {name: 0 for name in det}
        altered = 0
        for text in passages:
            for name, fn in det.items():
                try:
                    if fn(text):
                        false_positives[name] += 1
                except Exception:  # noqa: BLE001
                    continue
            if any(_altered(fn, text) for fn in surface_map.values()):
                altered += 1
        n = len(passages)
        add(outcome, "passages", n, unit="passages")
        add(
            outcome,
            "altered_by_any_surface",
            altered,
            of=n,
            higher_is_better=False,
            detail="benign prose the subject rewrites",
        )
        for name, hits in false_positives.items():
            add(
                outcome,
                f"fp_{name}",
                hits,
                of=n,
                higher_is_better=False,
                detail="benign prose flagged by a detector",
            )


SUITES = [BitAbuse(), YouTubeSpam(), TREC2007(), MeAJOR(), GutenbergBenign()]
