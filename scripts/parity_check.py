#!/usr/bin/env python3
"""Parity gate: diff the manifest's declared intent against each binding's LIVE
public surface (produced by tools/introspect/* against the *built* module).
Exits non-zero on drift. No source-scraping — reality comes from the live module.

Usage:
  # in CI, after building each binding:
  python tools/introspect/python_surface.py        > surfaces/python.json
  node   tools/introspect/node_surface.mjs         > surfaces/node.json
  ruby   tools/introspect/ruby_surface.rb          > surfaces/ruby.json
  cargo  public-api --simplified | ... > surfaces/rust.json
  python scripts/parity_check.py generated/parity.yaml surfaces/
"""

import sys, json, re, pathlib

LANGS = ["rust", "python", "ruby", "node"]


def load_manifest(path):
    """Tiny parser for the seed format. Cell = name | {provided_via:..} | {alias_of:..} | null."""
    ops = {}
    cur = None
    cells = False
    for ln in pathlib.Path(path).read_text().splitlines():
        m = re.match(r"\s*- id:\s*(\S+)", ln)
        if m:
            cur = m.group(1)
            ops[cur] = {}
            cells = False
            continue
        if re.match(r"\s*names:", ln):
            cells = True
            continue
        if cells and cur:
            m = re.match(r"\s*(rust|python|ruby|node):\s*(.+)", ln)
            if m:
                lang, val = m.group(1), m.group(2).strip()
                if val == "null":
                    ops[cur][lang] = None
                elif val.startswith("{"):
                    ops[cur][lang] = ("via",)  # provided_via/alias_of: not a live symbol
                else:
                    ops[cur][lang] = val
    return ops


def main(manifest, surfdir):
    ops = load_manifest(manifest)
    surf = {
        l: set(json.loads((pathlib.Path(surfdir) / f"{l}.json").read_text()))
        for l in LANGS
        if (pathlib.Path(surfdir) / f"{l}.json").exists()
    }
    fail = False
    for l in [x for x in LANGS if x in surf]:
        declared = {
            c: v
            for c, (cells) in ops.items()
            for ll, v in [(l, ops[c].get(l))]
            if isinstance(v, str)
        }
        # ruby predicates: respond_to? uses bare name; compare on rstrip('?!')
        live = surf[l]
        live_norm = {s.rstrip("?!") for s in live}
        drift = [
            (c, n) for c, n in declared.items() if n not in live and n.rstrip("?!") not in live_norm
        ]
        declared_names = {n for n in declared.values()} | {
            n.rstrip("?!") for n in declared.values()
        }
        undeclared = sorted(
            s for s in live if s not in declared_names and s.rstrip("?!") not in declared_names
        )
        print(
            f"[{l}] declared={len(declared)} live={len(live)} "
            f"drift={len(drift)} undeclared={len(undeclared)}"
        )
        for c, n in drift:
            print(f"   DRIFT  {l}: manifest declares `{n}` (op {c}) but live module lacks it")
            fail = True
        for s in undeclared:
            print(f"   UNDECL {l}: live export `{s}` not in manifest")
            fail = True
    if not surf:
        print("no surface JSONs found — run the introspect emitters first")
        return 2
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(
        main(
            sys.argv[1] if len(sys.argv) > 1 else "generated/parity.yaml",
            sys.argv[2] if len(sys.argv) > 2 else "surfaces",
        )
    )
