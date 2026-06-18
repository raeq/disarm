#!/usr/bin/env python3
"""Dev-time dependency-freshness audit across *every* manifest in the repo.

Why this exists
---------------
Dependabot (``.github/dependabot.yml``) only watches a subset of the repo's
manifests. It never saw the binding crates, so ``napi`` (2 → 3) and ``magnus``
(0.7 → 0.8) drifted a major version with no PR and no signal. This script closes
that gap at dev-time: it audits *all* manifests — the core crate, both binding
crates, the Node package, and the Ruby bundle — and flags anything a major
version behind, so drift is visible before it accumulates.

It complements dependabot (which is reactive and only as complete as its config);
run it locally, and the scheduled ``dependency-audit`` workflow runs it weekly.

Ecosystems
----------
- **Cargo** — direct deps of ``Cargo.toml``, ``bindings/node/Cargo.toml`` and
  ``bindings/ruby/ext/disarm/Cargo.toml``, compared against crates.io.
- **npm** — ``bindings/node`` via ``npm outdated`` (skipped if npm is absent).
- **bundler** — ``bindings/ruby`` via ``bundle outdated`` (skipped if absent).

The Python toolchain (``pyproject.toml`` / ``uv``) is already dependabot-watched,
so it is reported as covered rather than re-queried here.

Usage
-----
    python scripts/audit_dependencies.py            # report; exit 0 always
    python scripts/audit_dependencies.py --strict   # exit 1 if any MAJOR behind
    python scripts/audit_dependencies.py --offline   # skip network (cargo) checks
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import tomllib

REPO = Path(__file__).resolve().parent.parent
USER_AGENT = "disarm-dependency-audit (https://github.com/raeq/disarm)"
CRATES_API = "https://crates.io/api/v1/crates/{name}"

# Cargo manifests to audit, each paired with the lockfile that resolves it. The
# resolved (lock) version — not the req — is compared against crates.io, so a
# deliberately-broad req like ``regex = "1"`` that resolves to the latest 1.x is
# correctly reported as current rather than as drift.
CARGO_MANIFESTS = [
    ("core", REPO / "Cargo.toml", REPO / "Cargo.lock"),
    (
        "node binding",
        REPO / "bindings" / "node" / "Cargo.toml",
        REPO / "bindings" / "node" / "Cargo.lock",
    ),
    (
        "ruby binding",
        REPO / "bindings" / "ruby" / "ext" / "disarm" / "Cargo.toml",
        REPO / "bindings" / "ruby" / "Cargo.lock",
    ),
]
CARGO_TABLES = ["dependencies", "build-dependencies", "dev-dependencies"]

# The project's own crate (the bindings depend on it); not external rot.
SELF_CRATES = {"disarm", "disarm_core", "_disarm"}

# Crates this repo intentionally pins below the latest major (document the reason
# so the audit stays green for deliberate holds rather than silent rot).
CARGO_PINNED: dict[str, str] = {
    # name: reason
}


@dataclass
class Finding:
    ecosystem: str
    source: str
    name: str
    current: str
    latest: str
    severity: str  # "major" | "minor" | "current" | "unknown"


def _version_tuple(spec: str) -> tuple[int, ...] | None:
    """Extract the leading numeric (major, minor, patch) from a version spec.

    Handles bare reqs ("2", "0.7"), caret/tilde ("^0.29.0"), and comma ranges
    (">=1.13.3,<2") by taking the first version token.
    """
    m = re.search(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", spec)
    if not m:
        return None
    return tuple(int(g) if g is not None else 0 for g in m.groups())


def _severity(current: str, latest: str) -> str:
    """Classify drift between a declared req and the latest stable version.

    A 0.x crate treats its *minor* as the breaking component (Cargo semantics),
    so 0.7 → 0.8 counts as "major".
    """
    cur = _version_tuple(current)
    lat = _version_tuple(latest)
    if cur is None or lat is None:
        return "unknown"
    cur_major, cur_minor = cur[0], (cur[1] if len(cur) > 1 else 0)
    lat_major, lat_minor = lat[0], (lat[1] if len(lat) > 1 else 0)
    if cur_major == 0:
        if lat_major > 0 or lat_minor > cur_minor:
            return "major"
    elif lat_major > cur_major:
        return "major"
    if lat > cur:
        return "minor"
    return "current"


def _crate_req(value: object) -> str | None:
    """Pull the version string out of a Cargo dependency value.

    ``foo = "1"`` → ``"1"``; ``foo = { version = "1", ... }`` → ``"1"``;
    a path/git-only dep (no version) → ``None`` (nothing to compare).
    """
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        v = value.get("version")
        return v if isinstance(v, str) else None
    return None


def _lock_versions(lockfile: Path) -> dict[str, str]:
    """Map crate name → highest resolved version in a Cargo.lock."""
    if not lockfile.exists():
        return {}
    data = tomllib.loads(lockfile.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for pkg in data.get("package", []):
        name, version = pkg.get("name"), pkg.get("version")
        if not name or not version:
            continue
        prev = out.get(name)
        if prev is None or (_version_tuple(version) or ()) > (_version_tuple(prev) or ()):
            out[name] = version
    return out


def _crates_io_latest(name: str, *, timeout: float = 15.0) -> str | None:
    req = urllib.request.Request(CRATES_API.format(name=name), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            data = json.load(resp)
        latest = data["crate"]["max_stable_version"]
        return latest if isinstance(latest, str) else None
    except (urllib.error.URLError, KeyError, json.JSONDecodeError, TimeoutError):
        return None


def audit_cargo(*, offline: bool) -> list[Finding]:
    findings: list[Finding] = []
    # De-dupe crate lookups across manifests (one crates.io call per crate).
    latest_cache: dict[str, str | None] = {}
    for label, manifest, lockfile in CARGO_MANIFESTS:
        if not manifest.exists():
            continue
        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
        resolved = _lock_versions(lockfile)
        for table in CARGO_TABLES:
            for name, value in data.get(table, {}).items():
                if name in SELF_CRATES:
                    continue
                req = _crate_req(value)
                if req is None:
                    continue  # path/git/workspace dep — nothing to compare
                # Prefer the lockfile-resolved version; fall back to the req.
                current = resolved.get(name, req)
                if offline:
                    findings.append(Finding("cargo", label, name, current, "?", "unknown"))
                    continue
                if name not in latest_cache:
                    latest_cache[name] = _crates_io_latest(name)
                latest = latest_cache[name]
                if latest is None:
                    findings.append(Finding("cargo", label, name, current, "?", "unknown"))
                    continue
                sev = _severity(current, latest)
                if name in CARGO_PINNED and sev == "major":
                    sev = "pinned"
                findings.append(Finding("cargo", label, name, current, latest, sev))
    return findings


def audit_npm() -> list[Finding]:
    node_dir = REPO / "bindings" / "node"
    if not shutil.which("npm") or not (node_dir / "package.json").exists():
        return [Finding("npm", "node binding", "(npm not available)", "", "", "skipped")]
    # `npm outdated` exits 0 when everything is current and 1 when something is
    # outdated — neither is an error. Any OTHER code (or stderr noise with no
    # stdout) is a real failure (no node_modules, network, …); report it as
    # "unknown" rather than letting an empty stdout masquerade as "all current".
    proc = subprocess.run(  # noqa: S603
        ["npm", "outdated", "--json"],  # noqa: S607
        cwd=node_dir,
        capture_output=True,
        text=True,
    )
    out = proc.stdout.strip()
    if proc.returncode not in (0, 1):
        return [Finding("npm", "node binding", "(npm outdated failed)", "", "", "unknown")]
    if not out:
        if proc.returncode == 0 and not proc.stderr.strip():
            return []  # genuinely all current
        return [Finding("npm", "node binding", "(npm outdated inconclusive)", "", "", "unknown")]
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return [Finding("npm", "node binding", "(npm outdated unparseable)", "", "", "unknown")]
    findings: list[Finding] = []
    for name, info in data.items():
        current = info.get("current") or info.get("wanted") or "?"
        latest = info.get("latest", "?")
        findings.append(
            Finding("npm", "node binding", name, current, latest, _severity(current, latest))
        )
    return findings


def audit_bundler() -> list[Finding]:
    ruby_dir = REPO / "bindings" / "ruby"
    if not shutil.which("bundle") or not (ruby_dir / "Gemfile").exists():
        return [Finding("bundler", "ruby binding", "(bundler not available)", "", "", "skipped")]
    # `bundle outdated` exits 0 when all gems are current and non-zero when some
    # are outdated — but it ALSO exits non-zero on a real failure (no
    # Gemfile.lock, resolver error). Parse the "newest …" lines; if none parse on
    # a non-zero exit, treat it as a failure ("unknown"), not "all current".
    proc = subprocess.run(  # noqa: S603
        ["bundle", "outdated", "--parseable"],  # noqa: S607
        cwd=ruby_dir,
        capture_output=True,
        text=True,
    )
    findings: list[Finding] = []
    # Lines look like: "rubocop (newest 1.81.0, installed 1.79.0, requested ~> 1.79)"
    pat = re.compile(r"^(\S+)\s+\(newest ([0-9][0-9.]*), installed ([0-9][0-9.]*)")
    for line in proc.stdout.splitlines():
        m = pat.match(line.strip())
        if not m:
            continue
        name, latest, current = m.group(1), m.group(2), m.group(3)
        findings.append(
            Finding("bundler", "ruby binding", name, current, latest, _severity(current, latest))
        )
    if not findings and proc.returncode != 0:
        return [
            Finding("bundler", "ruby binding", "(bundle outdated inconclusive)", "", "", "unknown")
        ]
    return findings


SEV_ORDER = {"major": 0, "minor": 1, "unknown": 2, "pinned": 3, "current": 4, "skipped": 5}
SEV_LABEL = {
    "major": "⚠️  MAJOR behind",
    "minor": "    minor/patch",
    "unknown": "    unknown",
    "pinned": "    pinned (intentional)",
    "current": "    current",
    "skipped": "    skipped",
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit dependency freshness across every manifest.")
    ap.add_argument(
        "--strict", action="store_true", help="exit 1 if any dependency is a MAJOR version behind"
    )
    ap.add_argument("--offline", action="store_true", help="skip network (crates.io) checks")
    ap.add_argument(
        "--all", action="store_true", help="list current/up-to-date deps too (default: only drift)"
    )
    args = ap.parse_args()

    findings = audit_cargo(offline=args.offline) + audit_npm() + audit_bundler()
    findings.sort(key=lambda f: (SEV_ORDER.get(f.severity, 9), f.ecosystem, f.source, f.name))

    majors = [f for f in findings if f.severity == "major"]
    shown = (
        findings if args.all else [f for f in findings if f.severity not in {"current", "skipped"}]
    )

    print("Dependency freshness audit (every manifest, not just dependabot's)\n")
    if not shown:
        print("  ✅ all audited dependencies are current.")
    else:
        width = max((len(f.name) for f in shown), default=4)
        for f in shown:
            print(
                f"  {SEV_LABEL.get(f.severity, f.severity):<24}"
                f"{f.ecosystem:<9}{f.source:<15}{f.name:<{width}}  {f.current} → {f.latest}"
            )

    skipped = [f for f in findings if f.severity == "skipped"]
    for f in skipped:
        print(f"\n  note: {f.ecosystem} ({f.source}) not audited — {f.name.strip('()')}.")

    print("\n  (Python/uv is dependabot-watched; this audit covers the manifests it does not.)")

    if majors:
        print(f"\n  {len(majors)} dependency(ies) a MAJOR version behind:")
        for f in majors:
            print(f"    - {f.source} {f.name}: {f.current} → {f.latest}")
        if args.strict:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
