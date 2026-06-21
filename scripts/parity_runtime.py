#!/usr/bin/env python3
"""Cross-binding runtime parity + doc-signature oracle for disarm (LOCAL ONLY).

Sibling to scripts/parity.py. parity.py checks the static *symbol surface*
(which op names exist in each binding). This adds the two checks parity.py
explicitly disclaims ("neither is runtime-introspected"):

  docs      Documented signature vs the actual export signature. Parses the
            `### `name(args)`` headings in docs/node/api.md and diffs them
            against `export function name(...)` in bindings/node/index.ts.
            Catches docs that invent, omit, or mis-mark a parameter — e.g. the
            historical `collapseWhitespace(text, options?)` drift (fixed in
            #466/#468), where the doc listed an `options` param the export never
            accepted.

  behavior  Runs the same battery of inputs through Python, Node, and Ruby and
            asserts identical output per (op, input). Catches cross-binding
            divergence — one binding raising where another returns, or returning
            a different string. (A core bug shared by all bindings is NOT a
            divergence; this measures binding-to-binding agreement, the stated
            parity property.)

NOT wired into CI by design. Run by hand from the repo root:

    python scripts/parity_runtime.py docs
    python scripts/parity_runtime.py behavior
    python scripts/parity_runtime.py all

Behavior mode needs: the Python `disarm` importable, `node` on PATH with the
Node binding built (bindings/node/*.node), and `ruby` on PATH with the Ruby gem
loadable. Any binding that is missing is skipped with a note. Exit status is
nonzero if any mismatch is found.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "generated" / "parity.yaml"
NODE_API_MD = ROOT / "docs" / "node" / "api.md"
NODE_INDEX_TS = ROOT / "bindings" / "node" / "index.ts"
DRIVERS = ROOT / "scripts" / "parity_drivers"


# --------------------------------------------------------------------------
# manifest (parity.yaml) — op id -> {lang: name|None}; alias rows are skipped
# --------------------------------------------------------------------------
def load_manifest() -> dict[str, dict[str, str | None]]:
    text = MANIFEST.read_text()
    ops: dict[str, dict[str, str | None]] = {}
    blocks = re.split(r"\n  - id: ", text)
    for blk in blocks[1:]:
        op_id = blk.splitlines()[0].strip()
        if re.search(r"^\s*alias_of:", blk, re.M):  # alias rows are not ops
            continue
        names: dict[str, str | None] = {}
        for lang in ("rust", "python", "ruby", "node"):
            m = re.search(rf"^\s*{lang}:\s*(.+)$", blk, re.M)
            val = m.group(1).strip() if m else "null"
            # `null` = gap; `{ provided_via: ... }` / `{ alias_of: ... }` are
            # not direct exports, so treat those non-symbol cells as absent.
            names[lang] = None if (val == "null" or val.startswith("{")) else val
        ops[op_id] = names
    return ops


# ==========================================================================
# docs mode: documented signature vs actual export signature (Node)
# ==========================================================================
def _split_params(s: str) -> list[str]:
    """Depth-aware comma split (params can hold {}, <>, (), [] and defaults)."""
    parts, depth, cur = [], 0, ""
    for c in s:
        if c in "([{<":
            depth += 1
        elif c in ")]}>":
            depth -= 1
        if c == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += c
    if cur.strip():
        parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def _doc_param(tok: str) -> tuple[str, bool]:
    tok = tok.strip()
    optional = tok.endswith("?")
    name = re.match(r"([A-Za-z0-9_]+)", tok)
    return (name.group(1) if name else tok.rstrip("?")), optional


def _ts_param(tok: str) -> tuple[str, bool]:
    name = re.match(r"\s*([A-Za-z0-9_]+)", tok)
    head = tok.split(":", 1)[0]  # part before the type annotation
    optional = ("?" in head) or ("=" in tok)  # `x?: T` or `x: T = default`
    return (name.group(1) if name else tok), optional


def doc_signatures(md: str) -> dict[str, str]:
    sigs: dict[str, str] = {}
    for line in md.splitlines():
        if not line.startswith("### "):
            continue
        for m in re.finditer(r"`([A-Za-z0-9_]+)\(([^)]*)\)`", line):
            sigs[m.group(1)] = m.group(2)
    return sigs


def ts_exports(ts: str) -> dict[str, str]:
    """name -> raw param string, paren-depth aware (handles multi-line sigs)."""
    out: dict[str, str] = {}
    for m in re.finditer(r"export function ([A-Za-z0-9_]+)\s*\(", ts):
        i, depth, buf = m.end(), 1, []
        while i < len(ts) and depth > 0:
            c = ts[i]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            if depth > 0:
                buf.append(c)
            i += 1
        out[m.group(1)] = "".join(buf)
    return out


def check_docs() -> list[str]:
    problems: list[str] = []
    docs = doc_signatures(NODE_API_MD.read_text())
    exports = ts_exports(NODE_INDEX_TS.read_text())

    for fn, dargs in sorted(docs.items()):
        if fn not in exports:
            problems.append(f"[doc-only]      `{fn}` is documented but there is no matching export")
            continue
        dparams = [_doc_param(t) for t in _split_params(dargs)]
        tparams = [_ts_param(t) for t in _split_params(exports[fn])]
        dnames = {n for n, _ in dparams}
        tnames = {n for n, _ in tparams}
        dopt = dict(dparams)
        topt = dict(tparams)
        for n, _ in dparams:
            if n not in tnames:
                problems.append(
                    f"[extra-doc]     `{fn}`: doc lists parameter `{n}` that the export does not accept"
                )
        for n, opt in tparams:
            if n not in dnames and not opt:
                problems.append(
                    f"[missing-doc]   `{fn}`: export requires `{n}` but the doc omits it"
                )
        for n in sorted(dnames & tnames):
            if dopt[n] != topt[n]:
                problems.append(
                    f"[optionality]   `{fn}`: `{n}` optional={dopt[n]} in doc but optional={topt[n]} in export"
                )

    for fn in sorted(exports):
        if fn not in docs:
            # Coverage gap, not a doc lie: deprecated aliases are intentionally
            # undocumented. Informational so it does not count as a defect.
            problems.append(
                f"[info] export `{fn}` not documented in api.md (e.g. deprecated alias)"
            )
    return problems


# ==========================================================================
# behavior mode: same input through Python / Node / Ruby, compare outputs
# ==========================================================================
# Adversarial-but-JSON-bridgeable battery (no lone surrogates: JSON can't carry
# them; that contract gap is M-1 and needs a binding-native probe, out of scope
# here). Valid scalar values only.
BATTERY = [
    "",
    " ",
    "Hello café",
    "CAFÉ",
    "２０２４",
    "ﬁ",
    "Ⅻ",
    "½",
    "../../etc/passwd",
    "_\u00b7",
    "report...",
    "CON.txt",
    "a\tb",
    "a b c",
    "\u202eabc",
    "e" + "\u0301" * 6,
    "\U0001f600",
    "\U0001f1e9\U0001f1ea",
    "p\u0430yp\u0430l",
    "ＣＯＮ",
    "\ufeffbom",
    "a\u200bb",
    "\u202e",
    "Ａｄｍｉｎ",
    "Москва",
    "東京",
    "caf\u00e9\u0301",
    "\U0001d54a\U0001d557",
    "a.b.c",
    "...",
]
BENIGN = "Hello café 漢"  # used to detect simple single-text ops


def py_call(fn, s):
    try:
        r = fn(s)
    except Exception as e:  # noqa: BLE001
        return ("ERR", type(e).__name__)
    if isinstance(r, bool) or isinstance(r, int) or isinstance(r, str):
        return ("OK", r)
    if isinstance(r, list) and all(isinstance(x, (str, int, bool)) for x in r):
        return ("OK", r)
    return None  # complex return type -> not comparable here


def normalize_cell(cell):
    """driver/python cell -> ('OK', value) | ('ERR',). Error messages differ by
    language and are not compared; only OK/ERR status and OK values are."""
    if cell is None:
        return None
    if isinstance(cell, tuple):  # python side
        return ("OK", cell[1]) if cell[0] == "OK" else ("ERR",)
    if "e" in cell:  # driver side
        return ("ERR",)
    return ("OK", cell["v"])


def run_driver(cmd, ops_pairs, inputs):
    job = {"inputs": inputs, "ops": ops_pairs}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(job, f)
        jobfile = f.name
    try:
        proc = subprocess.run(
            cmd + [jobfile, str(ROOT)],
            capture_output=True,
            text=True,
            timeout=120,
        )
    finally:
        Path(jobfile).unlink(missing_ok=True)
    if proc.returncode != 0:
        return None, f"driver exit {proc.returncode}: {proc.stderr.strip()[:200]}"
    try:
        return json.loads(proc.stdout), None
    except json.JSONDecodeError as e:
        return None, f"bad driver JSON: {e}; stderr={proc.stderr.strip()[:200]}"


def check_behavior() -> list[str]:
    try:
        import disarm  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        return [f"[skip] cannot import python disarm: {e}"]

    manifest = load_manifest()

    # simple ops = callable as fn(text) returning a scalar/list in Python
    simple = []
    for op, names in manifest.items():
        pyname = names.get("python")
        if not pyname:
            continue
        fn = getattr(disarm, pyname, None)
        if not callable(fn):
            continue
        probe = py_call(fn, BENIGN)
        if probe is not None and probe[0] == "OK":  # benign input must succeed + be comparable
            simple.append(op)

    problems: list[str] = []

    # Python results
    py = {
        op: [py_call(getattr(disarm, manifest[op]["python"]), s) for s in BATTERY] for op in simple
    }

    # Node + Ruby results via drivers
    node_ok = ruby_ok = False
    node_res = ruby_res = {}
    node_pairs = [[op, manifest[op]["node"]] for op in simple if manifest[op]["node"]]
    ruby_pairs = [[op, manifest[op]["ruby"]] for op in simple if manifest[op]["ruby"]]

    node_res, nerr = run_driver(["node", str(DRIVERS / "node_driver.js")], node_pairs, BATTERY)
    if node_res is None:
        problems.append(f"[skip] node driver: {nerr}")
    else:
        node_ok = True
    ruby_res, rerr = run_driver(["ruby", str(DRIVERS / "ruby_driver.rb")], ruby_pairs, BATTERY)
    if ruby_res is None:
        problems.append(f"[skip] ruby driver: {rerr}")
    else:
        ruby_ok = True

    compared = 0
    for op in simple:
        for i, s in enumerate(BATTERY):
            cells = {"python": normalize_cell(py[op][i])}
            if node_ok and op in (node_res or {}):
                cells["node"] = normalize_cell(node_res[op][i])
            if ruby_ok and op in (ruby_res or {}):
                cells["ruby"] = normalize_cell(ruby_res[op][i])
            cells = {k: v for k, v in cells.items() if v is not None}
            if len(cells) < 2:
                continue
            compared += 1
            distinct = {json.dumps(v, ensure_ascii=False) for v in cells.values()}
            if len(distinct) > 1:
                desc = "  ".join(
                    f"{k}={v[0] if v == ('ERR',) else repr(v[1])}" for k, v in cells.items()
                )
                problems.append(f"[divergence]    {op}({s!r}):  {desc}")

    problems.append(
        f"[info] compared {compared} (op,input) cells across {len(simple)} ops; "
        f"node={'on' if node_ok else 'off'} ruby={'on' if ruby_ok else 'off'}"
    )
    return problems


# ==========================================================================
def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode not in ("docs", "behavior", "all"):
        print(__doc__)
        return 2

    real = 0
    if mode in ("docs", "all"):
        print("=== doc-signature vs export (Node) ===")
        probs = check_docs()
        mism = [p for p in probs if not p.startswith("[info]")]
        for p in probs:
            print(" " + p)
        print(f"  -> {len(mism)} signature finding(s)\n")
        real += len(mism)

    if mode in ("behavior", "all"):
        print("=== cross-binding behavioral parity (Python/Node/Ruby) ===")
        probs = check_behavior()
        div = [p for p in probs if p.startswith("[divergence]")]
        for p in probs:
            print(" " + p)
        print(f"  -> {len(div)} behavioral divergence(s)\n")
        real += len(div)

    print(f"TOTAL findings: {real}")
    return 1 if real else 0


if __name__ == "__main__":
    raise SystemExit(main())
