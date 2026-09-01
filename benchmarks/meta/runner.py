"""Run ``n`` of ``m`` suites and collect their outcomes.

Suites are independent by construction, so the runner is deliberately dull: it
executes them in registry order, catches everything, and never lets one suite's
failure end the run. A suite whose external artifact is missing comes back
SKIPPED with the reason, which is the only honest answer — an absent corpus is
not a passing corpus.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from .fetch import Provisioning, Source
from .fetch import provision as provision_sources
from .protocol import Family, Outcome, Provenance, Status, Suite
from .subjects import Subject
from .subjects import by_name as subject_by_name


@dataclass
class RunReport:
    outcomes: list[Outcome] = field(default_factory=list)
    selected: int = 0
    registered: int = 0
    duration_s: float = 0.0
    disarm_version: str = "?"
    unicode_version: str = "?"
    confusables_version: str = "?"
    subjects: list[str] = field(default_factory=list)
    provisioning: Provisioning = field(default_factory=Provisioning)

    @property
    def ran(self) -> list[Outcome]:
        return [o for o in self.outcomes if o.status is Status.OK]

    @property
    def skipped(self) -> list[Outcome]:
        return [o for o in self.outcomes if o.status is Status.SKIPPED]

    @property
    def errored(self) -> list[Outcome]:
        return [o for o in self.outcomes if o.status is Status.ERROR]

    @property
    def external_ran(self) -> list[Outcome]:
        return [o for o in self.ran if o.external]

    def by_family(self) -> dict[Family, list[Outcome]]:
        out: dict[Family, list[Outcome]] = {}
        for o in self.outcomes:
            out.setdefault(o.family, []).append(o)
        return out

    def by_subject(self) -> dict[str, list[Outcome]]:
        out: dict[str, list[Outcome]] = {}
        for o in self.outcomes:
            out.setdefault(o.method.subject, []).append(o)
        return out

    def comparison(self, suite: str, key: str) -> dict[str, float]:
        """One measurement across every subject that produced it.

        The whole point of a subject matrix: an absolute number becomes a
        column only when something else is in the next column.
        """
        got: dict[str, float] = {}
        for o in self.ran:
            if o.suite != suite:
                continue
            m = o.measurement(key)
            if m is not None:
                got[o.method.subject] = m.ratio if m.ratio is not None else m.value
        return got


def provision(
    suites: Sequence[Suite],
    offline: bool = False,
    refresh: bool = False,
) -> Provisioning:
    """Pull every artifact the selection needs, before any suite runs.

    Anything already on disk is left exactly as it is, so an operator who placed
    a particular revision keeps it. A failed fetch is recorded and the run
    continues: the suite then reports SKIPPED, the same answer it gave before
    provisioning existed.
    """
    sources: list[Source] = []
    seen: set[str] = set()
    for suite in suites:
        for source in getattr(suite, "SOURCES", ()):
            if source.url not in seen:
                seen.add(source.url)
                sources.append(source)
    return provision_sources(sources, offline=offline, refresh=refresh)


def run(
    suites: Sequence[Suite],
    registered: int,
    limit: int | None = None,
    subjects: Sequence[Subject] | None = None,
    provisioning: Provisioning | None = None,
    on_start: Callable[[Suite], None] | None = None,
    on_finish: Callable[[Outcome], None] | None = None,
) -> RunReport:
    """Run every (suite, subject) pair.

    A pair the suite cannot serve — a key-builder question put to a
    transliterator — comes back SKIPPED with the reason, exactly like a missing
    corpus. Silence would read as a zero, and a zero reads as a result.
    """
    if not subjects:
        default = subject_by_name("disarm")
        subjects = [default] if default is not None else []
    report = RunReport(selected=len(suites), registered=registered)
    report.disarm_version, report.unicode_version, report.confusables_version = _versions()
    report.subjects = [s.info.name for s in subjects]
    if provisioning is not None:
        report.provisioning = provisioning
    start = time.perf_counter()
    for suite in suites:
        if on_start:
            on_start(suite)
        for subject in subjects:
            try:
                outcome = suite.run(limit=limit, subject=subject)
            except Exception as exc:  # noqa: BLE001 - a broken suite is a finding
                outcome = Outcome(
                    suite=suite.name,
                    family=suite.family,
                    provenance=getattr(suite, "provenance", _unknown_provenance()),
                    status=Status.ERROR,
                    error=f"{type(exc).__name__}: {exc}",
                )
                outcome.method.subject = subject.info.name
            report.outcomes.append(outcome)
            if on_finish:
                on_finish(outcome)
    report.duration_s = time.perf_counter() - start
    return report


def _versions() -> tuple[str, str, str]:
    try:
        import disarm
    except ImportError:
        return "not installed", "?", "?"
    return (
        getattr(disarm, "__version__", "?"),
        getattr(disarm, "UNICODE_VERSION", "?"),
        getattr(disarm, "CONFUSABLES_VERSION", "?"),
    )


def _unknown_provenance() -> Provenance:
    return Provenance(
        origin="unknown",
        citation="unknown",
        url="",
        version="",
        licence="",
    )
