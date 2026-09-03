#!/usr/bin/env python3
"""Measure paultendo's confusable-vision discovery sets against disarm, and admit a tranche.

`data/confusables_vision.tsv` is generated from this script's output, not transcribed: the
header quotes the band table it prints, and `tests/test_vision_confusables.py` re-derives
the admitted rows from the same rule. Run it against the two published sets (#738):

    python scripts/measure_confusable_vision.py --dir <dir with the three JSON files>
    python scripts/measure_confusable_vision.py --dir <dir> --check data/confusables_vision.tsv

The directory holds ``candidate-discoveries.json`` (the 793 novel Latin-target pairs),
``m2b-verification-report.json`` (the CJK/Hangul scan) and ``IdentifierStatus.txt``, all
from https://github.com/paultendo/confusable-vision (code MIT, datasets CC-BY-4.0).

**Coverage is measured through `canonicalize`, not the bare fold.** Every preset runs NFKC
before the confusable step, and the strongest multi-font Latin-target hits in the set are
modifier, subscript and superscript letters that NFKC already folds; the bare fold would
report them as gaps. 96 of the 793 are covered that way.

**The admission rule** — measured-visual evidence stands in for TR39's judgement only where
it is strong and where folding is the right answer:

* ``validFontCount >= 5`` — the pair renders alike in at least five fonts, not one. The
  single-font hits at the top of the set are Nabataean, Duployan, Cuneiform and
  hieroglyph letters seen in one fallback font.
* ``meanSsim >= 0.85``.
* the source is a letter (``L*``) or a letter-number (``Nl``); the target is one ASCII
  letter. A numeric symbol (``No``) folded to a letter under the default policy is what
  `digit_policy` exists to refuse, and a digit target is refused for the same reason.
* the source is not an *accented form of its target*: if ``NFD(source)`` begins with the
  target letter, the pair is an accent (``ḷ`` → ``l`` agrees in 57 fonts), and a security
  fold that merges accents is the over-normalization #731 and #836 price.
* not already covered — by the rest of disarm. On a build that already carries this
  file, its own rows read as covered and the rule would admit the next-best target for the
  same source, so the file's sources are excluded from the coverage test.

Under that rule the two published sets admit two rows. The rule is the deliverable; the
threshold for the unpublished RaySpace superset and the IDN-filtered subset is #738's
open decision.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

import disarm

MIN_FONTS = 5
VISION_TSV = Path(__file__).resolve().parent.parent / "data" / "confusables_vision.tsv"
MIN_SSIM = 0.85
BANDS = (0.97, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70)
FONT_STEPS = (1, 2, 3, 5, 10)


def vision_sources(path: Path = VISION_TSV) -> set[int]:
    """The sources this file already ships, so coverage is measured without them."""
    if not path.is_file():
        return set()
    return {int(line.split("\t")[0], 16) for line in data_rows(path)}


def load_pairs(directory: Path) -> list[dict]:
    cand = json.loads((directory / "candidate-discoveries.json").read_text(encoding="utf-8"))[
        "pairs"
    ]
    m2b = json.loads((directory / "m2b-verification-report.json").read_text(encoding="utf-8"))[
        "topPairsBySsim"
    ]
    rows = []
    for origin, pairs in (("candidate-discoveries", cand), ("m2b-verification-report", m2b)):
        for p in pairs:
            cp = int(p["sourceCodepoint"][2:], 16)
            summary = p.get("summary", p)
            rows.append(
                {
                    "origin": origin,
                    "cp": cp,
                    "src": chr(cp),
                    "tgt": p["target"],
                    "ssim": float(summary["meanSsim"]),
                    "fonts": int(summary.get("validFontCount", len(p.get("fonts", [])))),
                    "cat": unicodedata.category(chr(cp)),
                    "name": unicodedata.name(chr(cp), "?"),
                }
            )
    shipped = vision_sources()
    for r in rows:
        r["covered"] = r["cp"] not in shipped and disarm.canonicalize(r["src"]) == r["tgt"]
    return rows


def is_accent_of_target(src: str, tgt: str) -> bool:
    return unicodedata.normalize("NFD", src).startswith(tgt)


def admitted(rows: list[dict]) -> list[dict]:
    best: dict[int, dict] = {}
    for r in rows:
        ok = (
            not r["covered"]
            and r["fonts"] >= MIN_FONTS
            and r["ssim"] >= MIN_SSIM
            and (r["cat"].startswith("L") or r["cat"] == "Nl")
            and len(r["tgt"]) == 1
            and r["tgt"].isascii()
            and r["tgt"].isalpha()
            and not is_accent_of_target(r["src"], r["tgt"])
        )
        if ok and (r["cp"] not in best or r["ssim"] > best[r["cp"]]["ssim"]):
            best[r["cp"]] = r
    return sorted(best.values(), key=lambda r: -r["ssim"])


def band_table(rows: list[dict]) -> str:
    cands = [r for r in rows if r["origin"] == "candidate-discoveries"]
    lines = [f"{'band':8}" + "".join(f"{'fonts>=' + str(n):>10}" for n in FONT_STEPS)]
    for b in BANDS:
        lines.append(
            f">={b:<6}"
            + "".join(
                f"{sum(1 for r in cands if not r['covered'] and r['ssim'] >= b and r['fonts'] >= n):>10}"
                for n in FONT_STEPS
            )
        )
    return "\n".join(lines)


def tsv_rows(rows: list[dict]) -> list[str]:
    return [
        f"{r['cp']:04X}\t{r['tgt']}\t-\t{r['ssim']:.3f}\t{r['fonts']}\t{r['name']} -> {r['tgt']} ({r['origin']}, {r['fonts']} fonts)"
        for r in rows
    ]


def data_rows(path: Path) -> list[str]:
    return [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line and not line.lstrip().startswith("#")
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--dir", type=Path, required=True, help="directory holding the confusable-vision JSON files"
    )
    ap.add_argument(
        "--check", type=Path, help="assert this TSV's rows are exactly the admitted ones"
    )
    args = ap.parse_args()
    rows = load_pairs(args.dir)
    cands = [r for r in rows if r["origin"] == "candidate-discoveries"]
    print(
        f"candidates: {len(cands)}; covered by canonicalize (NFKC + fold): {sum(r['covered'] for r in cands)}"
    )
    print("not covered, by meanSsim band x validFontCount >= n:")
    print(band_table(rows))
    adm = admitted(rows)
    print(
        f"\nadmitted under fonts >= {MIN_FONTS}, meanSsim >= {MIN_SSIM}, letters, no accents: {len(adm)}"
    )
    for line in tsv_rows(adm):
        print("  " + line)
    if args.check:
        want = [line.split("\t")[:2] for line in tsv_rows(adm)]
        have = [line.split("\t")[:2] for line in data_rows(args.check)]
        if want != have:
            print(
                f"\n{args.check}: rows differ from the rule's output:\n  file: {have}\n  rule: {want}",
                file=sys.stderr,
            )
            return 1
        print(f"\n{args.check}: rows match the rule")
    return 0


if __name__ == "__main__":
    sys.exit(main())
