#!/usr/bin/env python3
"""Differential test: the Lean model of the presets, key builders and profiles against the
real library.

    python3 scripts/difftest.py [--exhaustive N] [--small N] [--random N] [--seed S]

Needs the driver built (`lake build` in `formal/lean/Presets`) and an importable `disarm`.
Words are drawn from the model's input alphabet (`inputAlphabet` in Presets/Tables.lean):

* every word of length <= --exhaustive over the whole alphabet;
* every word of length <= --small over SMALL, the sub-alphabet that carries the findings;
* --random words of length <= 12 over the whole alphabet.

Each word goes through every surface the driver names (`Presets/Surfaces.lean`): the seven
builders under each of the three digit policies, `strip_format`, `ml_normalize` both ways,
the eight profiles (three of them also under `tr39`), and 17 single steps that have a public
function of their own. Code points are compared exactly. Exit status 0 only when every
comparison agrees.

The driver also prints each proposed fix (`Presets/Fixes.lean`, named `fixed:<surface>`).
Those are not expected to agree: the report counts, per fix, the words whose output it
moves, and how many of those are words on which the library is not a fixed point today.
"""

from __future__ import annotations

import argparse
import functools
import itertools
import pathlib
import random
import re
import subprocess
import sys

import disarm

HERE = pathlib.Path(__file__).resolve().parent.parent
EXE = HERE / ".lake" / "build" / "bin" / "difftest"
TABLES = HERE / "Presets" / "Tables.lean"

#: Carries every finding: I, 1, |, space, BS, the three marks, y-acute, upsilon with
#: dialytika and tonos, cent, =, Latin VY and vy, the lateral click, A with macron, ZWSP,
#: CGJ, PUA, NUL, the two jamo, and for Finding 8 g with cedilla and a third mark above.
SMALL = [
    0x49,
    0x31,
    0x7C,
    0x20,
    0x8,
    0x0,
    0x301,
    0x308,
    0x338,
    0xFD,
    0x3B0,
    0xA2,
    0x3D,
    0xA760,
    0xA761,
    0x1C1,
    0x100,
    0x200B,
    0x34F,
    0xE000,
    0x61,
    0x1100,
    0x1161,
    0x123,
    0x303,
]


def alphabet() -> list[int]:
    m = re.search(r"def inputAlphabet : List Nat := \[([^\]]*)\]", TABLES.read_text())
    assert m, "inputAlphabet not found"
    return [int(x.strip(), 16) for x in m.group(1).split(",")]


def library_surfaces() -> dict:
    s = {}
    for pol in ("numeric", "tr39", "preserve"):
        s[f"canonicalize@{pol}"] = functools.partial(disarm.canonicalize, digit_policy=pol)
        s[f"canonicalize_strict@{pol}"] = functools.partial(
            disarm.canonicalize_strict, digit_policy=pol
        )
        s[f"strip_obfuscation@{pol}"] = functools.partial(
            disarm.strip_obfuscation, digit_policy=pol
        )
        s[f"search_key@{pol}"] = functools.partial(disarm.search_key, digit_policy=pol)
        s[f"catalog_key@{pol}"] = functools.partial(disarm.catalog_key, digit_policy=pol)
        s[f"sort_key@{pol}"] = functools.partial(disarm.sort_key, digit_policy=pol)
        s[f"skeleton_key@{pol}"] = functools.partial(disarm.skeleton_key, digit_policy=pol)
    s["strip_format"] = disarm.strip_format
    s["ml_normalize"] = disarm.ml_normalize
    s["ml_normalize@nofold"] = functools.partial(disarm.ml_normalize, fold_case=False)
    for p in disarm.list_profiles():
        s[f"profile:{p}"] = disarm.get_pipeline(p)
    for p in ("llm_guardrail", "normalize_web_input", "library_catalog_key_eu"):
        s[f"profile:{p}@tr39"] = disarm.get_pipeline(p, digit_policy="tr39")
    s["step:nfc"] = functools.partial(disarm.normalize, form="NFC")
    s["step:nfkc"] = functools.partial(disarm.normalize, form="NFKC")
    s["step:nfd"] = functools.partial(disarm.normalize, form="NFD")
    s["step:fold_case"] = disarm.fold_case
    s["step:strip_accents"] = disarm.strip_accents
    s["step:strip_bidi"] = disarm.strip_bidi
    s["step:strip_zero_width"] = disarm.strip_zero_width_chars
    s["step:strip_control"] = disarm.strip_control_chars
    s["step:collapse_ws"] = disarm.collapse_whitespace
    s["step:zalgo3"] = functools.partial(disarm.strip_zalgo, max_marks=3)
    s["step:zalgo0"] = functools.partial(disarm.strip_zalgo, max_marks=0)
    s["step:strip_pua"] = disarm.strip_pua
    s["step:conf_public@numeric"] = disarm.normalize_confusables
    s["step:conf_public@tr39"] = functools.partial(
        disarm.normalize_confusables, digit_policy="tr39"
    )
    s["step:resolve_deletions"] = disarm.TextPipeline(resolve_deletions=True)
    s["step:translit_preserve"] = functools.partial(disarm.transliterate, errors="preserve")
    s["step:translit_ignore"] = functools.partial(disarm.transliterate, errors="ignore")
    return s


def words(args) -> list[tuple[int, ...]]:
    alpha = alphabet()
    out: list[tuple[int, ...]] = []
    for n in range(args.exhaustive + 1):
        out.extend(itertools.product(alpha, repeat=n))
    for n in range(args.exhaustive + 1, args.small + 1):
        out.extend(itertools.product(SMALL, repeat=n))
    rng = random.Random(args.seed)
    for _ in range(args.random):
        out.append(tuple(rng.choice(alpha) for _ in range(rng.randint(0, 12))))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exhaustive", type=int, default=3)
    ap.add_argument("--small", type=int, default=4)
    ap.add_argument("--random", type=int, default=100_000)
    ap.add_argument("--seed", type=int, default=1016)
    args = ap.parse_args()

    all_names = subprocess.run(
        [str(EXE), "names"], capture_output=True, text=True, check=True
    ).stdout.split()
    lib = library_surfaces()
    names = [n for n in all_names if not n.startswith("fixed:")]
    missing = [n for n in names if n not in lib]
    assert not missing, missing

    ws = words(args)
    lines = [" ".join(f"{c:X}" for c in w) for w in ws]
    proc = subprocess.run(
        [str(EXE)], input="\n".join(lines) + "\n", capture_output=True, text=True, check=True
    )
    answers = proc.stdout.removesuffix("\n").split("\n")
    compared = agree = 0
    failures: dict[str, list] = {}
    moved: dict[str, list[int]] = {}
    for w, ans in zip(ws, answers, strict=True):
        text = "".join(map(chr, w))
        model = ans.split(" | ")
        assert len(model) == len(all_names), (w, ans)
        real_of: dict[str, str] = {}
        for n, m in zip(all_names, model, strict=True):
            want = "".join(chr(int(x, 16)) for x in m.split())
            if n.startswith("fixed:"):
                base = n[len("fixed:") :]
                real = real_of[base]
                tally = moved.setdefault(base, [0, 0])
                if want != real:
                    tally[0] += 1
                    if lib[base](real) != real:
                        tally[1] += 1
                continue
            real = lib[n](text)
            real_of[n] = real
            compared += 1
            if want == real:
                agree += 1
            else:
                failures.setdefault(n, []).append((text, real, want))

    print(f"words: {len(ws)}  surfaces: {len(names)}  comparisons: {compared}")
    print(f"model == library: {agree}/{compared}")
    for n, v in failures.items():
        print(f"DISAGREE {n}: {len(v)}")
        for text, real, want in v[:5]:
            print(f"    {ascii(text)}  library={ascii(real)}  model={ascii(want)}")
    print(
        "proposed fixes: words whose output moves (of which the library is not a fixed point today)"
    )
    for n, (m, nonidem) in moved.items():
        print(f"    {n:<40} {m:>8} ({nonidem})")
    return 0 if agree == compared else 1


if __name__ == "__main__":
    sys.exit(main())
