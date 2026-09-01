"""Render a run as Markdown or JSON.

Two rules the report keeps. Every number prints with its denominator, because
"54" without "of 1,683" is how a figure ends up in prose and then drifts. And
the introspective tier is rendered in its own section, never folded into an
external total, so the bias boundary survives the trip into a document.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from .baseline import Drift
from .leaderboard import ALPHA_FLOOR, Leaderboard
from .protocol import Family, Measurement, Outcome, Provenance, Status
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
    if m.of is None:
        return _num(m.value)
    # `of == 0` is a real denominator, not a missing one: an empty population is
    # exactly the case the report must not hide behind a bare count.
    if m.of == 0:
        return f"{_num(m.value)} / 0"
    return f"{_num(m.value)} / {_num(m.of)} ({m.value / m.of * 100:.1f}%)"


def render_markdown(
    report: RunReport,
    drifts: Sequence[Drift] = (),
    baseline_name: str = "default",
    leaderboard: Leaderboard | None = None,
) -> str:
    lines: list[str] = [
        "# disarm meta-benchmark",
        "",
        f"_disarm {report.disarm_version} · Unicode {report.unicode_version} · "
        f"confusables {report.confusables_version}_",
        "",
        f"Subjects: {', '.join(f'`{s}`' for s in report.subjects)}.",
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

    if leaderboard is not None:
        lines += _render_leaderboard(leaderboard)
    lines += _render_comparison(report)
    by_family = report.by_family()
    for family in Family:
        outcomes = by_family.get(family)
        if not outcomes:
            continue
        lines += [f"## {_FAMILY_TITLE[family]}", ""]
        # Grouped by suite: the provenance, the finding and the methodology
        # belong to the benchmark, not to each tool that ran it. Repeating them
        # per subject buried the numbers.
        by_suite: dict[str, list[Outcome]] = {}
        for out in outcomes:
            by_suite.setdefault(out.suite, []).append(out)
        for group in by_suite.values():
            lines += _render_suite(group)
    if drifts:
        lines += _render_drift(drifts, baseline_name)
    lines += _render_skips(report)
    return "\n".join(lines).rstrip() + "\n"


def _render_leaderboard(board: Leaderboard) -> list[str]:
    """Rank the subjects, or say plainly why the battery cannot."""
    lines = ["## Leaderboard", ""]
    if not board.usable:
        return lines + ["Not enough directed measurements to compute anything.", ""]

    lines += [
        "Composite of discrimination-weighted z-scores. Each benchmark's weight is "
        "its corrected item-total correlation (classical test theory); measurements "
        "are averaged within a benchmark first so a suite reporting seven related "
        "numbers does not get seven votes; the scale is fitted on the tools and the "
        "controls are placed on it; intervals are bootstrapped over the benchmark "
        "set. Bradley-Terry strengths are fitted by Hunter's MM algorithm and use "
        "only the order of each pairwise result.",
        "",
        f"Battery: **{len(board.items)}** benchmarks, **{len(board.subjects)}** "
        f"subjects. Cronbach's alpha "
        f"**{board.alpha:.2f}**"
        if board.alpha is not None
        else "alpha n/a",
    ]
    lines[-1] += (
        f" (floor {ALPHA_FLOOR:.2f}), Kendall's W **{board.kendall_w:.2f}**"
        if board.kendall_w is not None
        else ""
    )
    lines[-1] += (
        f". {board.excluded_census_measurements} census measurements excluded for "
        "having no direction."
    )
    lines.append("")

    if not board.supported:
        lines += [
            "**This battery does not support a ranking, and none is published.**",
            "",
        ]
        lines += [f"- {why}" for why in board.blockers]
        lines += [
            "",
            "The composites below are recorded so the shortfall is auditable. They "
            "are not a result and must not be quoted as one.",
            "",
        ]

    lines += [
        "| # | subject | composite | 95% CI | Bradley-Terry | benchmarks |",
        "|---|---|---|---|---|---|",
    ]
    total = len(board.items)
    for st in board.standings:
        name = f"`{st.subject}`"
        if st.control:
            name += " *(control)*"
        if st.partial:
            name += " *(partial coverage — not ranked)*"
        composite = "off-scale" if st.control and abs(st.composite) > 10 else f"{st.composite:.3f}"
        # A subject answering one benchmark has no place in an ordering built
        # from four: it was asked fewer questions, not judged better.
        position = "—" if st.partial else str(st.rank)
        lines.append(
            f"| {position} | {name} | {composite} | "
            f"[{st.ci_low:.2f}, {st.ci_high:.2f}] | {st.bt_strength:.3f} | "
            f"{st.items}/{total} |"
        )
    lines += [
        "",
        "| benchmark | discrimination | measurements |",
        "|---|---|---|",
    ]
    for item in sorted(board.items, key=lambda i: -i.discrimination):
        lines.append(f"| `{item.suite}` | {item.discrimination:.3f} | {item.key} |")
    lines += ["", "### Per benchmark", ""]
    lines += [
        "Each benchmark ranked on its own. These stand whether or not the "
        "composite does: averaging benchmarks needs them to measure one thing "
        "first, but ranking within one benchmark assumes nothing beyond that "
        "benchmark. Equal scores share a rank. A subject absent from a table was "
        "not asked that question.",
        "",
    ]
    per = board.per_benchmark()
    for item in sorted(board.items, key=lambda i: -i.discrimination):
        standings = per.get(item.suite, [])
        if not standings:
            continue
        lines += [
            f"**`{item.suite}`** — discrimination {item.discrimination:.3f}, "
            f"{len(standings)} subjects",
            "",
            "| # | subject | z | oriented score |",
            "|---|---|---|---|",
        ]
        for place in standings:
            name = f"`{place.subject}`" + (" *(control)*" if place.control else "")
            lines.append(f"| {place.rank} | {name} | {place.z:+.2f} | {place.raw:.4g} |")
        lines.append("")
    return lines


def _render_comparison(report: RunReport) -> list[str]:
    """Cross-subject columns, wherever more than one subject produced a number."""
    if len(report.subjects) < 2:
        return []
    rows: list[tuple[str, str, dict[str, float]]] = []
    for suite in dict.fromkeys(o.suite for o in report.ran):
        for key in dict.fromkeys(
            m.key for o in report.ran if o.suite == suite for m in o.measurements
        ):
            got = report.comparison(suite, key)
            if len(got) > 1:
                rows.append((suite, key, got))
    if not rows:
        return []
    subjects = [s for s in report.subjects if any(s in g for _, _, g in rows)]
    lines = [
        "## Across subjects",
        "",
        "The same benchmark, the same rows, several tools. An absolute figure is "
        "readable only beside another one. A tool absent from a row could not be "
        "asked that question, which is not the same as scoring zero.",
        "",
        "| suite | measurement | " + " | ".join(f"`{s}`" for s in subjects) + " |",
        "|---|---|" + "---|" * len(subjects),
    ]
    for suite, key, got in rows:
        cells = ["—" if got.get(s) is None else _cell(got[s]) for s in subjects]
        lines.append(f"| `{suite}` | `{key}` | " + " | ".join(cells) + " |")
    lines.append("")
    return lines


def _cell(value: float) -> str:
    return f"{value * 100:.1f}%" if 0 <= value <= 1 else _num(value)


def _render_method(out: Outcome) -> list[str]:
    m = out.method
    bits = [
        "<details><summary>Method</summary>",
        "",
        f"- subject: `{m.subject_key}`",
        f"- domain: {m.domain or 'unstated'} ({m.domain_size:,} units)",
    ]
    if m.predicates:
        shown = ", ".join(f"`{x}`" for x in m.predicates[:12])
        more = f" (+{len(m.predicates) - 12} more)" if len(m.predicates) > 12 else ""
        bits.append(f"- predicates: {shown}{more}")
    if m.parameters:
        bits.append("- parameters:")
        bits += [f"    - `{k}` = {v!r}" for k, v in sorted(m.parameters.items())]
    if m.artifact:
        bits.append(
            f"- artifact: `{m.artifact}` "
            f"(sha256 `{(m.artifact_sha256 or '')[:16]}…`, {m.artifact_bytes:,} bytes)"
        )
    if m.environment:
        bits.append(
            "- environment: " + ", ".join(f"{k} {v}" for k, v in sorted(m.environment.items()))
        )
    bits += ["", "</details>", ""]
    return bits


def _render_suite(group: list[Outcome]) -> list[str]:
    """One benchmark: its provenance once, then what each subject measured."""
    head = group[0]
    lines = _render_outcome(head)
    for out in group[1:]:
        if out.status is Status.SKIPPED:
            lines += [
                f"> `{out.method.subject_key}` — not run: {out.skip_reason}",
                "",
            ]
            continue
        if out.status is Status.ERROR:
            lines += [
                f"> `{out.method.subject_key}` — errored: `{out.error}`",
                "",
            ]
            continue
        lines += [
            f"**`{out.method.subject_key}`** — population {out.population:,}",
            "",
            "| measurement | value | reading |",
            "|---|---|---|",
        ]
        lines += [f"| `{m.key}` | {fmt(m)} | {m.detail or ''} |" for m in out.measurements]
        lines.append("")
    return lines


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
    if out.reproduction:
        verdict = (
            "reproduces the published script exactly"
            if out.reproduces_its_finding
            else "**does NOT reproduce the published script** — the finding above "
            "and the table below are not a before/after"
        )
        lines += [
            f"**Reproduction.** {p.reproduces or 'pinned'} — {verdict}.",
            "",
            "| quantity | published | here |",
            "|---|---|---|",
        ]
        for r in out.reproduction:
            mark = "" if r.matches else " (differs)"
            lines.append(f"| `{r.key}` | {_num(r.expected)} | {_num(r.actual)}{mark} |")
        lines.append("")
    lines += [
        f"**`{out.method.subject_key}`** — measured now, "
        f"population {out.population:,}, {out.duration_s:.2f}s:",
        "",
        "| measurement | value | reading |",
        "|---|---|---|",
    ]
    for m in out.measurements:
        lines.append(f"| `{m.key}` | {fmt(m)} | {m.detail or ''} |")
    lines.append("")
    lines += _render_method(out)
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
        "| subject | suite | measurement | before | after | direction | comparable |",
        "|---|---|---|---|---|---|---|",
    ]
    for d in sorted(significant, key=lambda x: (x.suite, x.key)):
        note = (
            "yes"
            if d.comparable
            else (
                "**no — Unicode tables moved**"
                if d.tables_moved
                else "**no — different population**"
            )
        )
        lines.append(
            f"| `{d.subject}` | `{d.suite}` | `{d.key}` | {_num(d.before)} | "
            f"{_num(d.after)} | {d.direction} | {note} |"
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


def load_outcomes(path: str) -> list[Outcome]:
    """Rebuild outcomes from a JSON report written by an earlier run.

    This is how two builds of one tool compete. A compiled extension cannot be
    imported twice in one process, so `disarm@0.14.1` and `disarm@0.15.0` cannot
    both be live at once — they are measured in separate runs and merged here.
    Only what the comparison and the leaderboard need is reconstructed; the
    method record is carried through so a merged row can still be traced.
    """
    import json as _json

    from .protocol import Measurement, Method

    payload = _json.loads(Path(path).read_text(encoding="utf-8"))
    out: list[Outcome] = []
    for row in payload.get("suites", []):
        prov = row.get("provenance", {})
        method = row.get("method", {})
        outcome = Outcome(
            suite=row["name"],
            family=Family(row.get("family", "academic")),
            provenance=Provenance(
                origin=prov.get("origin", "?"),
                citation=prov.get("citation", "?"),
                url=prov.get("url", ""),
                version=prov.get("version", "?"),
                licence=prov.get("licence", "?"),
                external=prov.get("external", True),
                issues=tuple(prov.get("issues", ())),
                finding=prov.get("finding", ""),
                notes=prov.get("notes", ""),
            ),
            status=Status(row.get("status", "ok")),
            population=row.get("population", 0),
            method=Method(
                subject=method.get("subject", "?"),
                subject_version=method.get("subject_version", "?"),
                domain=method.get("domain", ""),
                domain_size=method.get("domain_size", 0),
                predicates=list(method.get("predicates", [])),
                parameters=dict(method.get("parameters", {})),
                artifact=method.get("artifact"),
                artifact_sha256=method.get("artifact_sha256"),
                artifact_bytes=method.get("artifact_bytes"),
                environment=dict(method.get("environment", {})),
            ),
            measurements=[
                Measurement(
                    key=m["key"],
                    value=m["value"],
                    of=m.get("of"),
                    unit=m.get("unit", "count"),
                    higher_is_better=m.get("higher_is_better"),
                    detail=m.get("detail", ""),
                )
                for m in row.get("measurements", [])
            ],
        )
        out.append(outcome)
    return out


def render_json(report: RunReport, drifts: Sequence[Drift] = ()) -> str:
    payload = {
        "subjects": report.subjects,
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
                "method": {
                    "subject": o.method.subject,
                    "subject_version": o.method.subject_version,
                    "subject_key": o.method.subject_key,
                    "domain": o.method.domain,
                    "domain_size": o.method.domain_size,
                    "predicates": o.method.predicates,
                    "parameters": o.method.parameters,
                    "artifact": o.method.artifact,
                    "artifact_sha256": o.method.artifact_sha256,
                    "artifact_bytes": o.method.artifact_bytes,
                    "environment": o.method.environment,
                },
                "reproduction": [
                    {
                        "key": r.key,
                        "expected": r.expected,
                        "actual": r.actual,
                        "matches": r.matches,
                        "version": r.version,
                    }
                    for r in o.reproduction
                ],
                "reproduces_its_finding": o.reproduces_its_finding,
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
                "subject": d.subject,
                "tables_moved": d.tables_moved,
                "direction": d.direction,
                "significant": d.significant,
            }
            for d in drifts
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True, default=str)
