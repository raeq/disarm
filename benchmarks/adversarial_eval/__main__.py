"""CLI for the adversarial-text robustness harness (#49).

python -m benchmarks.adversarial_eval --corpus youtube-spam [--limit N] [--report out.md]
python -m benchmarks.adversarial_eval --list
"""

from __future__ import annotations

import argparse
import sys

from .corpora import ADAPTERS
from .metrics import EvalResult, evaluate


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def render_markdown(res: EvalResult, limit: int | None) -> str:
    import disarm

    principled = sum(res.missed_principled.values())
    novel = sum(res.missed_novel.values())
    lines = [
        f"# Adversarial-text robustness — {res.corpus}",
        "",
        f"_disarm {getattr(disarm, '__version__', '?')}; `strip_obfuscation`. "
        "Numbers reflect the current version and may differ from the historical "
        "baseline in the README as coverage grows._",
        "",
        f"- rows evaluated: **{res.n_rows}**" + (f" (limit {limit})" if limit is not None else ""),
        f"- perturbation-bearing rows (contain non-ASCII): "
        f"**{_fmt_pct(res.perturbation_bearing_rate)}** "
        f"({res.rows_with_nonascii}/{res.n_rows})",
        f"- non-ASCII codepoints folded by `strip_obfuscation`: "
        f"**{_fmt_pct(res.folded_fraction)}** "
        f"({res.nonascii_before - res.nonascii_after}/{res.nonascii_before})",
    ]
    if res.labeled:
        lines += [
            "",
            "## Recovery (clean ground truth available)",
            "",
            f"- XMR (exact-match recovery, `P(perturbed) == P(clean)`): **{_fmt_pct(res.xmr)}**",
            f"- line-exact recovery (`P(perturbed) == clean`): **{_fmt_pct(res.line_exact)}**",
            f"- word-level recovery: **{_fmt_pct(res.word_recovery)}**",
        ]
    lines += [
        "",
        "## Miss-mining (non-ASCII codepoints surviving the defense)",
        "",
        f"- **principled** (in UTS#39, addressable — feed to #40): "
        f"**{len(res.missed_principled)}** distinct, {principled} occurrences",
        f"- **novel** (not in UTS#39, out of scope): "
        f"**{len(res.missed_novel)}** distinct, {novel} occurrences",
        "",
        "Top principled (addressable) misses:",
        "",
        "| codepoint | char | occurrences |",
        "|---|---|---|",
    ]
    for cp, count in res.missed_principled.most_common(15):
        lines.append(f"| U+{cp:04X} | `{chr(cp)}` | {count} |")
    lines += [
        "",
        "> Guardrail: these are **observations**, not optimization targets. "
        "Principled misses are candidates to verify and upstream via #40 — never "
        "silent table edits.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="benchmarks.adversarial_eval")
    parser.add_argument("--corpus", choices=sorted(ADAPTERS), help="corpus to evaluate")
    parser.add_argument("--limit", type=int, default=None, help="max rows (for a quick pass)")
    parser.add_argument("--report", type=str, default=None, help="write the markdown report here")
    parser.add_argument("--list", action="store_true", help="list available corpora and exit")
    parser.add_argument(
        "--processes",
        type=int,
        default=None,
        help="worker processes (default: all CPUs; 1 = inline)",
    )
    parser.add_argument("--chunk-size", type=int, default=4000, help="rows per worker chunk")
    args = parser.parse_args(argv)

    if args.list or not args.corpus:
        print("Available corpora:")
        for name, adapter in sorted(ADAPTERS.items()):
            tags = []
            if adapter.labeled:
                tags.append("labeled")
            if adapter.requires_credentials:
                tags.append("needs-credentials")
            print(f"  {name:14} {', '.join(tags) or 'unlabeled'}")
        return 0 if args.list else 2

    adapter = ADAPTERS[args.corpus]
    result = evaluate(
        adapter.load(limit=args.limit),
        corpus=adapter.name,
        labeled=adapter.labeled,
        processes=args.processes,
        chunk_size=args.chunk_size,
    )
    report = render_markdown(result, args.limit)
    print(report)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\nwrote {args.report}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
