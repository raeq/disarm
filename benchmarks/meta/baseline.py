"""Drift detection against a committed baseline.

The harness reports; it does not gate. A baseline exists so a *silent* change
between releases becomes visible — a coverage number that fell while every test
stayed green is exactly the failure mode 0.15.0 kept finding. Nothing here
returns a non-zero exit code, and nothing here decides that a delta is bad.

A baseline is keyed by suite and measurement. It records the disarm version and
the population it was measured over, because a ratio measured over 4,000 code
points and one measured over 150,000 are not comparable and must not be
subtracted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .protocol import Outcome, Status

BASELINE_DIR = Path(__file__).resolve().parent / "baselines"
#: Below this the delta is reported but flagged as noise rather than movement.
NOISE_FLOOR = 0.005


@dataclass
class Drift:
    suite: str
    key: str
    before: float
    after: float
    before_of: float | None
    after_of: float | None
    comparable: bool
    higher_is_better: bool | None
    subject: str = "disarm"
    #: The Unicode/confusables/UCD version moved since the baseline, so a change
    #: here is not attributable to the subject.
    tables_moved: bool = False

    @property
    def delta(self) -> float:
        return self.after - self.before

    @property
    def ratio_delta(self) -> float | None:
        if not self.comparable or not self.before_of or not self.after_of:
            return None
        return (self.after / self.after_of) - (self.before / self.before_of)

    @property
    def significant(self) -> bool:
        rd = self.ratio_delta
        if rd is None:
            return self.before != self.after
        return abs(rd) > NOISE_FLOOR

    @property
    def direction(self) -> str:
        """``better`` / ``worse`` / ``moved`` — never ``failed``."""
        if self.higher_is_better is None:
            return "moved"
        rd = self.ratio_delta
        change = rd if rd is not None else self.delta
        if change == 0:
            return "flat"
        improved = change > 0 if self.higher_is_better else change < 0
        return "better" if improved else "worse"


def baseline_path(name: str = "default") -> Path:
    return BASELINE_DIR / f"{name}.json"


def load(name: str = "default") -> dict[str, Any]:
    path = baseline_path(name)
    if not path.exists():
        return {}
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def snapshot(outcomes: list[Outcome], disarm_version: str) -> dict[str, Any]:
    """Build the record a baseline file holds."""
    suites: dict[str, dict[str, Any]] = {}
    for out in outcomes:
        if out.status is not Status.OK:
            continue
        # Keyed by subject as well as suite: the same measurement means a
        # different thing for a transliterator than for disarm, and subtracting
        # one from the other is meaningless.
        suites[f"{out.method.subject}::{out.suite}"] = {
            "population": out.population,
            "external": out.external,
            "subject": out.method.subject,
            "subject_version": out.method.subject_version,
            "measurements": {
                m.key: {
                    "value": m.value,
                    "of": m.of,
                    "higher_is_better": m.higher_is_better,
                }
                for m in out.measurements
            },
        }
    env = next((o.method.environment for o in outcomes if o.method.environment), {})
    return {
        "disarm_version": disarm_version,
        # A normative number moves when the tables move, not only when the code
        # does. Without these, a UCD bump reads as a disarm regression.
        "unicode_version": env.get("unicode_version", "?"),
        "confusables_version": env.get("confusables_version", "?"),
        "host_ucd": env.get("host_ucd", "?"),
        "recorded_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "suites": suites,
    }


def save(outcomes: list[Outcome], disarm_version: str, name: str = "default") -> Path:
    path = baseline_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot(outcomes, disarm_version), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def compare(outcomes: list[Outcome], name: str = "default") -> list[Drift]:
    """Diff this run against the baseline. Reports movement; judges nothing."""
    base = load(name)
    if not base:
        return []
    drifts: list[Drift] = []
    for out in outcomes:
        if out.status is not Status.OK:
            continue
        prior = base.get("suites", {}).get(f"{out.method.subject}::{out.suite}")
        if not prior:
            continue
        prior_pop = prior.get("population")
        comparable = prior_pop == out.population
        # A table bump moves normative numbers on its own. Recording it here
        # keeps the drift row honest about what actually changed.
        tables_moved = any(
            base.get(k, "?") not in ("?", out.method.environment.get(k, "?"))
            for k in ("unicode_version", "confusables_version", "host_ucd")
        )
        for m in out.measurements:
            before = prior.get("measurements", {}).get(m.key)
            if before is None:
                continue
            if before["value"] == m.value and before.get("of") == m.of:
                continue
            drifts.append(
                Drift(
                    suite=out.suite,
                    key=m.key,
                    before=float(before["value"]),
                    after=float(m.value),
                    before_of=before.get("of"),
                    after_of=m.of,
                    comparable=comparable and not tables_moved,
                    higher_is_better=m.higher_is_better,
                    subject=out.method.subject,
                    tables_moved=tables_moved,
                )
            )
    return drifts
