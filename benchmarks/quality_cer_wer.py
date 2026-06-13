#!/usr/bin/env python3
"""Phase-0 transliteration-quality harness — CER / WER baseline (issue #173).

This is the *minimal, reproducible* slice of issue #173 ("Quantify
transliteration quality with standard benchmarks"), built for epic #326's
0.10 milestone. Its single Phase-0 job is to produce a **pre-split behavioural
baseline**: a recorded CER/WER number, keyed to the disarm version, that can be
re-run after the #38 module split to prove the refactor caused **no quality
drift**.

What this is NOT (still scoped to #173, intentionally out of Phase 0):
  * the full Dakshina / uroman / ICU baseline comparison,
  * the abjad CCPD indicators (Selection Rate, Partial-/Reader-DER),
  * a CI quality gate with regression thresholds.

Design constraints (kept deliberately tight):
  * pure-Python + stdlib only — the edit distance is implemented inline, no
    jiwer / Levenshtein dependency,
  * offline + deterministic — fixtures are committed under
    ``benchmarks/quality_fixtures/``; nothing is downloaded,
  * fast — a few dozen short pairs, runs in well under a second,
  * NOT collected by the default ``pytest`` gate (benches never are; see
    ``benchmarks/README.md``). Run it explicitly.

Metrics
-------
CER (Character Error Rate) and WER (Word Error Rate) are the standard
Levenshtein-based rates used across the transliteration literature cited in
issue #173::

    CER = edit_distance(chars(hyp), chars(ref)) / len(chars(ref))
    WER = edit_distance(words(hyp), words(ref)) / len(words(ref))

where ``edit_distance`` is the classic Levenshtein distance (insertions +
deletions + substitutions, unit cost). Both are micro-averaged: total edits
over the corpus divided by total reference length, which is the convention used
when reporting a single corpus-level number.

Usage
-----
    python benchmarks/quality_cer_wer.py                  # human-readable table
    python benchmarks/quality_cer_wer.py --json           # machine-readable
    python benchmarks/quality_cer_wer.py --update-baseline # rewrite the .md baseline
    python benchmarks/quality_cer_wer.py --self-check      # assert the CER/WER math

Requires the built extension (``maturin develop``). See ``benchmarks/README.md``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

FIXTURE_PATH = Path(__file__).parent / "quality_fixtures" / "cer_wer_pairs.tsv"
BASELINE_PATH = Path(__file__).parent / "quality_baseline.md"


# The scored result is JSON-shaped; these TypedDicts pin its structure so both
# the producer (`score`) and the consumers (`render_*`) are statically checked.
class GroupRow(TypedDict):
    pairs: int
    cer: float
    wer: float


class DetailRow(TypedDict):
    script: str
    standard: str
    source: str
    reference: str
    hypothesis: str
    cer: float
    wer: float
    exact: bool


class Results(TypedDict):
    disarm_version: str
    fixture_pairs: int
    overall: GroupRow
    by_standard: dict[str, GroupRow]
    by_script: dict[str, GroupRow]
    detail: list[DetailRow]


# ---------------------------------------------------------------------------
# Metric primitives (stdlib-only; no external edit-distance dependency)
# ---------------------------------------------------------------------------


def levenshtein(a: list[str], b: list[str]) -> int:
    """Classic Levenshtein distance over two token sequences (unit costs).

    Works on any sequence of hashable tokens — pass a list of characters for
    CER, a list of words for WER. Uses the rolling two-row DP, so memory is
    O(min(len)) and it never recurses.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    # Keep the inner loop over the shorter sequence for a smaller row.
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    current = [0] * (len(b) + 1)
    for i, ca in enumerate(a, start=1):
        current[0] = i
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            current[j] = min(
                previous[j] + 1,  # deletion
                current[j - 1] + 1,  # insertion
                previous[j - 1] + cost,  # substitution / match
            )
        previous, current = current, previous
    return previous[len(b)]


@dataclass
class Tally:
    """Accumulates edits and reference length for a micro-averaged rate."""

    edits: int = 0
    ref_len: int = 0
    pairs: int = 0

    def add(self, hyp_tokens: list[str], ref_tokens: list[str]) -> None:
        self.edits += levenshtein(hyp_tokens, ref_tokens)
        self.ref_len += len(ref_tokens)
        self.pairs += 1

    @property
    def rate(self) -> float:
        # An all-empty reference set has no measurable error.
        return self.edits / self.ref_len if self.ref_len else 0.0


@dataclass
class GroupResult:
    label: str
    cer: Tally
    wer: Tally


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Pair:
    script: str
    standard: str
    source: str
    reference: str


def load_pairs(path: Path = FIXTURE_PATH) -> list[Pair]:
    """Parse the committed TSV fixtures, skipping comments and blank lines."""
    pairs: list[Pair] = []
    with path.open(encoding="utf-8") as handle:
        for lineno, raw in enumerate(handle, start=1):
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) != 4:
                raise ValueError(
                    f"{path}:{lineno}: expected 4 TAB-separated fields, got {len(fields)}: {line!r}"
                )
            script, standard, source, reference = (f.strip() for f in fields)
            pairs.append(Pair(script, standard, source, reference))
    if not pairs:
        raise ValueError(f"{path}: no fixture pairs found")
    return pairs


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _words(text: str) -> list[str]:
    return text.split()


def _chars(text: str) -> list[str]:
    return list(text)


def score(pairs: list[Pair]) -> Results:
    """Run disarm.transliterate over every pair and compute CER/WER.

    Returns a JSON-serialisable dict grouped by ``standard`` and by ``script``,
    plus an overall micro-average and the per-pair detail.
    """
    import disarm

    by_standard: dict[str, GroupResult] = {}
    by_script: dict[str, GroupResult] = {}
    overall = GroupResult("overall", Tally(), Tally())
    detail: list[DetailRow] = []

    def group(table: dict[str, GroupResult], key: str) -> GroupResult:
        if key not in table:
            table[key] = GroupResult(key, Tally(), Tally())
        return table[key]

    for pair in pairs:
        hyp = disarm.transliterate(pair.source)
        ref = pair.reference

        hyp_chars, ref_chars = _chars(hyp), _chars(ref)
        hyp_words, ref_words = _words(hyp), _words(ref)

        for grp in (
            overall,
            group(by_standard, pair.standard),
            group(by_script, pair.script),
        ):
            grp.cer.add(hyp_chars, ref_chars)
            grp.wer.add(hyp_words, ref_words)

        char_edits = levenshtein(hyp_chars, ref_chars)
        word_edits = levenshtein(hyp_words, ref_words)
        detail.append(
            {
                "script": pair.script,
                "standard": pair.standard,
                "source": pair.source,
                "reference": ref,
                "hypothesis": hyp,
                "cer": char_edits / len(ref_chars) if ref_chars else 0.0,
                "wer": word_edits / len(ref_words) if ref_words else 0.0,
                "exact": hyp == ref,
            }
        )

    def row(grp: GroupResult) -> GroupRow:
        return {
            "pairs": grp.cer.pairs,
            "cer": round(grp.cer.rate, 6),
            "wer": round(grp.wer.rate, 6),
        }

    def serialise(table: dict[str, GroupResult]) -> dict[str, GroupRow]:
        return {key: row(grp) for key, grp in sorted(table.items())}

    return {
        "disarm_version": getattr(disarm, "__version__", "unknown"),
        "fixture_pairs": len(pairs),
        "overall": row(overall),
        "by_standard": serialise(by_standard),
        "by_script": serialise(by_script),
        "detail": detail,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _fmt_pct(rate: float) -> str:
    return f"{rate * 100:6.2f}%"


def render_text(results: Results) -> str:
    out: list[str] = []
    out.append("=" * 72)
    out.append(f"disarm transliteration quality — CER/WER baseline (v{results['disarm_version']})")
    out.append(f"{results['fixture_pairs']} fixture pairs (Phase-0, issue #173)")
    out.append("=" * 72)

    ov = results["overall"]
    out.append("")
    out.append(f"OVERALL  CER {_fmt_pct(ov['cer'])}   WER {_fmt_pct(ov['wer'])}")

    out.append("")
    out.append("By romanization standard:")
    out.append(f"  {'standard':16s} {'pairs':>5s}  {'CER':>8s}  {'WER':>8s}")
    for key, row in results["by_standard"].items():
        out.append(
            f"  {key:16s} {row['pairs']:>5d}  {_fmt_pct(row['cer'])}  {_fmt_pct(row['wer'])}"
        )

    out.append("")
    out.append("By script:")
    out.append(f"  {'script':16s} {'pairs':>5s}  {'CER':>8s}  {'WER':>8s}")
    for key, row in results["by_script"].items():
        out.append(
            f"  {key:16s} {row['pairs']:>5d}  {_fmt_pct(row['cer'])}  {_fmt_pct(row['wer'])}"
        )

    # Surface the non-exact rows so a non-zero number is explainable, not magic.
    misses = [d for d in results["detail"] if not d["exact"]]
    if misses:
        out.append("")
        out.append(f"Non-exact pairs ({len(misses)}):")
        for d in misses:
            out.append(
                f"  [{d['standard']}] {d['source']!r} -> {d['hypothesis']!r} "
                f"(ref {d['reference']!r}; CER {_fmt_pct(d['cer'])})"
            )
    out.append("")
    return "\n".join(out)


def render_baseline_md(results: Results) -> str:
    """Render the committed Markdown baseline (re-run target for the #38 split)."""
    lines: list[str] = []
    lines.append("# disarm transliteration-quality baseline (Phase 0)")
    lines.append("")
    lines.append(
        "Recorded CER/WER baseline for issue "
        "[#173](https://github.com/raeq/disarm/issues/173) "
        "(epic [#326](https://github.com/raeq/disarm/issues/326), 0.10 milestone)."
    )
    lines.append("")
    lines.append(f"- **disarm version:** `{results['disarm_version']}` (pre-split baseline)")
    lines.append(f"- **fixture pairs:** {results['fixture_pairs']}")
    lines.append(
        "- **harness:** `benchmarks/quality_cer_wer.py` — pure-Python, offline, deterministic"
    )
    lines.append("- **fixtures:** `benchmarks/quality_fixtures/cer_wer_pairs.tsv`")
    lines.append("")
    lines.append("Regenerate / verify with:")
    lines.append("")
    lines.append("```bash")
    lines.append("python benchmarks/quality_cer_wer.py                  # view")
    lines.append("python benchmarks/quality_cer_wer.py --update-baseline # rewrite this file")
    lines.append("```")
    lines.append("")
    lines.append("## Why this exists")
    lines.append("")
    lines.append(
        "This is the **Phase-0** slice of #173: a pre-split behavioural "
        "baseline, not the full benchmark. Re-running it after the #38 module "
        "split must reproduce these numbers, proving the refactor caused no "
        "transliteration-quality drift. The fuller CER/WER work (Dakshina / "
        "uroman / ICU baselines) and the abjad CCPD indicators "
        "(Selection Rate, Partial-/Reader-DER) remain scoped to #173."
    )
    lines.append("")
    lines.append(
        "`disarm-default` rows score the engine against **its own** documented "
        "default output, so their error is expected to be ~0 — they are the "
        "drift sentinel. `english-common` rows score against established "
        "English exonyms (e.g. *Tchaikovsky*) that the phonetic default "
        "legitimately differs from, recording an **honest** non-zero gap."
    )
    lines.append("")

    ov = results["overall"]
    lines.append("## Overall (micro-averaged)")
    lines.append("")
    lines.append("| metric | value |")
    lines.append("|--------|-------|")
    lines.append(f"| pairs | {ov['pairs']} |")
    lines.append(f"| CER | {ov['cer'] * 100:.2f}% |")
    lines.append(f"| WER | {ov['wer'] * 100:.2f}% |")
    lines.append("")

    lines.append("## By romanization standard")
    lines.append("")
    lines.append("| standard | pairs | CER | WER |")
    lines.append("|----------|------:|----:|----:|")
    for key, row in results["by_standard"].items():
        lines.append(
            f"| {key} | {row['pairs']} | {row['cer'] * 100:.2f}% | {row['wer'] * 100:.2f}% |"
        )
    lines.append("")

    lines.append("## By script")
    lines.append("")
    lines.append("| script | pairs | CER | WER |")
    lines.append("|--------|------:|----:|----:|")
    for key, row in results["by_script"].items():
        lines.append(
            f"| {key} | {row['pairs']} | {row['cer'] * 100:.2f}% | {row['wer'] * 100:.2f}% |"
        )
    lines.append("")

    misses = [d for d in results["detail"] if not d["exact"]]
    lines.append("## Non-exact pairs")
    lines.append("")
    if misses:
        lines.append("| standard | source | hypothesis | reference | CER |")
        lines.append("|----------|--------|------------|-----------|----:|")
        for d in misses:
            lines.append(
                f"| {d['standard']} | `{d['source']}` | `{d['hypothesis']}` | "
                f"`{d['reference']}` | {d['cer'] * 100:.2f}% |"
            )
    else:
        lines.append("_All pairs matched their reference exactly._")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Self-check (sanity, not a pytest)
# ---------------------------------------------------------------------------


def _self_check() -> None:
    """Tiny assertions so the metric code can't silently rot."""
    assert levenshtein(list("kitten"), list("sitting")) == 3
    assert levenshtein(list("abc"), list("abc")) == 0
    assert levenshtein([], list("abc")) == 3
    assert levenshtein(list("abc"), []) == 3
    assert levenshtein("a b c".split(), "a x c".split()) == 1
    t = Tally()
    t.add(list("Moskva"), list("Moskva"))
    assert t.rate == 0.0
    t2 = Tally()
    t2.add(list("Moskwa"), list("Moskva"))  # 1 sub over 6 chars
    assert abs(t2.rate - 1 / 6) < 1e-9


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help=f"rewrite {BASELINE_PATH.name} with the current numbers",
    )
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="run the metric self-check and exit (no extension needed)",
    )
    args = parser.parse_args(argv)

    _self_check()
    if args.self_check:
        print("self-check OK")
        return 0

    pairs = load_pairs()
    results = score(pairs)

    if args.update_baseline:
        BASELINE_PATH.write_text(render_baseline_md(results), encoding="utf-8")
        print(f"wrote {BASELINE_PATH}")
        return 0

    if args.json:
        json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        print(render_text(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
