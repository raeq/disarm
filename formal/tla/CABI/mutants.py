"""Model validation: each mutant breaks one rule the model is meant to police, and
TLC must report the matching invariant on `CABI_contract.cfg` (which passes unmutated).

    TLA2TOOLS=/path/to/tla2tools.jar python3 mutants.py

A mutant that still passes would mean the invariant cannot see the defect it names.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SPEC = (HERE / "CABI.tla").read_text()
CFG = (HERE / "CABI_contract.cfg").read_text()

MUTANTS = {
    # The client stops before freeing everything.
    "NoLeak": ('Finish == /\\ phase = "cleanup" /\\ owned = {}', 'Finish == /\\ phase = "cleanup"'),
    # The library hands back an address it already gave out (call 1's) on call 2.
    "NoDoubleFree": (
        "OutAddr(n, k) == IF n = 0 THEN STATIC ELSE k",
        "OutAddr(n, k) == IF n = 0 THEN STATIC ELSE 1",
    ),
    # A failed call fills both halves of the DisarmResult.
    "ResultExclusive": ("ELSE [value |-> NULL, error |-> a]", "ELSE [value |-> a, error |-> a]"),
    # The drop frees one byte fewer than was allocated.
    "NoLayoutMismatch": ("[len EXCEPT ![a] = n + 1]", "[len EXCEPT ![a] = n + 2]"),
}


def main() -> int:
    jar = os.environ["TLA2TOOLS"]
    bad = 0
    for inv, (old, new) in MUTANTS.items():
        assert SPEC.count(old) == 1, f"mutation anchor for {inv} not found exactly once"
        with tempfile.TemporaryDirectory() as d:
            pathlib.Path(d, "CABI.tla").write_text(SPEC.replace(old, new))
            pathlib.Path(d, "CABI.cfg").write_text(CFG)
            out = subprocess.run(
                [
                    "java",
                    "-cp",
                    jar,
                    "tlc2.TLC",
                    "-workers",
                    "auto",
                    "-config",
                    "CABI.cfg",
                    "CABI.tla",
                ],
                cwd=d,
                capture_output=True,
                text=True,
                check=False,
            ).stdout
        m = re.search(r"Invariant (\w+) is violated", out)
        got = m.group(1) if m else ("pass" if "No error has been found" in out else "?")
        mark = "ok" if got == inv else "MISSED"
        bad += got != inv
        print(f"mutant for {inv:18} -> {got:18} {mark}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
