"""Drift guard: the Rust core's curated metadata (`src/metadata.rs`) is GENERATED
from the Python source of truth (`python/disarm/_enums.py`) by
`scripts/gen_metadata.py`. This test fails if they diverge — i.e. if `_enums.py`
(`LANG_META` / `SCRIPT_META` / `Script`) was edited without regenerating the Rust
mirror, which would make the core's `lang_info` / `script_info` / `list_scripts` /
`list_context_langs` return data inconsistent with Python.

Unlike the *advisory* binding-parity check (`test_parity.py`), this is a HARD
correctness gate: stale generated data is a real bug. Fix by running
`python scripts/gen_metadata.py` and committing `src/metadata.rs`.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
GEN = ROOT / "scripts" / "gen_metadata.py"
GENERATED = ROOT / "src" / "metadata.rs"


def test_metadata_rs_is_in_sync_with_python(tmp_path: pathlib.Path) -> None:
    if not GEN.exists() or not GENERATED.exists():  # pragma: no cover
        pytest.skip("metadata generator/output not present")

    regen = tmp_path / "metadata.rs"
    proc = subprocess.run(
        [sys.executable, str(GEN), str(regen)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"gen_metadata.py failed:\n{proc.stderr}"
    assert regen.read_text() == GENERATED.read_text(), (
        "src/metadata.rs is out of date with python/disarm/_enums.py — "
        "run `python scripts/gen_metadata.py` and commit the result."
    )
