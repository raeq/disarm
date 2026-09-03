"""The registry: every benchmark 0.15.0 leaned on, in one place.

``m`` is whatever :func:`all_suites` returns. ``n`` is whatever :func:`select`
picks out of it. Nothing else in the harness hard-codes a suite name.
"""

from __future__ import annotations

import fnmatch
import random
from collections.abc import Sequence

from .protocol import Availability, Family, Suite
from .suites import MODULES


def all_suites() -> list[Suite]:
    """Every registered suite, ordered by family then name — this is ``m``."""
    suites: list[Suite] = []
    for module in MODULES:
        suites.extend(module.SUITES)
    order = list(Family)
    return sorted(suites, key=lambda s: (order.index(s.family), s.name))


def by_name(name: str) -> Suite | None:
    for suite in all_suites():
        if suite.name == name:
            return suite
    return None


def select(
    patterns: Sequence[str] | None = None,
    families: Sequence[str] | None = None,
    availabilities: Sequence[str] | None = None,
    include_introspective: bool = False,
    only_available: bool = False,
    sample: int | None = None,
    seed: int = 0,
) -> list[Suite]:
    """Pick ``n`` of ``m``.

    Filters compose (all must match). ``patterns`` are shell globs over the
    suite name, so ``--select 'uts39-*'`` takes the whole UTS #39 group.
    ``sample`` draws deterministically from whatever survives the filters, so a
    partial run is reproducible from its seed.
    """
    suites = all_suites()
    if not include_introspective:
        suites = [s for s in suites if s.provenance.external]
    if patterns:
        suites = [s for s in suites if any(fnmatch.fnmatch(s.name, p) for p in patterns)]
    if families:
        wanted = {Family(f) for f in families}
        suites = [s for s in suites if s.family in wanted]
    if availabilities:
        wanted_av = {Availability(a) for a in availabilities}
        suites = [s for s in suites if s.availability in wanted_av]
    if only_available:
        suites = [s for s in suites if s.available()[0]]
    if sample is not None and sample < len(suites):
        rng = random.Random(seed)
        suites = sorted(rng.sample(suites, sample), key=lambda s: s.name)
    return suites
