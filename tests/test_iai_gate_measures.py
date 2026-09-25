"""The iai gate measures something, and says so when it does not.

`[profile.release]` sets `strip = true`, and `cargo bench` inherits it. iai-callgrind
counts only between the entry and exit of the benchmark function, which Callgrind finds by
symbol, so in a stripped binary it finds nothing and every metric is 0. The required
"iai estimated-cycles gate" then compared 0 against 0 from #893 until this fix, and passed
every pull request whatever it did to performance.

Two fixes, each tested here:

* `[profile.bench]` keeps the symbols, and the workflow sets `CARGO_PROFILE_BENCH_STRIP`
  so that a merge-base from before the fix measures too;
* `scripts/check_iai_nonzero.py` reads the `summary.json` each benchmark writes and fails
  when one measured zero instructions, so the gate cannot quietly go vacuous again.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "scripts" / "check_iai_nonzero.py"
WORKFLOW = ROOT / ".github" / "workflows" / "perf-gate.yml"


def _checker():
    spec = importlib.util.spec_from_file_location("check_iai_nonzero", CHECKER)
    assert spec and spec.loader, f"{CHECKER} is missing"
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_iai_nonzero"] = module
    spec.loader.exec_module(module)
    return module


def _summary(root: Path, name: str, metrics: dict) -> None:
    """A `summary.json` in the shape iai-callgrind 0.16 writes, reduced to what is read."""
    path = root / "disarm" / "bench_iai" / "perf_gate" / name / "summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "module_path": f"bench_iai::perf_gate::{name.split('.')[0]}",
                "id": name.split(".")[1],
                "profiles": [
                    {
                        "tool": "Callgrind",
                        "summaries": {
                            "total": {"summary": {"Callgrind": {"Ir": {"metrics": metrics}}}}
                        },
                    }
                ],
            }
        )
    )


def test_a_run_that_measured_passes(tmp_path: Path) -> None:
    _summary(tmp_path, "transliterate_doc.ascii", {"Left": {"Int": 4982}})
    _summary(tmp_path, "slugify_doc.latin", {"Both": [{"Int": 1474160}, {"Int": 1474160}]})
    assert _checker().zero_measurements(tmp_path) == []


def test_a_benchmark_that_measured_zero_is_named(tmp_path: Path) -> None:
    _summary(tmp_path, "transliterate_doc.ascii", {"Left": {"Int": 4982}})
    _summary(tmp_path, "slugify_doc.latin", {"Both": [{"Int": 0}, {"Int": 0}]})
    assert _checker().zero_measurements(tmp_path) == ["bench_iai::perf_gate::slugify_doc latin"]


def test_a_zero_baseline_is_as_invalid_as_a_zero_run(tmp_path: Path) -> None:
    """A comparison against 0 is no comparison: 4,982 against 0 reads as +inf, and
    0 against 0 as "no change". Either side measuring zero fails the gate."""
    _summary(tmp_path, "transliterate_doc.ascii", {"Both": [{"Int": 4982}, {"Int": 0}]})
    _summary(tmp_path, "slugify_doc.ascii", {"Both": [{"Int": 0}, {"Int": 851918}]})
    assert _checker().zero_measurements(tmp_path) == [
        "bench_iai::perf_gate::slugify_doc ascii",
        "bench_iai::perf_gate::transliterate_doc ascii",
    ]


def test_no_summaries_at_all_is_a_failure(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        _checker().main([str(tmp_path)])


def test_the_bench_profile_keeps_symbols() -> None:
    manifest = (ROOT / "Cargo.toml").read_text()
    section = re.search(r"^\[profile\.bench\]\n((?:[^\[].*\n?)*)", manifest, re.M)
    assert section, "Cargo.toml has no [profile.bench]; it inherits release's strip = true"
    assert re.search(r"^strip\s*=\s*false", section[1], re.M), section[1]


def test_the_gate_keeps_symbols_on_both_sides_and_checks_the_result() -> None:
    workflow = WORKFLOW.read_text()
    # The env reaches the merge-base build too, whose Cargo.toml may still strip.
    assert re.search(r'CARGO_PROFILE_BENCH_STRIP:\s*"?false"?', workflow)
    assert "--save-summary=json" in workflow
    assert "scripts/check_iai_nonzero.py" in workflow


def _push_paths() -> list[str]:
    """The `on.push.paths` globs, in order."""
    block = WORKFLOW.read_text().split("  push:", 1)[1].split("\nconcurrency:", 1)[0]
    return re.findall(r'^\s+- "([^"]+)"$', block, re.MULTILINE)


def _relevant_alternatives() -> list[str]:
    """The alternatives of the `changes` job's perf-relevant `grep -qE`."""
    pattern = re.search(r"grep -qE '\^\(([^']+)\)'; then\n\s+touched=true", WORKFLOW.read_text())
    assert pattern, "the perf-relevant grep in the `changes` job has moved"
    return pattern.group(1).split("|")


def _as_alternative(glob: str) -> str:
    """`src/**` -> `src/`, `build.rs` -> `build\\.rs$`: the regex a path glob means."""
    if glob.endswith("/**"):
        return glob[: -len("**")]
    return glob.replace(".", "\\.") + "$"


def test_push_paths_and_the_perf_relevant_grep_are_one_list():
    """The two lists the header says MUST stay in lockstep, held equal.

    A path in the grep but not the push filter is measured on a pull request and never
    on main; `codegen/` was in neither while build.rs generated the tables the hot paths
    read from it (the normalization boundaries, the emoji candidates, the confusable key
    bitmaps), so a change there alone went unmeasured everywhere.
    """
    paths = _push_paths()
    assert "codegen/**" in paths
    assert sorted(_as_alternative(p) for p in paths) == sorted(_relevant_alternatives())
