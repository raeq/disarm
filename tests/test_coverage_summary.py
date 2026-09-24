"""`scripts/coverage_summary.py` renders the lcov that `coverage.yml` publishes.

The job summary is the only place the Rust coverage numbers are read, so a parser that
silently dropped a file, or sorted the wrong way, would misreport the baseline without
failing anything. Three small checks on a hand-written lcov.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "coverage_summary", ROOT / "scripts" / "coverage_summary.py"
)
assert _spec is not None and _spec.loader is not None
cov = importlib.util.module_from_spec(_spec)
sys.modules["coverage_summary"] = cov
_spec.loader.exec_module(cov)

LCOV = """\
SF:/work/disarm/src/zalgo.rs
FNF:4
FNH:4
BRF:10
BRH:9
LF:100
LH:100
end_of_record
SF:/work/disarm/src/api/safety.rs
FNF:10
FNH:5
LF:200
LH:100
end_of_record
SF:/work/disarm/tests/api_idioms.rs
LF:50
LH:10
end_of_record
"""


def test_totals_cover_src_only() -> None:
    table = cov.render(cov.parse(LCOV))
    # 200 of 300 src lines; the tests/ file is not the thing measured.
    assert "| **Total** | **66.7%** (200/300)" in table
    assert "api_idioms" not in table


def test_lowest_covered_module_first() -> None:
    rows = [r for r in cov.render(cov.parse(LCOV)).splitlines() if r.startswith("| `")]
    assert [r.split("`")[1] for r in rows] == ["src/api/safety.rs", "src/zalgo.rs"]


def test_no_branch_records_reads_as_a_dash() -> None:
    safety = next(r for r in cov.render(cov.parse(LCOV)).splitlines() if "safety" in r)
    assert "| - |" in safety
