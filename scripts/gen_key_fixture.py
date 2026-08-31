#!/usr/bin/env python3
"""Regenerate the golden key-stability fixture (#644).

`search_key`, `catalog_key` and `sort_key` exist to produce a value a consumer
**stores** and compares later, so a change to their output is a reindex event on
somebody's production data. `docs/RUST_API.md` states the contract — *a patch
release never changes key-builder output; a minor release may* — and until this
fixture existed that contract was held by review rather than by a gate.

Run this **only when a key change is intended**. It rewrites the expected values,
so running it to make a red test go green is exactly the mistake the fixture is
here to prevent. The correct sequence is:

1. `tests/test_key_stability.py` fails and prints what moved.
2. Read the diff. Decide whether the movement is right.
3. If it is, run this, commit the regenerated fixture in the same change, and
   write it up in the release's *Upgrade notes* — which is what `0.14.0` did for
   #602.
4. The release that carries it is a **minor**, per `RELEASING.md`.

Usage:
    python scripts/gen_key_fixture.py            # rewrite the fixture
    python scripts/gen_key_fixture.py --check    # exit 1 if it is out of date
"""

from __future__ import annotations

import argparse
import gzip
import sys
from pathlib import Path

import disarm

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "key_stability"
CORPUS = FIXTURE_DIR / "corpus.txt"
GOLDEN = FIXTURE_DIR / "golden_keys.tsv.gz"

#: Every function whose output a consumer might store. The three key builders are
#: the reason this exists; the other four are here because they share the table
#: layers underneath, so a table change that moves one usually moves several, and
#: seeing which is how you tell a targeted fix from a broad one.
FUNCTIONS = (
    "search_key",
    "catalog_key",
    "sort_key",
    "canonicalize",
    "canonicalize_strict",
    "strip_obfuscation",
    "normalize_confusables",
    "fold_case",
)

#: A value containing a tab or newline would break the TSV; neither appears in the
#: corpus today, and escaping rather than rejecting keeps that from becoming a
#: silent truncation if one ever does.
_ESCAPES = ((("\\"), r"\\"), ("\t", r"\t"), ("\n", r"\n"), ("\r", r"\r"))


def escape(value: str) -> str:
    for raw, escaped in _ESCAPES:
        value = value.replace(raw, escaped)
    return value


def unescape(value: str) -> str:
    out, i = [], 0
    while i < len(value):
        if value[i] == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            out.append({"\\": "\\", "t": "\t", "n": "\n", "r": "\r"}.get(nxt, "\\" + nxt))
            i += 2
        else:
            out.append(value[i])
            i += 1
    return "".join(out)


def read_corpus() -> list[str]:
    return [line for line in CORPUS.read_text(encoding="utf-8").split("\n") if line]


def compute(rows: list[str]) -> str:
    """The fixture body: a header, then one TSV line per corpus row."""
    functions = [(name, getattr(disarm, name)) for name in FUNCTIONS]
    out = [
        "# disarm golden key fixture — see tests/fixtures/key_stability/README.md",
        f"# generated against disarm {disarm.__version__}",
        f"# rows = {len(rows)}",
        # #645: the schema counter travels with the data it describes. `KEY_SCHEMA_VERSION`
        # is only worth anything if regenerating this fixture without bumping it is caught,
        # and that is exactly how a counter like this goes stale. The gate lives in
        # `tests/test_key_stability.py`.
        f"# key_schema_version = {disarm.KEY_SCHEMA_VERSION}",
        "# columns: input\t" + "\t".join(FUNCTIONS),
    ]
    for row in rows:
        values = []
        for _, function in functions:
            try:
                values.append(function(row))
            except Exception as exc:  # noqa: BLE001 — the error IS the expected value
                values.append(f"<ERR:{type(exc).__name__}>")
        out.append("\t".join([escape(row), *(escape(v) for v in values)]))
    return "\n".join(out) + "\n"


def read_golden() -> str:
    with gzip.open(GOLDEN, "rt", encoding="utf-8") as handle:
        return handle.read()


def write_golden(body: str) -> None:
    # mtime=0 so the bytes depend only on the content. The gate compares decoded
    # text rather than bytes, so a zlib difference between machines cannot cause a
    # false failure — this only keeps a regeneration from showing a spurious diff.
    with gzip.GzipFile(GOLDEN, "wb", compresslevel=9, mtime=0) as handle:
        handle.write(body.encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if the fixture is out of date")
    args = parser.parse_args()

    rows = read_corpus()
    body = compute(rows)

    if args.check:
        if not GOLDEN.exists():
            print(f"error: {GOLDEN} is missing; run this script without --check", file=sys.stderr)
            return 1
        if read_golden() == body:
            print(f"fixture is up to date ({len(rows)} rows, disarm {disarm.__version__})")
            return 0
        print(
            "error: the golden key fixture is out of date.\n"
            "Run tests/test_key_stability.py for the per-function report of what moved.",
            file=sys.stderr,
        )
        return 1

    write_golden(body)
    print(
        f"wrote {GOLDEN.relative_to(ROOT)}  rows={len(rows)}  "
        f"functions={len(FUNCTIONS)}  disarm={disarm.__version__}"
    )
    print("Commit this with the change that moved the keys, and write it up in Upgrade notes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
