"""The disarm meta-benchmark: one harness over every externally produced
benchmark the 0.15.0 cycle used to find and verify a defect.

Entry points:

.. code-block:: bash

    python -m benchmarks.meta --list
    python -m benchmarks.meta --run --only-available
    python -m benchmarks.meta --run --select 'uts39-*' --report out.md
"""

from __future__ import annotations

from .protocol import Availability, Family, Measurement, Outcome, Provenance, Status, Suite
from .registry import all_suites, by_name, select
from .runner import RunReport, run

__all__ = [
    "Availability",
    "Family",
    "Measurement",
    "Outcome",
    "Provenance",
    "RunReport",
    "Status",
    "Suite",
    "all_suites",
    "by_name",
    "run",
    "select",
]
