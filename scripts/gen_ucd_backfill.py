#!/usr/bin/env python3
"""Generate `data/ucd_backfill.tsv` — UCD properties for code points an older
interpreter cannot classify.

`scripts/gen_confusables.py` classifies every code point in `data/confusables.txt`
through `unicodedata`, whose table is whatever the running Python ships. When that table
predates the data, the code point reads as `Cn` and the generator's rules cannot fire: a
digit is not recognised and folds to a look-alike letter (#439), an uppercase source is
not reconciled and keeps TR39's lowercase prototype (#734). The run is wrong, and quiet.

Requiring the matching interpreter is one answer, but it pins table generation to a
CPython alpha for as long as the data leads the release cycle. This file is the other:
carry the properties the older table lacks, and let any supported interpreter reproduce
the same output.

Only code points that a *baseline* interpreter cannot classify are included. Anything it
already knows is left to `unicodedata`, which stays authoritative — the generator consults
this file only on a `Cn` reading, so a newer interpreter can never be overridden by it.

Run under an interpreter whose UCD matches `gen_confusables.DATA_UNICODE_VERSION`:

    uv run --python 3.15 python scripts/gen_ucd_backfill.py
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFUSABLES = ROOT / "data" / "confusables.txt"
OUT = ROOT / "data" / "ucd_backfill.tsv"

#: The oldest interpreter table the backfill must lift to the data version. Every code
#: point unassigned in this UCD is written out; everything else is left to the running
#: `unicodedata`. CPython 3.13 ships 15.1.0 and is what this repo's venv and CI run.
BASELINE_UCD = "15.1.0"
#: The interpreter that ships it, probed directly — see the note in `main`.
BASELINE_PYTHON = "3.13"


def _encode_seq(decomposed: str, source: str) -> str:
    """`-` when the code point decomposes to itself, else space-separated code points."""
    if decomposed == source:
        return "-"
    return " ".join(f"{ord(c):04X}" for c in decomposed)


def referenced_codepoints() -> set[int]:
    """Every code point confusables.txt mentions, on either side of a mapping.

    Targets count: `fix_case_mismatch` inspects the target's category too, so a target
    the interpreter cannot classify is as damaging as a source it cannot classify.
    """
    text = CONFUSABLES.read_text(encoding="utf-8")
    sources = {int(m.group(1), 16) for m in re.finditer(r"^([0-9A-F]{4,6})\s*;", text, re.M)}
    targets: set[int] = set()
    for m in re.finditer(r"^[0-9A-F]{4,6}\s*;\s*([0-9A-F ]+);", text, re.M):
        targets |= {int(x, 16) for x in m.group(1).split()}
    return sources | targets


def main() -> None:
    from gen_confusables import DATA_UNICODE_VERSION  # noqa: PLC0415

    if unicodedata.unidata_version != DATA_UNICODE_VERSION:
        sys.exit(
            f"gen_ucd_backfill must run under a UCD matching the data "
            f"({DATA_UNICODE_VERSION}); this Python ships "
            f"{unicodedata.unidata_version}. Anything else writes a backfill that is "
            f"itself incomplete."
        )

    # Which code points the baseline cannot classify is a property of the *baseline's*
    # UCD, and this interpreter knows everything, so it cannot answer that by itself.
    # Ask the baseline interpreter directly rather than inferring it: `unicodedata`
    # exposes no age API, and a guess here silently produces an incomplete backfill,
    # which is the same class of quiet wrongness this file exists to remove.
    probe = (
        "import sys,unicodedata;"
        "cps=[int(x,16) for x in sys.argv[1:]];"
        "print(' '.join(f'{c:04X}' for c in cps "
        "if unicodedata.category(chr(c))=='Cn'))"
    )
    referenced = sorted(referenced_codepoints())
    proc = subprocess.run(
        ["uv", "run", "--python", BASELINE_PYTHON, "--no-project", "python", "-c", probe]
        + [f"{cp:04X}" for cp in referenced],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        sys.exit(f"could not probe the baseline interpreter ({BASELINE_PYTHON}):\n{proc.stderr}")
    unknown = [int(tok, 16) for tok in proc.stdout.split()]

    rows = []
    for cp in unknown:
        ch = chr(cp)
        if unicodedata.category(ch) == "Cn":
            sys.exit(
                f"U+{cp:04X} is unassigned in this interpreter's UCD "
                f"({unicodedata.unidata_version}) too — the backfill cannot describe it."
            )
        nfkc = unicodedata.normalize("NFKC", ch)
        nfd = unicodedata.normalize("NFD", ch)
        digit = unicodedata.digit(ch, None)
        rows.append(
            (
                f"{cp:04X}",
                unicodedata.category(ch),
                "-" if digit is None else str(digit),
                _encode_seq(nfkc, ch),
                _encode_seq(nfd, ch),
                unicodedata.name(ch, ""),
            )
        )

    header = [
        "# UCD properties for code points an older interpreter cannot classify.",
        "#",
        "# scripts/gen_confusables.py reads every code point in data/confusables.txt through",
        "# `unicodedata`, whose table is whatever the running Python ships. Under a table that",
        "# predates the data a code point reads as `Cn`, the generator's rules cannot fire, and",
        "# the output is wrong without being loud: a digit folds to a look-alike letter (#439),",
        "# an uppercase source keeps TR39's lowercase prototype (#734).",
        "#",
        "# The generator prefers `unicodedata` and consults this file only on a `Cn` reading, so",
        "# a newer interpreter is always authoritative and this file can never mask it.",
        "#",
        f"# Contains every referenced code point that CPython {BASELINE_PYTHON} (UCD "
        f"{BASELINE_UCD}) reports as unassigned.",
        f"# Generated from Unicode {unicodedata.unidata_version} by CPython "
        f"{sys.version.split()[0]}.",
        "# Regenerate with: uv run --python 3.15 python scripts/gen_ucd_backfill.py",
        "#",
        "# codepoint\tcategory\tdigit\tnfkc\tnfd\tname",
    ]
    OUT.write_text("\n".join(header + ["\t".join(r) for r in rows]) + "\n", encoding="utf-8")
    print(f"  → ucd backfill: {len(rows)} code points → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "scripts"))
    main()
