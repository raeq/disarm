"""Types every meta-benchmark suite speaks.

The meta-harness runs *externally produced* benchmarks. It owns the runner, the
selection, the provenance record and the report; it owns **no vectors**. Every
suite in the registry names an artifact somebody else published — an academic
corpus, a public dataset, a normative Unicode/IETF/ICANN table, a CVE, or a
released model artifact — and scores disarm against it without editing it.

That boundary is machine-checkable rather than aspirational: :class:`Provenance`
carries ``external``, and :func:`Suite.run` results are tagged with it, so a
report can never quietly mix a self-referential census into an external score.
See ``benchmarks/adversarial_eval/README.md`` for the guardrail this inherits
(#39/#40): corpora are measuring instruments, never optimization targets.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


class Family(str, enum.Enum):
    """Which kind of external artifact a suite is anchored to."""

    ACADEMIC = "academic"  # a corpus released with a paper
    DATASET = "dataset"  # a public spam/phishing/prose dataset
    NORMATIVE = "normative"  # UTS/UAX/UCD/RFC/ICANN/CLDR table
    CVE = "cve"  # a published vulnerability's vector
    MODEL_ARTIFACT = "model"  # a released tokenizer / chat template
    COMPARATOR = "comparator"  # a third-party labelled benchmark or rival tool
    INTROSPECTIVE = "introspective"  # sweeps disarm's own tables — NOT external


class Availability(str, enum.Enum):
    """How the suite's external artifact reaches the machine."""

    VENDORED = "vendored"  # already in the repo (data/, tests/fixtures/)
    DERIVED = "derived"  # computed from the installed Python/Unicode
    NETWORK = "network"  # public download, no credentials
    CREDENTIALED = "credentialed"  # needs a Kaggle / HF token
    MANUAL = "manual"  # operator must place the file


class Status(str, enum.Enum):
    OK = "ok"
    SKIPPED = "skipped"  # artifact absent — never a silent pass
    ERROR = "error"


@dataclass(frozen=True)
class Provenance:
    """Where a benchmark came from, pinned hard enough to cite.

    ``external`` is the bias boundary. It is ``False`` only for the
    introspective tier, whose numbers are excluded from every headline figure.
    """

    origin: str  # human-readable source, e.g. "Boucher et al."
    citation: str  # arXiv id, UTS number, CVE id, dataset slug
    url: str
    version: str  # the pinned edition of the artifact
    licence: str
    external: bool = True
    issues: Sequence[int] = ()  # disarm issues this benchmark identified
    #: What this benchmark measured when it was run during the 0.15.0 cycle.
    #: Historical, and deliberately kept separate from :attr:`notes`: a fixed
    #: defect makes today's number differ, and that difference is the report's
    #: most useful column. Never edit one of these to match a fresh run.
    finding: str = ""
    #: How the benchmark works — methodology, not results. Stays true over time.
    notes: str = ""


@dataclass
class Measurement:
    """One reported number, with the denominator that makes it readable.

    ``value`` is whatever the suite measured. ``of`` is the population it was
    measured over, so "54" never appears in a report without "of 1683".
    """

    key: str
    value: float
    of: float | None = None
    unit: str = "count"
    higher_is_better: bool | None = None  # None = neither; a census, not a score
    detail: str = ""

    @property
    def ratio(self) -> float | None:
        if self.of in (None, 0):
            return None
        return self.value / self.of


@dataclass
class Outcome:
    """What one suite produced on one run."""

    suite: str
    family: Family
    provenance: Provenance
    status: Status = Status.OK
    measurements: list[Measurement] = field(default_factory=list)
    skip_reason: str = ""
    error: str = ""
    duration_s: float = 0.0
    population: int = 0
    extra: Mapping[str, Any] = field(default_factory=dict)

    @property
    def external(self) -> bool:
        return self.provenance.external

    def measurement(self, key: str) -> Measurement | None:
        for m in self.measurements:
            if m.key == key:
                return m
        return None


@runtime_checkable
class Suite(Protocol):
    """A single externally-produced benchmark, adapted.

    A suite must not carry attack vectors of its own. It locates the external
    artifact, loads it, scores disarm against it, and reports. If the artifact
    is not present it returns :attr:`Status.SKIPPED` — an absent corpus is
    never a pass.
    """

    name: str
    family: Family
    availability: Availability
    provenance: Provenance
    summary: str

    def available(self) -> tuple[bool, str]:
        """Return ``(ready, reason)``. ``reason`` explains a ``False``."""

    def run(self, limit: int | None = None) -> Outcome:
        """Score disarm against the artifact and return the measurements."""
