"""Differential driver: every binding against the Rust core, over all of Unicode.

    python3 formal/bindings/difftest.py [--runners rust,py,c,node,ruby,java]
                                        [--cases tr,can,...] [--jobs 4] [--out FILE]

Run `bash formal/bindings/build.sh` first. Each runner prints one CRC per block of
4,096 inputs per case (see `rust_oracle/src/main.rs`); a block whose CRC differs from
the oracle's is re-run in `dump` mode on both sides and compared input by input. The
report (JSON) lists, per runner and case, how many inputs were compared, how many
differed, and the first differing inputs with both encodings.

Environment:
  DISARM_PYTHON   interpreter with the `disarm` Python package importable (for `py`)
  DISARM_JAVA_CP  extra classpath entries for the Java runner (default: built classes)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TARGET = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "target" / "formal-bindings"))
WORK = TARGET / "work"
CORPUS = WORK / "corpus.hex"
NSCALAR = 0x110000 - 0x800
MAX_EXAMPLES = 12
MAX_BLOCKS = 24  # blocks dumped input-by-input per case; the rest are counted only


def runner_cmd(name: str) -> tuple[list[str], dict[str, str]]:
    env = dict(os.environ)
    if name == "rust":
        return [str(TARGET / "release" / "disarm-binding-oracle")], env
    if name == "py":
        return [
            os.environ.get("DISARM_PYTHON", sys.executable),
            str(HERE / "runners" / "py_runner.py"),
        ], env
    if name == "c":
        env["DISARM_FFI"] = str(TARGET / "release" / "libdisarm_ffi.so")
        return [sys.executable, str(HERE / "runners" / "c_runner.py")], env
    if name == "node":
        return ["node", str(HERE / "runners" / "node_runner.cjs")], env
    if name == "ruby":
        return [
            "ruby",
            "-I",
            str(ROOT / "bindings" / "ruby" / "lib"),
            str(HERE / "runners" / "ruby_runner.rb"),
        ], env
    if name == "java":
        cp = os.pathsep.join([str(TARGET / "java-classes"), str(TARGET / "java-runner")])
        return [
            "java",
            "-Xss16m",
            f"-Ddisarm.native.lib={TARGET / 'release' / 'libdisarm_jni.so'}",
            "-cp",
            cp,
            "JavaRunner",
        ], env
    raise SystemExit(f"unknown runner {name}")


def run(name: str, args: list[str]) -> str:
    cmd, env = runner_cmd(name)
    p = subprocess.run(cmd + args, env=env, capture_output=True, text=True, check=False)
    if p.returncode != 0:
        raise RuntimeError(
            f"{name} {args[:1]} {args[2:3]} failed ({p.returncode}): {p.stderr[-2000:]}"
        )
    return p.stdout


def supported(name: str) -> list[str]:
    if name == "rust":
        return ALL_CASES
    return [c for c in run(name, ["list"]).strip().split(",") if c]


def crcs(name: str, cases: list[str]) -> dict[tuple[str, int], str]:
    out = run(name, ["crc", str(CORPUS), ",".join(cases)])
    res = {}
    for line in out.splitlines():
        case, block, crc, _n = line.split("\t")
        res[(case, int(block))] = crc
    return res


def dump(name: str, case: str, lo: int, hi: int) -> dict[int, str]:
    out = run(name, ["dump", str(CORPUS), case, str(lo), str(hi)])
    return {int(i): h for i, h in (line.split("\t") for line in out.splitlines())}


def decode_input(i: int, corpus: list[str]) -> str:
    if i < NSCALAR:
        return "U+%04X" % (i if i < 0xD800 else i + 0x800)
    s = corpus[i - NSCALAR]
    shown = (s[:120] + "...") if len(s) > 120 else s
    return f"corpus[{i - NSCALAR}] {shown}"


def same(runner: str, oracle_hex: str, got_hex: str) -> bool:
    if got_hex == oracle_hex or got_hex == "78":  # 'x' = input the binding cannot express
        return True
    if runner == "c":
        o, g = bytes.fromhex(oracle_hex), bytes.fromhex(got_hex)
        # C errors carry no kind: compare `e<kind>:` + message by message only.
        if o.startswith(b"e") and g.startswith(b"ec:"):
            return o.split(b":", 1)[1] == g[3:]
    return False


ALL_CASES = [
    "tr",
    "tr_iso9",
    "tr_gost",
    "tr_de",
    "tr_auto",
    "tr_uk",
    "tr_ja",
    "tr_bad",
    "nc_lat",
    "nc_lat_tr39",
    "nc_lat_pres",
    "nc_cyr",
    "nc_ara",
    "nc_heb",
    "sa",
    "fc",
    "cfs",
    "dj",
    "dj_sm",
    "re_empty",
    "re_sp",
    "cw",
    "scc",
    "szw",
    "sbd",
    "stg",
    "svs",
    "snc",
    "spua",
    "can",
    "can_tr39",
    "can_pres",
    "cans",
    "sfmt",
    "sobf",
    "sobf_tr39",
    "sk",
    "sk_de",
    "sok",
    "ck",
    "ck_iso",
    "skel",
    "skel_tr39",
    "nfc",
    "nfd",
    "nfkc",
    "nfkd",
    "isn_nfc",
    "mix",
    "bconf",
    "bctl",
    "susp",
    "ah",
    "ah_c",
    "glen",
    "gsplit",
    "gtrunc1",
    "tw",
    "tw_amb",
    "ial",
    "ds",
    "iscan",
    "mln",
    "mln_nofold",
    "sfn",
    "ia",
    "ha",
    "ed",
    "fu",
    "fuc",
    "rv_ru",
    "rv_el",
    "rv_uk",
    "slug",
    "zs",
    "zi",
    "isconf",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runners", default="py,c,node,ruby,java")
    ap.add_argument("--cases", default=",".join(ALL_CASES))
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--out", default=str(WORK / "difftest.json"))
    a = ap.parse_args()
    cases = a.cases.split(",")
    runners = a.runners.split(",")
    if not CORPUS.exists():
        WORK.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, str(HERE / "gen_corpus.py"), str(CORPUS)], check=True)
    with open(CORPUS, encoding="ascii") as f:
        corpus = [bytes.fromhex(line.strip()).decode("utf-8") for line in f]
    total = NSCALAR + len(corpus)

    pool = ThreadPoolExecutor(a.jobs)
    sup = {r: set(supported(r)) for r in runners}
    jobs = {("rust", c): pool.submit(crcs, "rust", [c]) for c in cases}
    for r in runners:
        for c in cases:
            if c in sup[r]:
                jobs[(r, c)] = pool.submit(crcs, r, [c])
    got = {k: f.result() for k, f in jobs.items()}

    report: dict = {"inputs": total, "scalars": NSCALAR, "corpus": len(corpus), "runners": {}}
    for r in runners:
        rr: dict = {"cases": {}, "unsupported": [c for c in cases if c not in sup[r]]}
        for c in cases:
            if c not in sup[r]:
                continue
            o, g = got[("rust", c)], got[(r, c)]
            bad_blocks = [b for (cc, b), crc in o.items() if g.get((cc, b)) != crc]
            diffs: list[int] = []
            ex = []
            examined = bad_blocks[:MAX_BLOCKS]
            for b in examined:
                lo, hi = b * 4096, min((b + 1) * 4096, total)
                od, gd = dump("rust", c, lo, hi), dump(r, c, lo, hi)
                for i in range(lo, hi):
                    if not same(r, od[i], gd.get(i, "")):
                        diffs.append(i)
                        if len(ex) < MAX_EXAMPLES:
                            ex.append(
                                {
                                    "input": decode_input(i, corpus),
                                    "rust": bytes.fromhex(od[i]).decode(
                                        "utf-8", "backslashreplace"
                                    )[:300],
                                    r: bytes.fromhex(gd.get(i, "")).decode(
                                        "utf-8", "backslashreplace"
                                    )[:300],
                                }
                            )
            rr["cases"][c] = {
                "compared": total,
                "blocks_differ": len(bad_blocks),
                "blocks_examined": len(examined),
                "differ": len(diffs),
                "examples": ex,
            }
            print(f"{r:5} {c:12} blocks={len(bad_blocks)} differ>={len(diffs)}", flush=True)
        report["runners"][r] = rr
    Path(a.out).write_text(json.dumps(report, indent=1, ensure_ascii=True))
    print("report:", a.out)


if __name__ == "__main__":
    main()
