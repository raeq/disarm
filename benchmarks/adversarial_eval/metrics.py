"""Metrics for the adversarial-text robustness harness (#49).

Where clean ground truth exists (BitAbuse), report **XMR / exact recovery** and
**word-level recovery**. For unlabeled corpora, report **canonicalization stats**
(perturbation-bearing rows, non-ASCII codepoints folded) and **miss-mining**: the
non-ASCII codepoints that survive ``strip_obfuscation``, split into

* **principled** — present as a source in UTS#39 ``confusables.txt`` (addressable;
  a coverage gap translit could close, to be verified/upstreamed per #40), and
* **novel** — not in UTS#39 (out of scope, e.g. Viper-synthetic perturbations).

The split uses the *full* UTS#39 source set (``data/confusables.txt``), not just
translit's bundled table, so a char already in the standard but not yet mapped is
correctly counted as an addressable miss rather than novel.

The scan is **parallelized with multiprocessing**: records are streamed into
chunks, each chunk is canonicalized + scored in a worker process, and the partial
aggregates are reduced. UTS#39 sources are loaded once per worker via the pool
initializer rather than pickled per chunk.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from multiprocessing import Pool
from pathlib import Path

from translit import strip_obfuscation

from .corpora import Record

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFUSABLES = _REPO_ROOT / "data" / "confusables.txt"


def load_uts39_sources(path: Path | str = DEFAULT_CONFUSABLES) -> set[int]:
    """Return the set of source codepoints listed in UTS#39 ``confusables.txt``.

    Lines look like ``SOURCE ; TARGET ; TYPE # comment``; the source is a single
    codepoint. Comment/blank lines are skipped.
    """
    sources: set[int] = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        head = line.split(";", 1)[0].strip()
        try:
            sources.add(int(head, 16))
        except ValueError:
            continue
    return sources


def _nonascii(text: str) -> list[str]:
    return [ch for ch in text if ord(ch) > 0x7F]


@dataclass
class _Partial:
    """Reducible per-chunk aggregates."""

    n_rows: int = 0
    rows_with_nonascii: int = 0
    nonascii_before: int = 0
    nonascii_after: int = 0
    labeled_rows: int = 0
    xmr_hits: int = 0
    line_exact_hits: int = 0
    word_recall_sum: float = 0.0
    missed_principled: Counter[int] = field(default_factory=Counter)
    missed_novel: Counter[int] = field(default_factory=Counter)

    def merge(self, other: _Partial) -> None:
        self.n_rows += other.n_rows
        self.rows_with_nonascii += other.rows_with_nonascii
        self.nonascii_before += other.nonascii_before
        self.nonascii_after += other.nonascii_after
        self.labeled_rows += other.labeled_rows
        self.xmr_hits += other.xmr_hits
        self.line_exact_hits += other.line_exact_hits
        self.word_recall_sum += other.word_recall_sum
        self.missed_principled.update(other.missed_principled)
        self.missed_novel.update(other.missed_novel)


@dataclass
class EvalResult:
    corpus: str
    labeled: bool
    n_rows: int = 0
    rows_with_nonascii: int = 0
    nonascii_before: int = 0
    nonascii_after: int = 0
    xmr: float | None = None
    word_recovery: float | None = None
    line_exact: float | None = None
    missed_principled: Counter[int] = field(default_factory=Counter)
    missed_novel: Counter[int] = field(default_factory=Counter)

    @property
    def perturbation_bearing_rate(self) -> float:
        return self.rows_with_nonascii / self.n_rows if self.n_rows else 0.0

    @property
    def folded_fraction(self) -> float:
        if not self.nonascii_before:
            return 0.0
        return 1.0 - self.nonascii_after / self.nonascii_before


def _word_recovery(recovered: str, clean: str) -> float:
    """Fraction of clean words present (multiset overlap) in the recovered text."""
    clean_words = clean.split()
    if not clean_words:
        return 1.0 if not recovered.split() else 0.0
    recovered_counts = Counter(recovered.split())
    hits = 0
    for word, need in Counter(clean_words).items():
        hits += min(need, recovered_counts.get(word, 0))
    return hits / len(clean_words)


# --- multiprocessing worker -------------------------------------------------

_WORKER_SOURCES: set[int] = set()


def _init_worker(confusables_path: str) -> None:
    global _WORKER_SOURCES
    _WORKER_SOURCES = load_uts39_sources(confusables_path)


def _score_chunk(chunk: list[tuple[str, str | None]]) -> _Partial:
    sources = _WORKER_SOURCES
    p = _Partial()
    for text, clean in chunk:
        p.n_rows += 1
        cleaned = strip_obfuscation(text)
        before = _nonascii(text)
        after = _nonascii(cleaned)
        if before:
            p.rows_with_nonascii += 1
        p.nonascii_before += len(before)
        p.nonascii_after += len(after)
        # Count every occurrence (not distinct-per-row) so the miss totals
        # reconcile with nonascii_after and "occurrences" in the report is honest.
        for ch, count in Counter(after).items():
            cp = ord(ch)
            if cp in sources:
                p.missed_principled[cp] += count
            else:
                p.missed_novel[cp] += count
        if clean is not None:
            p.labeled_rows += 1
            clean_canon = strip_obfuscation(clean)
            if cleaned == clean_canon:
                p.xmr_hits += 1
            if cleaned == clean:
                p.line_exact_hits += 1
            p.word_recall_sum += _word_recovery(cleaned, clean_canon)
    return p


def _chunked(records: Iterable[Record], size: int) -> Iterator[list[tuple[str, str | None]]]:
    batch: list[tuple[str, str | None]] = []
    for rec in records:
        batch.append((rec.text, rec.clean))
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def evaluate(
    records: Iterable[Record],
    corpus: str,
    labeled: bool,
    uts39_sources: set[int] | None = None,  # retained for API compatibility
    confusables_path: Path | str = DEFAULT_CONFUSABLES,
    processes: int | None = None,
    chunk_size: int = 4000,
) -> EvalResult:
    """Scan ``records`` through ``strip_obfuscation`` and accumulate metrics.

    The scan runs across ``processes`` worker processes (default: all CPUs). Pass
    ``processes=1`` to run inline (useful for tests / tiny inputs).
    """
    if processes is None:
        processes = os.cpu_count() or 1

    total = _Partial()
    chunks = _chunked(records, chunk_size)
    if processes <= 1:
        _init_worker(str(confusables_path))
        for chunk in chunks:
            total.merge(_score_chunk(chunk))
    else:
        with Pool(
            processes=processes,
            initializer=_init_worker,
            initargs=(str(confusables_path),),
        ) as pool:
            for partial in pool.imap_unordered(_score_chunk, chunks):
                total.merge(partial)

    res = EvalResult(
        corpus=corpus,
        labeled=labeled,
        n_rows=total.n_rows,
        rows_with_nonascii=total.rows_with_nonascii,
        nonascii_before=total.nonascii_before,
        nonascii_after=total.nonascii_after,
        missed_principled=total.missed_principled,
        missed_novel=total.missed_novel,
    )
    if labeled and total.labeled_rows:
        res.xmr = total.xmr_hits / total.labeled_rows
        res.line_exact = total.line_exact_hits / total.labeled_rows
        res.word_recovery = total.word_recall_sum / total.labeled_rows
    return res
