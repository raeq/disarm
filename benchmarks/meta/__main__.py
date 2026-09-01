"""CLI for the meta-benchmark.

``--list`` shows ``m``; every other flag narrows it to ``n``.
"""

from __future__ import annotations

import argparse
import sys

from . import baseline as baseline_mod
from . import subjects as subjects_mod
from .leaderboard import build as build_leaderboard
from .protocol import Availability, Family, Outcome, Status, Suite
from .registry import all_suites, select
from .report import render_json, render_markdown
from .runner import provision, run


def _list(suites: list[Suite], registered: int) -> None:
    print(f"{len(suites)} of {registered} registered benchmarks\n")
    width = max((len(s.name) for s in suites), default=10)
    current: Family | None = None
    for suite in suites:
        if suite.family is not current:
            current = suite.family
            print(f"[{current.value}]")
        ready, reason = suite.available()
        mark = "ok " if ready else "-- "
        ext = "" if suite.provenance.external else "  (introspective: no external oracle)"
        print(
            f"  {mark}{suite.name:<{width}}  {suite.availability.value:<13}"
            f"{suite.provenance.citation}{ext}"
        )
        if not ready:
            print(f"     {' ' * width}  {reason}")
    print()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="benchmarks.meta",
        description="Run n of m externally produced benchmarks against disarm.",
    )
    p.add_argument("--list", action="store_true", help="list benchmarks and availability")
    p.add_argument("--run", action="store_true", help="execute the selection")
    p.add_argument(
        "--select", nargs="+", metavar="GLOB", help="suite name globs, e.g. 'uts39-*' bitabuse"
    )
    p.add_argument(
        "--family", nargs="+", choices=[f.value for f in Family], help="restrict to these families"
    )
    p.add_argument(
        "--availability",
        nargs="+",
        choices=[a.value for a in Availability],
        help="restrict to these availability classes",
    )
    p.add_argument(
        "--only-available", action="store_true", help="drop suites whose artifact is not present"
    )
    p.add_argument(
        "--sample", type=int, metavar="N", help="deterministically draw N of the selection"
    )
    p.add_argument("--seed", type=int, default=0, help="sample seed (default 0)")
    p.add_argument(
        "--include-introspective",
        action="store_true",
        help="also run the self-referential sweeps (excluded by default)",
    )
    p.add_argument("--limit", type=int, help="cap rows/code points per suite")
    p.add_argument(
        "--offline",
        action="store_true",
        help="never reach the network; use only what is already cached",
    )
    p.add_argument(
        "--refresh",
        action="store_true",
        help="re-download even when a cached copy exists (default: leave it alone)",
    )
    p.add_argument(
        "--subject",
        nargs="+",
        metavar="TOOL",
        help=(
            "tools to score (default: disarm). 'all' runs every installed "
            "subject; see --list-subjects. Suites that measure a disarm-specific "
            "surface skip other subjects rather than scoring them zero."
        ),
    )
    p.add_argument("--list-subjects", action="store_true", help="list tools and exit")
    p.add_argument("--report", metavar="PATH", help="write the markdown report here")
    p.add_argument("--json", metavar="PATH", help="write the machine-readable report here")
    p.add_argument(
        "--baseline",
        default="default",
        metavar="NAME",
        help="baseline to compare against (default: 'default')",
    )
    p.add_argument("--no-baseline", action="store_true", help="skip drift comparison")
    p.add_argument(
        "--update-baseline", action="store_true", help="rewrite the baseline from this run"
    )
    p.add_argument("--quiet", action="store_true", help="suppress per-suite progress")
    p.add_argument(
        "--leaderboard",
        action="store_true",
        help=(
            "rank the subjects, weighting each benchmark by its corrected "
            "item-total correlation. Refuses to publish a ranking when the "
            "battery's own diagnostics say it cannot carry one."
        ),
    )
    args = p.parse_args(argv)

    if args.list_subjects:
        print("Subjects (from requirements/bench.txt):\n")
        for subject in subjects_mod.all_subjects():
            ready, why = subject.available()
            caps = ",".join(sorted(subject.capabilities())) if ready else "-"
            mark = "ok " if ready else "-- "
            print(
                f"  {mark}{subject.info.name:<16}{subject.info.version:<10}"
                f"{caps:<26}{subject.info.role}"
            )
            if not ready:
                print(f"     {' ' * 16}{why}")
        return 0

    registered = len(all_suites())
    subjects = subjects_mod.select(args.subject)
    if not subjects:
        print("No requested subject is installed.", file=sys.stderr)
        return 2
    suites = select(
        patterns=args.select,
        families=args.family,
        availabilities=args.availability,
        include_introspective=args.include_introspective,
        only_available=args.only_available,
        sample=args.sample,
        seed=args.seed,
    )

    if args.list or not args.run:
        _list(suites, registered)
        return 0 if args.list else 2

    if not suites:
        print("Selection matched no benchmarks.", file=sys.stderr)
        return 2

    def started(suite: Suite) -> None:
        if not args.quiet:
            print(f"  running {suite.name} ...", file=sys.stderr, flush=True)

    def finished(outcome: Outcome) -> None:
        if args.quiet:
            return
        tag = {Status.OK: "ok", Status.SKIPPED: "skip", Status.ERROR: "ERROR"}[outcome.status]
        note = outcome.skip_reason or outcome.error or f"{outcome.population:,} rows"
        label = f"{outcome.suite} [{outcome.method.subject}]"
        print(f"  {tag:>5}  {label}: {note}", file=sys.stderr, flush=True)

    # Provision before anything runs. An existing file is never overwritten, so
    # an operator who placed a specific revision keeps it.
    if not args.quiet:
        print("Provisioning artifacts ...", file=sys.stderr, flush=True)
    got = provision(suites, offline=args.offline, refresh=args.refresh)
    if not args.quiet:
        for item in got.downloaded:
            print(
                f"  fetched  {item.source.filename} ({item.bytes:,} bytes, {item.source.licence})",
                file=sys.stderr,
            )
        for item in got.reused:
            print(f"  cached   {item.source.filename} (left intact)", file=sys.stderr)
        for source, why in got.failed:
            print(f"  FAILED   {source.filename}: {why}", file=sys.stderr)
        for source in got.skipped_offline:
            print(f"  offline  {source.filename}: not cached", file=sys.stderr)

    report = run(
        suites,
        registered=registered,
        limit=args.limit,
        subjects=subjects,
        provisioning=got,
        on_start=started,
        on_finish=finished,
    )

    drifts = [] if args.no_baseline else baseline_mod.compare(report.outcomes, args.baseline)
    board = build_leaderboard(report.outcomes) if args.leaderboard else None
    markdown = render_markdown(report, drifts, args.baseline, leaderboard=board)
    print(markdown)

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(markdown)
        print(f"wrote {args.report}", file=sys.stderr)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            f.write(render_json(report, drifts) + "\n")
        print(f"wrote {args.json}", file=sys.stderr)
    if args.update_baseline:
        path = baseline_mod.save(report.outcomes, report.disarm_version, args.baseline)
        print(f"baseline updated: {path}", file=sys.stderr)

    # Observations only: a moved number never fails the run. A suite that threw
    # is a harness defect, and that does.
    return 1 if report.errored else 0


if __name__ == "__main__":
    raise SystemExit(main())
