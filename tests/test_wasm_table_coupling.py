"""#695 — a preset links only the tables its own steps reach.

`presets::run` walked a `&[Step]` and called `apply_into` with a runtime value, so the
optimiser could not prove any match arm unreachable and every preset linked every table
a step *could* reach. `strip_format` declares five steps that neither transliterate nor
demojize, and linked the Hanzi pinyin and CLDR emoji tables anyway — 663 KB against a
possible 27 KB.

The check that matters is **not** the byte count. A module grows and shrinks for ordinary
reasons and a threshold on it produces noise; a table *appearing* in a surface that cannot
reach it is categorical, and it is what actually regressed. So the sizes are recorded as
generous ceilings and the table presence is asserted exactly.

Marked `slow`: each surface is a full `--release` wasm build. Run with `-m slow`, or
directly via `python scripts/wasm_size_probe.py`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parent.parent

#: `surface -> (pinyin expected, emoji expected, byte ceiling)`.
#:
#: The ceilings are roughly 1.5x the measured size — loose enough that ordinary codegen
#: drift does not fail them, tight enough that a re-coupled table cannot hide, since the
#: tables are hundreds of KB.
EXPECTED = {
    "strip_format": (False, False, 60_000),
    "canonicalize": (False, False, 320_000),
    "canonicalize_strict": (False, False, 330_000),
    # No longer demojizes (#910), so the emoji table must NOT be linked. This gate caught
    # the change the moment the step came out, which is what it is for — and the ceiling
    # drops with it: a preset that stopped naming emoji has no business carrying the CLDR
    # name table into a wasm build.
    "strip_obfuscation": (False, False, 400_000),
    "strip_bidi": (False, False, 40_000),
    "collapse_whitespace": (False, False, 40_000),
}


def wasm_target_installed() -> bool:
    if shutil.which("rustup") is None:
        return False
    out = subprocess.run(
        ["rustup", "target", "list", "--installed"], capture_output=True, text=True, check=False
    ).stdout
    return "wasm32-unknown-unknown" in out


requires_wasm = pytest.mark.skipif(
    not wasm_target_installed(), reason="wasm32-unknown-unknown target not installed"
)


@requires_wasm
def test_no_preset_links_a_table_its_steps_cannot_reach() -> None:
    """The #695 acceptance criterion, for every surface at once.

    One build per surface, so this runs them in a single subprocess call rather than
    parametrising — six `--release` wasm builds is already the slow part.
    """
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "wasm_size_probe.py"), *EXPECTED],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    measured = {row["surface"]: row for row in json.loads(result.stdout)}

    wrong_tables = []
    over_ceiling = []
    for surface, (pinyin, emoji, ceiling) in EXPECTED.items():
        row = measured[surface]
        if (row["pinyin"], row["emoji"]) != (pinyin, emoji):
            wrong_tables.append(
                f"{surface}: expected pinyin={pinyin} emoji={emoji}, "
                f"got pinyin={row['pinyin']} emoji={row['emoji']}"
            )
        if row["bytes"] > ceiling:
            over_ceiling.append(f"{surface}: {row['bytes']:,} bytes over {ceiling:,}")

    assert not wrong_tables, (
        "a preset links a table its own steps cannot reach — the #695 coupling is back:\n  "
        + "\n  ".join(wrong_tables)
    )
    assert not over_ceiling, (
        "a surface grew past its ceiling. If the growth is deliberate, raise the ceiling "
        "and say why; if not, something re-coupled:\n  " + "\n  ".join(over_ceiling)
    )


def test_every_expected_surface_is_one_the_probe_knows() -> None:
    """Cheap, and runs without the wasm target.

    A surface renamed in the probe and not here would skip silently — the probe would
    error on an unknown name, but only if this list is what it is given.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from wasm_size_probe import SURFACES
    finally:
        sys.path.pop(0)
    assert set(EXPECTED) <= set(SURFACES), (
        f"expected surfaces missing from the probe: {sorted(set(EXPECTED) - set(SURFACES))}"
    )
