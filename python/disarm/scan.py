"""Walk a tree and report anomalies, for `disarm scan` (#704).

`inspect_anomalies` returns findings with byte spans, a kind, evidence and a
plain-language reason — everything a scanner needs — and until now there was no way to
point it at a file. That single absence is most of why third-party tools in this space
exist as separate projects rather than as thin wrappers: the detection is the hard part
and disarm has it, while the file plumbing is the easy part and disarm had none of it.

Python rather than a Rust binary, which is #704's own recommendation and its reasoning:
this is plumbing over an API that already exists, so it ships now and can be measured
against real repositories before anyone commits to releasing binaries per tag.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, TextIO

from disarm import inspect_anomalies

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

#: Directories that hold no hand-written source, so skipping them hides nothing.
#:
#: `build`, `dist`, `out`, `target`, `bin` and `vendor` are **deliberately absent**. They
#: are generated in some projects and hand-written in others, and a scanner that skips
#: them by name reports clean on a tree it never read. #704 takes that distinction from
#: `juriku/untrace`, and it is the difference between a default and a guess.
DEFAULT_SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        ".tox",
        ".nox",
        ".venv",
        "venv",
        "node_modules",
        ".terraform",
        ".gradle",
        ".idea",
        ".vscode",
    }
)

#: A file larger than this is not scanned. Nothing here streams, and a finding needs the
#: whole string in memory to report a span into it.
MAX_FILE_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class ScanFinding:
    """One anomaly, located for a report rather than for the library.

    `Finding.start`/`end` are byte offsets, which are right for disarm and wrong for
    something a person or an editor reads. `line` and `column` are 1-based, and `column`
    counts **characters**, because that is what an editor's gutter shows.
    """

    path: str
    line: int
    column: int
    kind: str
    reason: str
    token: str
    #: The library's evidence string — `U+202E`, `U+200B ×16`, a scheme name. This is the
    #: "character" half of the fingerprint: what was found, independent of where.
    detail: str
    #: Stable across edits that move the finding. See `fingerprint_for` for the rule.
    fingerprint: str

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "kind": self.kind,
            "reason": self.reason,
            "token": self.token,
            "detail": self.detail,
            "fingerprint": self.fingerprint,
        }

    def render(self) -> str:
        return f"{self.path}:{self.line}:{self.column}: {self.kind}: {self.reason}"


def fingerprint_for(path: str, kind: str, detail: str, occurrence: int) -> str:
    """The identity of a finding that survives an edit (#705).

    **File, what was found, and which occurrence of it this is — never the line.** The
    naive fingerprint is file + line + column, and it breaks on the first commit that
    inserts a paragraph: every finding below the insertion looks new. Keying on the
    occurrence index instead means inserting text *above* a finding does not raise a
    second alert for it.

    **The honest limit, which belongs beside the rule.** Two occurrences of the same
    `(kind, detail)` in one file are told apart only by their order. Inserting a *second*
    occurrence above a recorded first accepts the new one and reports the old: the count
    stays right and nothing is silently dropped, but which occurrence is named can swap.
    That is the trade for surviving ordinary edits, taken from `juriku/untrace`.

    `path` is the path as scanned, so a baseline written from the repository root has to
    be applied from the repository root. It is POSIX-separated on every host — see
    `_portable` — so a baseline written on Windows applies on Linux, and the SARIF `uri`
    carries the same form.
    """
    ident = f"{path}\0{kind}\0{detail}\0{occurrence}".encode("utf-8", "surrogatepass")
    return hashlib.sha256(ident).hexdigest()[:24]


#: The on-disk shape. `version` is here so a later change to the rule can refuse an old
#: file rather than silently matching nothing.
BASELINE_VERSION = 1


def load_baseline(path: Path) -> set[str]:
    """The fingerprints a baseline file accepts.

    Refuses, by name, a version it does not know and a shape it does not expect. Every
    refusal is a `ValueError`, which the CLI reports as an error and exit 1: a baseline
    that cannot be used must not read as "nothing was found", and must not be a
    traceback either.
    """
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: not a baseline file: {exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: not a baseline file: expected an object")
    if doc.get("version") != BASELINE_VERSION:
        msg = f"{path}: baseline version {doc.get('version')!r}, expected {BASELINE_VERSION}"
        raise ValueError(msg)
    fps = doc.get("fingerprints", [])
    if not isinstance(fps, list) or not all(isinstance(f, str) for f in fps):
        raise ValueError(f"{path}: baseline fingerprints must be a list of strings")
    return set(fps)


def write_baseline(path: Path, findings: Iterable[ScanFinding]) -> int:
    """Record every current finding so only what arrives afterwards fails the check.

    A repository with years of history will not be clean on its first scan, and requiring
    it to be clean before the check can be turned on is the order that stops adoption.
    Sorted, so the file diffs cleanly as it shrinks.
    """
    fps = sorted({f.fingerprint for f in findings})
    path.write_text(
        json.dumps({"version": BASELINE_VERSION, "fingerprints": fps}, indent=2) + "\n",
        encoding="utf-8",
    )
    return len(fps)


@dataclass
class ScanResult:
    findings: list[ScanFinding]
    scanned: int
    #: Paths that could not be read, with the reason. Not the same as a finding, which is
    #: why they get their own exit code (#704 item 4).
    unreadable: list[tuple[str, str]]


def _git_ignored(root: Path, paths: list[Path]) -> set[Path]:
    """The subset of `paths` git would ignore, asked of git itself.

    **The three-source rule is delegated, not reimplemented.** git reads `.gitignore` in
    the scanned directory *and every parent up to the repository root*, plus
    `.git/info/exclude`, plus the global `core.excludesFile`. A scanner that reads only the
    nearest file gives different answers for `disarm scan src/` and `disarm scan .` on one
    tree — a bug users report as flakiness (#704 item 1). `git check-ignore` applies all
    three by construction, so the two cannot disagree.

    Returns an empty set when git is unavailable or the tree is not a repository, which is
    a scan with no ignore rules rather than an error.
    """
    if not paths:
        return set()
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, paths on stdin
            ["git", "--no-optional-locks", "check-ignore", "--stdin"],  # noqa: S607
            cwd=root,
            input="\n".join(str(p) for p in paths),
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    # 0 = some paths ignored, 1 = none ignored, 128 = not a repository.
    if proc.returncode not in (0, 1):
        return set()
    return {Path(line) for line in proc.stdout.splitlines() if line}


def _line_and_column(text: str, byte_offset: int) -> tuple[int, int]:
    """Convert a byte offset into a 1-based (line, character column)."""
    prefix = text.encode("utf-8")[:byte_offset].decode("utf-8", errors="ignore")
    line = prefix.count("\n") + 1
    last_break = prefix.rfind("\n")
    column = len(prefix) - last_break
    return line, column


def iter_files(
    roots: Iterable[Path],
    *,
    skip_dirs: frozenset[str] = DEFAULT_SKIP_DIRS,
    use_gitignore: bool = True,
    on_error: Callable[[OSError], None] | None = None,
) -> Iterator[Path]:
    """Yield the files under `roots`, in a stable order.

    **Symlinks are never followed**, so a scan stays inside the tree it was pointed at
    (#704 item 3). That applies to directory links, which could otherwise walk out of the
    tree or loop, and to file links, which would report a finding against a path whose
    content lives somewhere else.
    """
    for root in roots:
        if root.is_symlink():
            # `is_file()` and `is_dir()` resolve links, so without this a root that is
            # itself a symlink was followed — `disarm scan <link>` walked whatever it
            # pointed at, outside the tree the contract promises to stay in (caught in
            # review on #944). Reported rather than skipped: a root the scanner refused
            # must not look like a root that scanned clean.
            if on_error is not None:
                on_error(OSError(0, "is a symlink; not followed", str(root)))
            continue
        if root.is_file():
            yield root
            continue
        if not root.is_dir():
            # `os.walk` on a path that does not exist yields nothing and raises nothing,
            # so without this a typo'd path scanned "cleanly" with exit 0 — the exact
            # thing the exit-code contract exists to prevent. Caught by the first run of
            # `TestTheExitCodeContract`.
            if on_error is not None:
                on_error(FileNotFoundError(2, "No such file or directory", str(root)))
            continue
        candidates: list[Path] = []
        # `onerror` for the same reason: a subdirectory that cannot be listed is
        # otherwise skipped in silence, and silence looks like clean.
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False, onerror=on_error):
            here = Path(dirpath)
            dirnames[:] = sorted(
                d for d in dirnames if d not in skip_dirs and not (here / d).is_symlink()
            )
            candidates.extend(
                here / name for name in sorted(filenames) if not (here / name).is_symlink()
            )
        ignored = (
            _git_ignored(root if root.is_dir() else root.parent, candidates)
            if use_gitignore
            else set()
        )
        for path in candidates:
            if path not in ignored and _relative_to(path, root) not in ignored:
                yield path


def _relative_to(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def _portable(path: PurePath) -> str:
    """The path as a finding, a fingerprint and a SARIF `uri` carry it: POSIX-separated.

    `str(path)` on Windows carries backslashes, which would make every fingerprint — and so
    every baseline — platform-dependent. `as_posix` converts the separator on Windows and
    is the identity on POSIX, where a backslash is an ordinary filename character.
    """
    return path.as_posix()


def scan_paths(
    roots: Iterable[Path],
    *,
    skip_dirs: frozenset[str] = DEFAULT_SKIP_DIRS,
    use_gitignore: bool = True,
    max_bytes: int = MAX_FILE_BYTES,
) -> ScanResult:
    """Scan `roots` and return every anomaly, with the paths that could not be read."""
    findings: list[ScanFinding] = []
    unreadable: list[tuple[str, str]] = []
    scanned = 0

    def record(exc: OSError) -> None:
        unreadable.append((exc.filename or "?", exc.strerror or str(exc)))

    for path in iter_files(
        roots, skip_dirs=skip_dirs, use_gitignore=use_gitignore, on_error=record
    ):
        try:
            raw = path.read_bytes()
        except OSError as exc:
            unreadable.append((_portable(path), exc.strerror or str(exc)))
            continue
        if len(raw) > max_bytes or b"\x00" in raw:
            continue  # too large to hold, or binary — neither is an error
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue  # not UTF-8 text; `decode_to_utf8` is a different job
        scanned += 1
        report = inspect_anomalies(text)
        # Occurrence index per (kind, detail) within THIS file, in report order — which is
        # byte order, so "which occurrence" means "how many earlier in the file".
        seen: dict[tuple[str, str], int] = {}
        for finding in report.findings:
            line, column = _line_and_column(text, finding.start)
            key = (finding.kind, finding.detail)
            occurrence = seen.get(key, 0)
            seen[key] = occurrence + 1
            findings.append(
                ScanFinding(
                    path=_portable(path),
                    line=line,
                    column=column,
                    kind=finding.kind,
                    reason=finding.reason,
                    token=finding.token,
                    detail=finding.detail,
                    fingerprint=fingerprint_for(
                        _portable(path), finding.kind, finding.detail, occurrence
                    ),
                )
            )
    return ScanResult(findings=findings, scanned=scanned, unreadable=unreadable)


#: SARIF `level` per anomaly kind (#705).
#:
#: A decoded payload is the one finding that needs no threshold to interpret, so it is the
#: one `error`. The rest are `warning`: each reports a technical fact and leaves the
#: judgement to the caller, which is the library's stated stance. Hard-coded HERE rather
#: than on `AnomalyKind`: #705 item 4 says a severity on the enum is a public API addition
#: and should be its own change, so this writer carries the map and a test asserts it
#: covers every kind the library can produce — the map cannot fall behind the enum.
SARIF_LEVELS: dict[str, str] = {
    "smuggled": "error",
    "invisible": "warning",
    "bidi": "warning",
    "bidi_mixed": "warning",
    "control": "warning",
    "deletion": "warning",
    "mixed_script": "warning",
    "confusable": "warning",
    "compat_fold": "warning",
    "zalgo": "warning",
    "enclosing_mark": "warning",
    "duplicate_mark": "warning",
    "mixed_numbers": "warning",
    "leet": "warning",
    "segmentation": "warning",
}


def to_sarif(result: ScanResult, *, version: str) -> dict[str, object]:
    """A SARIF 2.1.0 document, so findings land in a Security tab and as PR annotations.

    One rule per kind seen, one result per finding, with `partialFingerprints` carrying
    the disarm fingerprint so a consumer that does its own baselining keys on the same
    identity this tool does.
    """
    kinds = sorted({f.kind for f in result.findings})
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "disarm",
                        "version": version,
                        "informationUri": "https://github.com/raeq/disarm",
                        "rules": [
                            {
                                "id": k,
                                "shortDescription": {"text": f"disarm anomaly kind `{k}`"},
                                "defaultConfiguration": {"level": SARIF_LEVELS.get(k, "warning")},
                            }
                            for k in kinds
                        ],
                    }
                },
                "results": [
                    {
                        "ruleId": f.kind,
                        "level": SARIF_LEVELS.get(f.kind, "warning"),
                        "message": {"text": f.reason},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": f.path},
                                    "region": {"startLine": f.line, "startColumn": f.column},
                                }
                            }
                        ],
                        "partialFingerprints": {"disarm/v1": f.fingerprint},
                    }
                    for f in result.findings
                ],
            }
        ],
    }


#: Exit codes, so CI can tell the outcomes apart (#704 item 4).
#:
#: `2` is skipped on purpose: argparse exits 2 on a usage error, and `docs/cli.md`'s
#: table already assigns it. Reusing it would make "you typed the flag wrong" and "a
#: file could not be read" the same number, which is the confusion the contract exists
#: to prevent — something found (1) and something failed to read (3) are different facts.
EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_READ_ERROR = 3


def run(
    roots: list[Path],
    *,
    as_json: bool = False,
    as_sarif: bool = False,
    fail: bool = False,
    use_gitignore: bool = True,
    baseline: Path | None = None,
    write_baseline_to: Path | None = None,
    out: TextIO | None = None,
) -> int:
    """Run a scan and print it. Returns the process exit code.

    **Something found is not something failed to read**, and the codes say so: `1` means
    findings with `--fail`, `3` means a path could not be read (`2` belongs to argparse).
    A tree that scanned cleanly and a tree that could not be opened must not look alike
    to CI.
    """
    stream = out if out is not None else sys.stdout
    result = scan_paths(roots, use_gitignore=use_gitignore)

    if write_baseline_to is not None:
        n = write_baseline(write_baseline_to, result.findings)
        print(f"wrote {n} fingerprint(s) to {write_baseline_to}", file=stream)
        return EXIT_READ_ERROR if result.unreadable else EXIT_OK

    suppressed = 0
    stale: list[str] = []
    if baseline is not None:
        accepted = load_baseline(baseline)
        present = {f.fingerprint for f in result.findings}
        # A baselined finding is counted and not shown. One that no longer exists is
        # reported as stale rather than quietly kept, so the file shrinks as the tree is
        # cleaned instead of accumulating acceptances for findings that are gone.
        stale = sorted(accepted - present)
        kept = [f for f in result.findings if f.fingerprint not in accepted]
        suppressed = len(result.findings) - len(kept)
        result = ScanResult(findings=kept, scanned=result.scanned, unreadable=result.unreadable)

    from disarm import __version__

    if as_sarif:
        print(json.dumps(to_sarif(result, version=__version__), indent=2), file=stream)
    elif as_json:
        print(
            json.dumps(
                {
                    "findings": [f.as_dict() for f in result.findings],
                    "scanned": result.scanned,
                    "unreadable": [{"path": p, "error": e} for p, e in result.unreadable],
                },
                indent=2,
                ensure_ascii=False,
            ),
            file=stream,
        )
    else:
        for finding in result.findings:
            print(finding.render(), file=stream)
        summary = f"scanned {result.scanned} file(s), {len(result.findings)} finding(s)"
        if suppressed:
            summary += f", {suppressed} baselined"
        print(summary, file=stream)
    for fp in stale:
        print(f"stale: baseline entry {fp} matches no current finding", file=sys.stderr)
    for path, error in result.unreadable:
        print(f"error: {path}: {error}", file=sys.stderr)
    if result.unreadable:
        return EXIT_READ_ERROR
    if result.findings and fail:
        return EXIT_FINDINGS
    return EXIT_OK
