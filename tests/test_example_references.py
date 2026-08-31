"""Every `--example NAME` a workflow or script builds must exist in `examples/`.

`examples/perf_workload.rs` was deleted in a branch and nothing failed: the perf gate is
the only thing that builds it, `perf-gate.yml` is not part of PR CI, and no test reads
`examples/` at all. The deletion reached review as a silent `-114` in a diff about
something else.

`cargo` does not help here either — an example nobody names is simply not built, so a
missing one is not a compile error. The reference is in YAML and shell, so the check has
to be too.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"

#: `--example foo`, `--example=foo`, and the bare name in a `PERF_WORKLOAD_BIN`-style path.
_CARGO_EXAMPLE = re.compile(r"--example[= ]([A-Za-z0-9_]+)")
_TARGET_PATH = re.compile(r"target/(?:release|debug)/examples/([A-Za-z0-9_]+)")

_SEARCH_DIRS = (".github/workflows", "scripts", "benchmarks")
_SEARCH_SUFFIXES = {".yml", ".yaml", ".sh", ".py", ".toml", ".md"}


def _referenced() -> dict[str, list[str]]:
    """Every example name a workflow or script builds or runs, with where it was named."""
    found: dict[str, list[str]] = {}
    for directory in _SEARCH_DIRS:
        base = ROOT / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in _SEARCH_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in (_CARGO_EXAMPLE, _TARGET_PATH):
                for name in pattern.findall(text):
                    found.setdefault(name, []).append(str(path.relative_to(ROOT)))
    return found


REFERENCED = _referenced()


def test_something_actually_references_an_example() -> None:
    """A gate over an empty set passes for the wrong reason."""
    assert REFERENCED, (
        "no `--example` reference found at all — the patterns or the search dirs have "
        "drifted, and this file is no longer checking anything"
    )


@pytest.mark.parametrize("name", sorted(REFERENCED), ids=sorted(REFERENCED))
def test_a_referenced_example_exists(name: str) -> None:
    source = EXAMPLES / f"{name}.rs"
    assert source.is_file(), (
        f"examples/{name}.rs is referenced by {', '.join(sorted(set(REFERENCED[name])))} "
        f"and does not exist. `cargo build` will not catch this — an example nobody names "
        f"is simply not built — and the perf gate that builds this one does not run on PR CI."
    )


def test_every_example_compiles_under_the_pure_core() -> None:
    """The examples build with `--no-default-features`, which is how the perf gate builds.

    Not a compile here — that is the Rust gate's job — but a cheap structural check that
    no example was added carrying a `use disarm::` path only the pyo3 build provides.
    """
    for source in sorted(EXAMPLES.glob("*.rs")):
        text = source.read_text(encoding="utf-8")
        assert "_disarm::" not in text, (
            f"{source.name} names the pyo3 crate `_disarm`; examples build against the "
            f"pure core as `disarm`"
        )
