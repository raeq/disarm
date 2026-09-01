"""Shared machinery for meta-benchmark suites.

Nothing here decides what a benchmark *is* — that belongs to the external
artifact. This module only locates artifacts, enumerates the disarm surfaces a
suite scores against, and gives suites a common way to say "not available"
rather than quietly reporting a zero.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from .protocol import (
    Availability,
    Family,
    Measurement,
    Method,
    Outcome,
    Provenance,
    Reproduction,
    Status,
)
from .subjects import Capability, Subject
from .subjects import by_name as subject_by_name

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


def surfaces(subject: Subject | None = None) -> dict[str, Callable[[str], str]]:
    """Every transforming entry point of ``subject``, defaulting to disarm.

    For disarm that is eleven ``PRESETS`` plus the eight named ``get_pipeline``
    profiles. Suites score across all of them because the 0.15.0 findings
    repeatedly turned on a *disagreement between surfaces*, not on one surface's
    behaviour.
    """
    return (subject or _default_subject()).transforms()


def detectors(subject: Subject | None = None) -> dict[str, Callable[[str], bool]]:
    """Boolean detector surfaces — the "does the tool see it" half of a score."""
    return (subject or _default_subject()).detectors()


def _default_subject() -> Subject:
    subject = subject_by_name("disarm")
    if subject is None:  # pragma: no cover - disarm is always registered
        raise RuntimeError("the disarm subject is not registered")
    return subject


def sha256_of(path: Path) -> tuple[str, int]:
    """Digest and size of an external artifact, so a run pins what it read."""
    import hashlib

    h = hashlib.sha256()
    size = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def _environment() -> dict[str, str]:
    import platform
    import unicodedata as ud

    env = {
        "python": platform.python_version(),
        "host_ucd": ud.unidata_version,
        "platform": platform.platform(terse=True),
    }
    try:
        import disarm

        env["disarm"] = getattr(disarm, "__version__", "?")
        env["unicode_version"] = getattr(disarm, "UNICODE_VERSION", "?")
        env["confusables_version"] = getattr(disarm, "CONFUSABLES_VERSION", "?")
    except ImportError:  # pragma: no cover
        pass
    return env


def record(
    outcome: Outcome,
    domain: str,
    predicates: Sequence[str] = (),
    **parameters: object,
) -> None:
    """Write the method half of an outcome: what was swept, and with what."""
    outcome.method.domain = domain
    outcome.method.predicates = list(predicates)
    outcome.method.parameters.update(parameters)


def skipped(suite: SuiteBase, reason: str) -> Outcome:
    out = Outcome(
        suite=suite.name,
        family=suite.family,
        provenance=suite.provenance,
        status=Status.SKIPPED,
        skip_reason=reason,
    )
    subject = getattr(suite, "subject", None)
    if subject is not None:
        out.method.subject = subject.info.name
        out.method.subject_version = subject.info.version
    return out


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
    #: Can this suite score a tool other than disarm? False where the question is
    #: about a disarm-specific surface (a key builder, a named anomaly kind) that
    #: no other tool exposes — running such a suite against `ftfy` would produce a
    #: zero that reads as a result rather than as "not applicable".
    MULTI_SUBJECT = False
    #: Capabilities a subject must provide before this suite can score it.
    REQUIRES: tuple[str, ...] = (Capability.TRANSFORM,)

    #: Set for the duration of :meth:`run`.
    subject: Subject | None = None

    def transforms(self) -> dict[str, Callable[[str], str]]:
        return surfaces(self.subject)

    def detect(self) -> dict[str, Callable[[str], bool]]:
        return detectors(self.subject)

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

    #: Values the suite's published script printed at :attr:`REPRO_VERSION`,
    #: copied from that script's own output. Never edited to match a fresh run —
    #: a mismatch is the signal this suite no longer measures what it cites.
    REPRO_EXPECTED: dict[str, float] = {}
    REPRO_VERSION = "0.14.1"

    def reproduce(self) -> dict[str, float]:
        """Recompute the published script's exact quantities.

        Distinct from :meth:`measure`, which usually sweeps a wider domain. This
        one has to match the gist method for method, or the finding and the
        measurement are not a before/after.
        """
        return {}

    def measure(self, outcome: Outcome, limit: int | None) -> None:  # pragma: no cover
        raise NotImplementedError

    def supports(self, subject: Subject) -> tuple[bool, str]:
        """Can this suite score ``subject``?"""
        if subject.info.name != "disarm" and not self.MULTI_SUBJECT:
            return False, (
                f"{self.name} measures a disarm-specific surface; "
                f"{subject.info.name} exposes no equivalent"
            )
        missing = set(self.REQUIRES) - subject.capabilities()
        if missing:
            return False, f"{subject.info.name} provides no {'/'.join(sorted(missing))} surface"
        return True, ""

    def run(self, limit: int | None = None, subject: Subject | None = None) -> Outcome:
        self.subject = subject or _default_subject()
        ready, reason = self.available()
        if not ready:
            return skipped(self, reason)
        supported, why = self.supports(self.subject)
        if not supported:
            return skipped(self, why)
        outcome = Outcome(suite=self.name, family=self.family, provenance=self.provenance)
        outcome.method = Method(
            subject=self.subject.info.name,
            subject_version=self.subject.info.version,
            environment=_environment(),
            parameters={"limit": limit},
        )
        located = self.locate()
        if located is not None:
            digest, size = sha256_of(located)
            outcome.method.artifact = str(located)
            outcome.method.artifact_sha256 = digest
            outcome.method.artifact_bytes = size
        with timed(outcome):
            try:
                self.measure(outcome, limit)
                outcome.method.domain_size = outcome.population
                # A reproduction pins a published disarm measurement, so it is
                # meaningless for any other subject.
                if self.REPRO_EXPECTED and outcome.method.subject == "disarm":
                    actual = self.reproduce()
                    outcome.reproduction = [
                        Reproduction(
                            key=key,
                            expected=expected,
                            actual=actual.get(key, float("nan")),
                            version=self.REPRO_VERSION,
                        )
                        for key, expected in sorted(self.REPRO_EXPECTED.items())
                    ]
            except Exception as exc:  # noqa: BLE001 - a suite must never kill the run
                outcome.status = Status.ERROR
                outcome.error = f"{type(exc).__name__}: {exc}"
        return outcome


def add(outcome: Outcome, key: str, value: float, of: float | None = None, **kw: object) -> None:
    """Record one measurement on ``outcome``."""
    outcome.measurements.append(Measurement(key=key, value=value, of=of, **kw))  # type: ignore[arg-type]
