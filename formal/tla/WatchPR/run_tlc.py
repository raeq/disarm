#!/usr/bin/env python3
"""Run every TLC experiment for WatchPR.tla and tabulate the results.

Every property gets its own verdict and, when it fails, its own shortest counterexample
(see `experiment()`). A single-property .cfg per result row is generated into `cfg/`
(and committed, so one row can be re-run by hand); counterexamples land in `traces/`.

    TLA2TOOLS=/path/to/tla2tools.jar python3 formal/tla/WatchPR/run_tlc.py [name-regex]
    # re-run one row:
    java -cp tla2tools.jar tlc2.TLC -deadlock -noGenerateSpecTE -config cfg/<row>.cfg WatchPR.tla
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
JAR = os.environ.get("TLA2TOOLS", "tla2tools.jar")

T, F = "TRUE", "FALSE"

# This repository (raeq/disarm): a required roll-up check, conversation resolution
# required, branches must be up to date. The current code: no fixes.
DISARM = dict(
    MaxHead=3,
    MaxUnres=1,
    MaxPolls=0,
    MaxReadFails=2,
    RequiredChecks=T,
    ProtectThreads=T,
    Strict=T,
    SquashRejected=F,
    AwaitReview=F,
    AllowMerge=T,
    ThreadsFirst=F,
    EnvPush=T,
    EnvLag=F,
    EnvGhost=F,
    EnvThreads=T,
    EnvReviews=F,
    EnvBase=T,
    EnvClose=T,
    EnvOverflow=T,
    EnvBetweenReads=T,
    EnvInWindow=T,
    ThreadReadCanFail=T,
    FixMatchHead=F,
    FixThreadRead=F,
    FixDedup=F,
    FixMergeReject=F,
    FixChanges=F,
    FixReviewHead=F,
)
# A repo run with --await-review: required checks, NO conversation resolution (#987).
AWAIT = {
    **DISARM,
    "ProtectThreads": F,
    "AwaitReview": T,
    "EnvReviews": T,
    # Smaller: the review state multiplies the space. Base moves, overflow and closing
    # are checked in the DISARM runs and add nothing new to the review gate.
    "EnvBase": F,
    "EnvOverflow": F,
    "EnvClose": F,
    "MaxReadFails": 1,
}
# The same without any required check (nothing server-side gates the merge).
AWAIT_NOREQ = {**AWAIT, "RequiredChecks": F}
ALL_FIXES = dict(
    FixMatchHead=T, FixThreadRead=T, FixDedup=T, FixMergeReject=T, FixChanges=T, FixReviewHead=T
)
QUIET = dict(EnvBetweenReads=F, EnvInWindow=F)  # fetch..merge is atomic w.r.t. env

SAFETY = [
    "IssueEvaluatedHead",
    "IssueGreen",
    "MergedEvaluatedHead",
    "MergedNotRed",
    "MergedCompletedGreen",
    "MergedNoUnresolved",
    "ThreadGateSound",
    "AwaitContract",
    "AwaitNoChangesRequested",
    "AwaitReviewedThisHead",
    "NoStaleFailStop",
    "NoFalseStuck",
]

# (name, constants, [properties], kind)  kind: "inv" or "prop"
EXPERIMENTS: list[tuple[str, dict, list[str], str]] = [
    # --- this repo, current code, then with the fixes
    ("disarm_current", DISARM, ["TypeOK", *SAFETY], "inv"),
    ("disarm_fixed", {**DISARM, **ALL_FIXES}, SAFETY, "inv"),
    # --- a failed thread read must not count as a sighting (F1b)
    ("disarm_streak_current", DISARM, ["StreakFromCompleteReads"], "inv"),
    ("disarm_streak_fixed", {**DISARM, "FixThreadRead": T}, ["StreakFromCompleteReads"], "inv"),
    # --- stale rollups, isolated: view lag only / duplicate runs only
    (
        "disarm_lag",
        {**DISARM, "EnvLag": T, "EnvThreads": F, "EnvOverflow": F, "ThreadReadCanFail": F},
        ["NoStaleFailStop", "NoFalseStuck"],
        "inv",
    ),
    (
        "disarm_ghost",
        {**DISARM, "EnvGhost": T, "EnvThreads": F, "EnvOverflow": F, "ThreadReadCanFail": F},
        ["NoStaleFailStop"],
        "inv",
    ),
    (
        "disarm_ghost_fixdedup",
        {
            **DISARM,
            "EnvGhost": T,
            "EnvThreads": F,
            "EnvOverflow": F,
            "ThreadReadCanFail": F,
            "FixDedup": T,
        },
        ["NoStaleFailStop"],
        "inv",
    ),
    # --- --await-review repo, current code, then fixes, then atomic windows
    ("await_current", AWAIT, SAFETY, "inv"),
    ("await_fixed", {**AWAIT, **ALL_FIXES}, SAFETY, "inv"),
    ("await_current_quiet", {**AWAIT, **QUIET}, SAFETY, "inv"),
    ("await_fixed_quiet", {**AWAIT, **ALL_FIXES, **QUIET}, SAFETY, "inv"),
    # the read order is load-bearing: threads before the view, all else fixed & quiet
    (
        "await_threadsfirst_tailquiet",
        {**AWAIT, **ALL_FIXES, "EnvInWindow": F, "ThreadsFirst": T},
        ["MergedNoUnresolved"],
        "inv",
    ),
    (
        "await_viewfirst_tailquiet",
        {**AWAIT, **ALL_FIXES, "EnvInWindow": F},
        ["MergedNoUnresolved"],
        "inv",
    ),
    # --- --await-review repo with no required check: the head race lands
    (
        "await_noreq_current",
        AWAIT_NOREQ,
        ["MergedEvaluatedHead", "UnevaluatedNotRed", "MergedNotRed", "MergedCompletedGreen"],
        "inv",
    ),
    (
        "await_noreq_fixmatchhead",
        {**AWAIT_NOREQ, "FixMatchHead": T},
        ["MergedEvaluatedHead", "UnevaluatedNotRed", "MergedNotRed", "MergedCompletedGreen"],
        "inv",
    ),
    # --- liveness (unbounded polls, WF on the watcher)
    (
        "live_disarm_current",
        {**DISARM, "EnvOverflow": F},
        ["EventuallyStops", "EventuallyMerges"],
        "prop",
    ),
    (
        "live_disarm_rejected",
        {**DISARM, "EnvOverflow": F, "SquashRejected": T},
        ["EventuallyStops"],
        "prop",
    ),
    (
        "live_disarm_rejected_fix",
        {**DISARM, "EnvOverflow": F, "SquashRejected": T, "FixMergeReject": T},
        ["EventuallyStops"],
        "prop",
    ),
    (
        "live_await_current",
        {**AWAIT, "EnvOverflow": F},
        ["EventuallyStops", "EventuallyMerges"],
        "prop",
    ),
    (
        "live_await_fixed",
        {**AWAIT, **ALL_FIXES, "EnvOverflow": F},
        ["EventuallyStops", "EventuallyMerges"],
        "prop",
    ),
]


def write_cfg(consts: dict, props: list[str], kind: str, path: Path) -> Path:
    spec = "LiveSpec" if kind == "prop" else "Spec"
    lines = [f"SPECIFICATION {spec}", "CONSTANTS"]
    lines += [f"    {k} = {v}" for k, v in consts.items()]
    lines += [("INVARIANT " if kind == "inv" else "PROPERTY ") + p for p in props]
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return path


def tlc(cfg: Path) -> str:
    log = os.environ.get("TLC_LOG")  # optional: tail -f it to watch progress
    with tempfile.TemporaryDirectory() as meta:
        cmd = ["java", "-XX:+UseParallelGC", "-cp", JAR, "tlc2.TLC", "-workers", "auto"]
        cmd += ["-deadlock", "-noGenerateSpecTE", "-metadir", meta]
        cmd += ["-config", str(cfg), str(HERE / "WatchPR.tla")]
        if log:
            with open(log, "w") as fh:
                subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, check=False)
            return Path(log).read_text()
        return subprocess.run(cmd, capture_output=True, text=True, check=False).stdout


def stats(out: str) -> tuple[str, str, str]:
    m = re.search(r"([\d,]+) states generated, ([\d,]+) distinct states found", out)
    d = re.search(r"The depth of the complete state graph search is (\d+)", out)
    gen, dist = (m.group(1), m.group(2)) if m else ("?", "?")
    return gen, dist, d.group(1) if d else "-"


def experiment(name: str, consts: dict, props: list[str], kind: str):
    """Yield (property, verdict, generated, distinct, depth).

    Invariants: one TLC run with every remaining invariant. A violation names the
    invariant, whose (shortest, breadth-first) trace is saved, and the rest are re-run
    without it; what survives the final, complete run HOLDS. Temporal properties: one run
    each, since TLC does not name which of several was violated.
    """
    for p in props:  # a single-property .cfg per row, to re-run one by hand
        write_cfg(consts, [p], kind, HERE / "cfg" / f"{name}__{p}.cfg")
    remaining = list(props)
    while remaining:
        batch = remaining if kind == "inv" else remaining[:1]
        tmp = HERE / "cfg" / f".{name}.batch.cfg"
        out = tlc(write_cfg(consts, batch, kind, tmp))
        tmp.unlink()
        gen, dist, depth = stats(out)
        if "No error has been found" in out:
            for p in batch:
                yield p, "HOLDS", gen, dist, depth
            remaining = [p for p in remaining if p not in batch]
            continue
        m = re.search(r"(?:Invariant|Temporal property) (\w+) (?:is|was) violated", out)
        bad = m.group(1) if m else batch[0]
        ok = m is not None or "Temporal properties were violated" in out
        suffix = "" if ok else ".ERROR"
        (HERE / "traces").mkdir(exist_ok=True)
        (HERE / "traces" / f"{name}__{bad}{suffix}.txt").write_text(out)
        yield bad, "VIOLATED" if ok else "ERROR", gen, dist, depth
        remaining.remove(bad)


def main() -> None:
    filt = sys.argv[1] if len(sys.argv) > 1 else ""
    print("| experiment | property | verdict | states generated | distinct | depth |")
    print("|---|---|---|---|---|---|")
    for name, consts, props, kind in EXPERIMENTS:
        if filt and not re.search(filt, name):
            continue
        for p, v, g, dd, depth in experiment(name, consts, props, kind):
            print(f"| {name} | {p} | {v} | {g} | {dd} | {depth} |", flush=True)


if __name__ == "__main__":
    main()
