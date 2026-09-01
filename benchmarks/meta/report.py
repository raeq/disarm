"""Render a run as Markdown or JSON.

Two rules the report keeps. Every number prints with its denominator, because
"54" without "of 1,683" is how a figure ends up in prose and then drifts. And
the introspective tier is rendered in its own section, never folded into an
external total, so the bias boundary survives the trip into a document.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from .baseline import Drift
from .protocol import Family, Measurement, Outcome, Status
from .runner import RunReport

_FAMILY_TITLE = {
    Family.NORMATIVE: "Normative tables (Unicode, IETF, ICANN, CLDR)",
    Family.CVE: "Published vulnerabilities",
    Family.ACADEMIC: "Released academic corpora",
    Family.DATASET: "Public datasets",
    Family.MODEL_ARTIFACT: "Released model artifacts",
    Family.COMPARATOR: "Third-party labelled benchmarks and rival implementations",
    Family.INTROSPECTIVE: "Introspective sweeps — no external oracle, excluded from totals",
}


def _num(value: float) -> str:
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:.4g}"


def fmt(m: Measurement) -> str:
    if m.unit == "ratio":
        return f"{m.value * 100:.1f}%"
    if m.of:
        return f"{_num(m.value)} / {_num(m.of)} ({m.value / m.of * 100:.1f}%)"
    return _num(m.value)


def render_markdown(
    report: RunReport,
    drifts: Sequence[Drift] = (),
    baseline_name: str = "default",
) -> str:
    lines: list[str] = [
        "# disarm meta-benchmark",
        "",
        f"_disarm {report.disarm_version} · Unicode {report.unicode_version} · "
        f"confusables {report.confusables_version}_",
        "",
        f"Ran **{report.selected} of {report.registered}** registered benchmarks in "
        f"{report.duration_s:.1f}s: {len(report.ran)} produced measurements, "
        f"{len(report.skipped)} skipped for a missing artifact, "
        f"{len(report.errored)} errored.",
        "",
        "Every benchmark here was produced by somebody else. This harness supplies "
        "the runner, the selection and the report; it supplies no vectors. Corpora "
        "are measuring instruments, never optimization targets — a number that moves "
        "is an observation to explain, not a target to close.",
        "",
    ]

    external = [o for o in report.ran if o.external]
    if external:
        lines += [
            f"**{len(external)}** external suites carried the run. "
            f"**{len([o for o in report.ran if not o.external])}** introspective "
            "sweeps ran alongside and are reported separately.",
            "",
        ]

    by_family = report.by_family()
    for family in Family:
        outcomes = by_family.get(family)
        if not outcomes:
            continue
        lines += [f"## {_FAMILY_TITLE[family]}", ""]
        for out in outcomes:
            lines += _render_outcome(out)
    if drifts:
        lines += _render_drift(drifts, baseline_name)
    lines += _render_skips(report)
    return "\n".join(lines).rstrip() + "\n"


def _render_outcome(out: Outcome) -> list[str]:
    p = out.provenance
    lines = [
        f"### `{out.suite}`",
        "",
        f"**Source.** {p.origin} — {p.citation} ({p.version}). Licence: {p.licence}. <{p.url}>",
    ]
    if p.issues:
        refs = ", ".join(f"[#{n}](https://github.com/raeq/disarm/issues/{n})" for n in p.issues)
        lines.append(f"**Identified.** {refs}")
    lines.append("")
    if p.finding:
        # Historical, and labelled as such. The gap between this paragraph and the
        # table below it is the reason the harness exists.
        lines += [f"**Found during the cycle.** {p.finding}", ""]
    if out.status is Status.SKIPPED:
        lines += [f"> Not run — {out.skip_reason}", ""]
        return lines
    if out.status is Status.ERROR:
        lines += [f"> Errored — `{out.error}`", ""]
        return lines
    if p.notes:
        lines += [f"**How it is measured.** {p.notes}", ""]
    lines += [
        f"Measured now — population {out.population:,}, {out.duration_s:.2f}s:",
        "",
        "| measurement | value | reading |",
        "|---|---|---|",
    ]
    for m in out.measurements:
        lines.append(f"| `{m.key}` | {fmt(m)} | {m.detail or ''} |")
    lines.append("")
    return lines


def _render_drift(drifts: Sequence[Drift], baseline_name: str) -> list[str]:
    significant = [d for d in drifts if d.significant]
    lines = [
        "## Drift against the committed baseline",
        "",
        f"Baseline `{baseline_name}`. {len(drifts)} "
        f"measurement{'' if len(drifts) == 1 else 's'} moved; "
        f"{len(significant)} beyond the noise floor. "
        "Nothing here fails a run — the point is that a silent change becomes visible.",
        "",
        "| suite | measurement | before | after | direction | comparable |",
        "|---|---|---|---|---|---|",
    ]
    for d in sorted(significant, key=lambda x: (x.suite, x.key)):
        note = "yes" if d.comparable else "**no — different population**"
        lines.append(
            f"| `{d.suite}` | `{d.key}` | {_num(d.before)} | {_num(d.after)} | "
            f"{d.direction} | {note} |"
        )
    lines.append("")
    incomparable = [d for d in significant if not d.comparable]
    if incomparable:
        lines += [
            "> Rows marked *no* were measured over a different population than the "
            "baseline (usually a `--limit` on one side). The values are printed but "
            "the difference between them means nothing.",
            "",
        ]
    return lines


def _render_skips(report: RunReport) -> list[str]:
    if not report.skipped:
        return []
    lines = [
        "## Not run",
        "",
        "An absent corpus is not a passing corpus. Each row names what to place and where.",
        "",
        "| suite | source | why |",
        "|---|---|---|",
    ]
    for out in report.skipped:
        lines.append(f"| `{out.suite}` | {out.provenance.citation} | {out.skip_reason} |")
    lines.append("")
    return lines


def render_json(report: RunReport, drifts: Sequence[Drift] = ()) -> str:
    payload = {
        "disarm_version": report.disarm_version,
        "unicode_version": report.unicode_version,
        "confusables_version": report.confusables_version,
        "registered": report.registered,
        "selected": report.selected,
        "duration_s": round(report.duration_s, 3),
        "suites": [
            {
                "name": o.suite,
                "family": o.family.value,
                "status": o.status.value,
                "external": o.external,
                "population": o.population,
                "duration_s": round(o.duration_s, 3),
                "skip_reason": o.skip_reason,
                "error": o.error,
                "provenance": {
                    "origin": o.provenance.origin,
                    "citation": o.provenance.citation,
                    "url": o.provenance.url,
                    "version": o.provenance.version,
                    "licence": o.provenance.licence,
                    "external": o.provenance.external,
                    "issues": list(o.provenance.issues),
                    "finding": o.provenance.finding,
                    "notes": o.provenance.notes,
                },
                "measurements": [
                    {
                        "key": m.key,
                        "value": m.value,
                        "of": m.of,
                        "unit": m.unit,
                        "ratio": m.ratio,
                        "higher_is_better": m.higher_is_better,
                        "detail": m.detail,
                    }
                    for m in o.measurements
                ],
                "extra": dict(o.extra),
            }
            for o in report.outcomes
        ],
        "drift": [
            {
                "suite": d.suite,
                "measurement": d.key,
                "before": d.before,
                "after": d.after,
                "delta": d.delta,
                "ratio_delta": d.ratio_delta,
                "comparable": d.comparable,
                "direction": d.direction,
                "significant": d.significant,
            }
            for d in drifts
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True, default=str)
