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

from .protocol import Family, Outcome, Provenance, Status, Suite


@dataclass
class RunReport:
    outcomes: list[Outcome] = field(default_factory=list)
    selected: int = 0
    registered: int = 0
    duration_s: float = 0.0
    disarm_version: str = "?"
    unicode_version: str = "?"
    confusables_version: str = "?"

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


def run(
    suites: Sequence[Suite],
    registered: int,
    limit: int | None = None,
    on_start: Callable[[Suite], None] | None = None,
    on_finish: Callable[[Outcome], None] | None = None,
) -> RunReport:
    report = RunReport(selected=len(suites), registered=registered)
    report.disarm_version, report.unicode_version, report.confusables_version = _versions()
    start = time.perf_counter()
    for suite in suites:
        if on_start:
            on_start(suite)
        try:
            outcome = suite.run(limit=limit)
        except Exception as exc:  # noqa: BLE001 - a broken suite is a finding, not a crash
            outcome = Outcome(
                suite=suite.name,
                family=suite.family,
                provenance=getattr(suite, "provenance", _unknown_provenance()),
                status=Status.ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )
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
