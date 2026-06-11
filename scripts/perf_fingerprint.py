#!/usr/bin/env python3
"""Emit the perf measurement fingerprint (#234 gate V5) as one JSON record.

A perf measurement is comparable to another **only within an identical
fingerprint bucket** — same corpus digest, same build arch, same CPU
microarchitecture, same CPython. Absolute numbers never transfer across
machines; even comparator ratios are only valid bucketed by detected microarch
and interpreter (see #234). This script gathers every field the methodology
requires and merges the Rust half (runtime corpus digest + build target,
gate V6) produced by ``perf_workload --fingerprint``.

Usage::

    python scripts/perf_fingerprint.py           # readable summary + JSON
    python scripts/perf_fingerprint.py --json     # JSON only (append to perf-results)

Env overrides::

    PERF_WORKLOAD_BIN   path to a prebuilt perf_workload (skips ``cargo run``)
"""

from __future__ import annotations

import importlib.metadata as ilmd
import json
import os
import platform
import subprocess
import sys
import sysconfig
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "disarm-perf-fingerprint/v1"
REPO_ROOT = Path(__file__).resolve().parent.parent

# Comparators whose exact version is part of the fingerprint (must match the
# `bench` extra in pyproject.toml). The denominator of every ratio lives here;
# an unpinned/floating one silently shifts the result (gate V8).
COMPARATORS = [
    "Unidecode",
    "text-unidecode",
    "anyascii",
    "uroman",
    "ftfy",
    "python-slugify",
    "pathvalidate",
]


def _run(cmd: list[str], *, cwd: str | None = None, env: dict[str, str] | None = None) -> str:
    """Run a command, return stripped stdout, or '' on any failure."""
    try:
        out = subprocess.run(  # noqa: S603 (fixed, trusted argv)
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
            env=env,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return out.stdout.strip()


def _read(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def rust_half() -> dict[str, object]:
    """Corpus digest (V6) + build target, from the compiled workload binary."""
    env = {**os.environ, "PYO3_PYTHON": os.environ.get("PYO3_PYTHON", sys.executable)}
    prebuilt = os.environ.get("PERF_WORKLOAD_BIN")
    if prebuilt:
        line = _run([prebuilt, "--fingerprint"], env=env)
    else:
        line = _run(
            [
                "cargo",
                "run",
                "-q",
                "--release",
                "--no-default-features",
                "--example",
                "perf_workload",
                "--",
                "--fingerprint",
            ],
            cwd=str(REPO_ROOT),
            env=env,
        )
    # The binary prints exactly one JSON line; tolerate leading build chatter.
    for candidate in reversed(line.splitlines()):
        candidate = candidate.strip()
        if candidate.startswith("{"):
            parsed: dict[str, object] = json.loads(candidate)
            return parsed
    raise SystemExit(
        "perf_fingerprint: could not obtain the Rust fingerprint half; "
        "build perf_workload or set PERF_WORKLOAD_BIN."
    )


def cpu_info() -> dict[str, object]:
    arch = platform.machine()
    model: str | None = None
    microarch: str | None = None
    if sys.platform == "darwin":
        model = _run(["sysctl", "-n", "machdep.cpu.brand_string"]) or None
        # On Apple Silicon the brand string ("Apple M2") is the microarch.
        microarch = model
    elif sys.platform.startswith("linux"):
        info = _read("/proc/cpuinfo") or ""
        fields: dict[str, str] = {}
        for raw in info.splitlines():
            if ":" in raw:
                key, _, val = raw.partition(":")
                fields.setdefault(key.strip(), val.strip())
        model = fields.get("model name")
        fam, mod, step = (
            fields.get("cpu family"),
            fields.get("model"),
            fields.get("stepping"),
        )
        if fam and mod:
            # Bucket key — distinguishes Skylake-era from Zen etc. (gate, per
            # the runner-label≠microarch correction).
            microarch = f"x86-fam{fam}-mod{mod}-step{step or '?'}"
    return {"arch": arch, "model": model, "microarch": microarch}


def pinning_info() -> dict[str, object]:
    affinity: object = "n/a"
    sched = getattr(os, "sched_getaffinity", None)
    if sched is not None:
        try:
            cpus = sorted(sched(0))
            total = os.cpu_count() or len(cpus)
            affinity = {"cpus": cpus, "pinned": len(cpus) < total}
        except OSError:
            affinity = "n/a"
    governor = _read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor") or "n/a"
    no_turbo = _read("/sys/devices/system/cpu/intel_pstate/no_turbo")
    boost = _read("/sys/devices/system/cpu/cpufreq/boost")
    if no_turbo is not None:
        turbo = "off" if no_turbo == "1" else "on"
    elif boost is not None:
        turbo = "on" if boost == "1" else "off"
    else:
        turbo = "n/a"
    return {"affinity": affinity, "governor": governor, "turbo": turbo}


def rustc_info() -> dict[str, object]:
    out = _run(["rustc", "-vV"])
    fields: dict[str, str] = {}
    for line in out.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip()
    return {
        "version": out.splitlines()[0] if out else None,
        "host": fields.get("host"),
        "commit_hash": fields.get("commit-hash"),
        "llvm": fields.get("LLVM version"),
    }


def cpython_info() -> dict[str, object]:
    gil = getattr(sys, "_is_gil_enabled", None)
    return {
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "compiler": platform.python_compiler(),
        "gil_enabled": gil() if callable(gil) else None,
        "free_threaded": bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
        "config_args": sysconfig.get_config_var("CONFIG_ARGS"),
    }


def comparator_versions() -> dict[str, str]:
    out: dict[str, str] = {}
    for pkg in COMPARATORS:
        try:
            out[pkg] = ilmd.version(pkg)
        except ilmd.PackageNotFoundError:
            out[pkg] = "NOT INSTALLED"
    return out


def disarm_info(rust: dict[str, object]) -> dict[str, object]:
    commit = _run(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT)) or None
    dirty = bool(_run(["git", "status", "--porcelain"], cwd=str(REPO_ROOT)))
    return {"version": rust.get("disarm_version"), "commit": commit, "dirty": dirty}


def ci_image() -> dict[str, str] | None:
    keys = ("RUNNER_OS", "RUNNER_NAME", "ImageOS", "ImageVersion")
    found = {k: os.environ[k] for k in keys if k in os.environ}
    return found or None


def build_record() -> dict[str, object]:
    rust = rust_half()
    return {
        "schema": SCHEMA,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "corpus_digest": rust.get("corpus_digest"),
        "disarm": disarm_info(rust),
        "build": {
            "arch": rust.get("build_arch"),
            "os": rust.get("build_os"),
            "pointer_width_bits": rust.get("pointer_width_bits"),
            "profile": rust.get("build_profile"),
        },
        "rustc": rustc_info(),
        "cpu": cpu_info(),
        "pinning": pinning_info(),
        "os": {"platform": platform.platform(), "ci_image": ci_image()},
        "cpython": cpython_info(),
        "comparators": comparator_versions(),
    }


def main(argv: list[str]) -> int:
    record = build_record()
    if "--json" in argv[1:]:
        print(json.dumps(record, separators=(",", ":"), sort_keys=True))
        return 0
    # Human summary, then the canonical JSON.
    print(f"corpus_digest : {record['corpus_digest']}")
    build = record["build"]
    cpu = record["cpu"]
    assert isinstance(build, dict) and isinstance(cpu, dict)
    print(f"build target  : {build['arch']}-{build['os']} ({build['profile']})")
    print(f"cpu / uarch   : {cpu['model']} / {cpu['microarch']}")
    print(f"cpython       : {record['cpython']}")
    print(f"comparators   : {record['comparators']}")
    print("---")
    print(json.dumps(record, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
