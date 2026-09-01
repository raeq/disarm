"""Shared machinery for meta-benchmark suites.

Nothing here decides what a benchmark *is* — that belongs to the external
artifact. This module only locates artifacts, enumerates the disarm surfaces a
suite scores against, and gives suites a common way to say "not available"
rather than quietly reporting a zero.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from .protocol import Availability, Family, Measurement, Outcome, Provenance, Status

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
FIXTURES = REPO_ROOT / "tests" / "fixtures"
CACHE = Path(os.environ.get("DISARM_META_CACHE", "/tmp/disarm_meta_cache"))


def artifact(*candidates: Path | str, env: str | None = None) -> Path | None:
    """Return the first artifact path that exists, honouring ``env`` first.

    External corpora are not vendored. An operator points the suite at a
    downloaded copy through the environment variable named in the registry;
    absent that, the suite falls back to the shared cache directory.
    """
    if env:
        override = os.environ.get(env)
        if override and Path(override).exists():
            return Path(override)
    for cand in candidates:
        p = Path(cand)
        if p.exists():
            return p
    return None


def thin(items: list[int], limit: int | None) -> list[int]:
    """Reduce a code-point domain to ``limit`` by even stride, never by truncation.

    Truncating a sorted code-point list to the first N samples Latin, Greek and
    Cyrillic and nothing else, which makes a quick pass silently disagree with a
    full one — the low planes are the best-covered part of every table here. A
    stride keeps the sample spread across the planes, so ``--limit`` changes the
    precision of a census and not its shape.
    """
    if limit is None or limit >= len(items):
        return items
    if limit <= 0:
        return []
    step = max(1, len(items) // limit)
    return items[::step][:limit]


def surfaces() -> dict[str, Callable[[str], str]]:
    """Every transforming disarm entry point, by the name a report should print.

    Eleven ``PRESETS`` plus the eight named ``get_pipeline`` profiles. Suites
    score across all of them because the 0.15.0 findings repeatedly turned on a
    *disagreement between surfaces*, not on one surface's behaviour.
    """
    import disarm

    out: dict[str, Callable[[str], str]] = {}
    for name in sorted(disarm.PRESETS):
        out[name] = getattr(disarm, name)
    for profile in disarm.list_profiles():
        # TextPipeline is callable; it has no apply() method.
        out[f"profile:{profile}"] = disarm.get_pipeline(profile)
    return out


def detectors() -> dict[str, Callable[[str], bool]]:
    """Boolean detector surfaces — the "does disarm see it" half of a score."""
    import disarm

    return {
        "has_anomalies": disarm.has_anomalies,
        "is_confusable": lambda s: bool(disarm.is_confusable(s)),
        "is_mixed_script": disarm.is_mixed_script,
        "is_zalgo": disarm.is_zalgo,
        "has_bidi_conflict": disarm.has_bidi_conflict,
        "has_bidi_control": disarm.has_bidi_control,
    }


def skipped(suite: SuiteBase, reason: str) -> Outcome:
    return Outcome(
        suite=suite.name,
        family=suite.family,
        provenance=suite.provenance,
        status=Status.SKIPPED,
        skip_reason=reason,
    )


@contextmanager
def timed(outcome: Outcome) -> Iterator[Outcome]:
    start = time.perf_counter()
    try:
        yield outcome
    finally:
        outcome.duration_s = time.perf_counter() - start


class SuiteBase:
    """Default :class:`~.protocol.Suite` behaviour: declare, locate, measure.

    Subclasses set the class attributes and implement :meth:`measure`. The base
    handles availability, timing, error capture and the ``SKIPPED`` path, so a
    suite that cannot find its corpus reports that fact instead of a zero.
    """

    name: str = ""
    family: Family = Family.ACADEMIC
    availability: Availability = Availability.VENDORED
    provenance: Provenance
    summary: str = ""
    #: Environment variable an operator sets to point at the downloaded artifact.
    env_var: str | None = None

    def locate(self) -> Path | None:
        """Where the external artifact lives, or ``None``. Override as needed."""
        return None

    def available(self) -> tuple[bool, str]:
        if self.availability in (Availability.VENDORED, Availability.DERIVED):
            return True, ""
        path = self.locate()
        if path is not None:
            return True, ""
        hint = f" Set ${self.env_var} to a downloaded copy." if self.env_var else ""
        return False, f"{self.provenance.citation} artifact not present.{hint}"

    def measure(self, outcome: Outcome, limit: int | None) -> None:  # pragma: no cover
        raise NotImplementedError

    def run(self, limit: int | None = None) -> Outcome:
        ready, reason = self.available()
        if not ready:
            return skipped(self, reason)
        outcome = Outcome(suite=self.name, family=self.family, provenance=self.provenance)
        with timed(outcome):
            try:
                self.measure(outcome, limit)
            except Exception as exc:  # noqa: BLE001 - a suite must never kill the run
                outcome.status = Status.ERROR
                outcome.error = f"{type(exc).__name__}: {exc}"
        return outcome


def add(outcome: Outcome, key: str, value: float, of: float | None = None, **kw: object) -> None:
    """Record one measurement on ``outcome``."""
    outcome.measurements.append(Measurement(key=key, value=value, of=of, **kw))  # type: ignore[arg-type]
