"""Advisory binding-parity check — runs in the normal test cycle and EMITS WARNINGS,
never failures.

A security release must never wait on interface parity, so this is informational
only: it re-seeds the cross-binding parity matrix from source and warns on
(a) gaps where a binding lacks an operation the core/Python expose, and (b) a stale
committed manifest (`generated/parity.yaml`). It never asserts/fails.

This is the *lightweight* check (pure source-scrape, no binding builds, so it runs
anywhere). The rigorous live-introspection check —
`scripts/parity_check.py` diffing the manifest against the *built* modules via
`tools/introspect/*` — is the CI-binding-job / release-prep tool.

The check is deliberately NOT in the publish flow (publish.yml runs only the formal
tier), so interface parity never gates a release.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import warnings

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEEDER = ROOT / "scripts" / "parity.py"
MANIFEST = ROOT / "generated" / "parity.yaml"


class ParityWarning(UserWarning):
    """Advisory signal that binding parity drifted or the manifest is stale."""


def test_binding_parity_advisory(tmp_path: pathlib.Path) -> None:
    """Re-seed parity from source and warn (never fail) on gaps or a stale manifest."""
    if not SEEDER.exists():  # pragma: no cover - tooling is optional
        warnings.warn("parity seeder (scripts/parity.py) not present", ParityWarning, stacklevel=2)
        return

    regen = tmp_path / "parity.yaml"
    proc = subprocess.run(
        [sys.executable, str(SEEDER), str(regen)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:  # advisory: surface, don't fail
        warnings.warn(f"parity seeder errored:\n{proc.stderr}", ParityWarning, stacklevel=2)
        return

    # (a) cross-binding gaps — "=== <lang>: <n> true gaps ==="
    gaps = [
        (lang, int(n)) for lang, n in re.findall(r"=== (\w+): (\d+) true gaps ===", proc.stdout)
    ]
    summary = ", ".join(f"{lang} {n}" for lang, n in gaps if n)
    if summary:
        warnings.warn(
            f"binding parity gaps (advisory, non-blocking): {summary}. "
            "Run `python scripts/parity.py` for the matrix; this never blocks a release.",
            ParityWarning,
            stacklevel=2,
        )

    # (b) stale committed manifest
    if MANIFEST.exists() and regen.read_text() != MANIFEST.read_text():
        warnings.warn(
            "generated/parity.yaml is out of date — run `python scripts/parity.py` and commit it.",
            ParityWarning,
            stacklevel=2,
        )

    # Always passes: this check is advisory only.
