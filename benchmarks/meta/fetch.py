"""Provisioning: pull each benchmark's artifact from its upstream, once.

The earlier design made every academic corpus a manual download, on the argument
that copying an attack corpus into this repository would make it disarm's corpus.
That argument is about **vendoring**, and it does not reach **caching**: a file
fetched from its upstream URL into a scratch directory is still the upstream's
corpus, still versioned by whoever publishes it, and still not something a commit
here can quietly edit. Conflating the two left twenty-one suites unrunnable for
no benefit.

So a run provisions what it needs and leaves alone anything already present. What
survives from the original argument is the part that was actually load-bearing:
nothing fetched is ever committed, and every download is recorded with its URL,
digest, size and licence, so a number can always be traced to the bytes it came
from.

Three things this deliberately does not do. It does not overwrite an existing
file — an operator who has placed a specific revision keeps it. It does not
invent a URL: a suite with no verified upstream stays manual and says so, rather
than implying a download that has never been shown to exist. And it does not
reach the network at all under ``--offline``.
"""

from __future__ import annotations

import hashlib
import json
import os
import tarfile
import time
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

CACHE = Path(os.environ.get("DISARM_META_CACHE", "/tmp/disarm_meta_cache"))
MANIFEST = "fetch-manifest.json"
#: Long enough for a 90 MB research corpus on a slow link, short enough that a
#: dead host fails the run rather than hanging it.
TIMEOUT = 120


@dataclass(frozen=True)
class Source:
    """One upstream artifact, named precisely enough to cite.

    ``sha256`` is optional and, when set, enforced: a mismatch aborts rather than
    scoring against unexpected bytes. It is left unset for artifacts that
    legitimately move (a ``latest`` UCD file, a repository's default branch), and
    the digest actually seen is recorded in the manifest either way.
    """

    url: str
    filename: str
    licence: str
    #: ``file`` | ``zip`` | ``tar.gz`` — archives are expanded into a directory
    #: named after ``filename``.
    kind: str = "file"
    #: For an archive, the sub-path to hand back to the suite.
    member: str | None = None
    sha256: str | None = None
    note: str = ""


@dataclass
class Fetched:
    source: Source
    path: Path
    sha256: str
    bytes: int
    from_cache: bool
    fetched_at: str = ""


@dataclass
class Provisioning:
    """What one run pulled, or could not."""

    fetched: list[Fetched] = field(default_factory=list)
    failed: list[tuple[Source, str]] = field(default_factory=list)
    skipped_offline: list[Source] = field(default_factory=list)

    @property
    def downloaded(self) -> list[Fetched]:
        return [f for f in self.fetched if not f.from_cache]

    @property
    def reused(self) -> list[Fetched]:
        return [f for f in self.fetched if f.from_cache]


def _digest(path: Path) -> tuple[str, int]:
    h, size = hashlib.sha256(), 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def _target(source: Source, cache: Path) -> Path:
    base = cache / source.filename
    if source.kind == "file":
        return base
    return base / source.member if source.member else base


def _download(source: Source, cache: Path) -> Path:
    """Fetch to a temporary name and move into place only once complete.

    An interrupted download must not leave a short file that the next run treats
    as cached and scores against.
    """
    cache.mkdir(parents=True, exist_ok=True)
    raw = cache / (source.filename if source.kind == "file" else f"{source.filename}.archive")
    raw.parent.mkdir(parents=True, exist_ok=True)
    part = raw.with_suffix(raw.suffix + ".part")
    request = Request(source.url, headers={"User-Agent": "disarm-meta-benchmark"})
    with urlopen(request, timeout=TIMEOUT) as response, open(part, "wb") as out:  # noqa: S310
        while chunk := response.read(1 << 20):
            out.write(chunk)
    part.replace(raw)

    if source.kind == "file":
        return raw
    dest = cache / source.filename
    dest.mkdir(parents=True, exist_ok=True)
    if source.kind == "zip":
        with zipfile.ZipFile(raw) as z:
            _safe_extract_zip(z, dest)
    elif source.kind == "tar.gz":
        with tarfile.open(raw, "r:gz") as t:
            _safe_extract(t, dest)
    else:
        raise ValueError(f"unknown source kind: {source.kind}")
    raw.unlink(missing_ok=True)
    return dest / source.member if source.member else dest


def _safe_extract_zip(archive: zipfile.ZipFile, dest: Path) -> None:
    """The same rule for zip archives.

    CodeQL flagged only the tar path, because that is the only archive kind any
    registered source uses today. The zip branch has the identical defect and is
    fixed with it rather than left for the first zip source to reintroduce.
    `ZipFile.extract` already refuses absolute paths and `..`, but it does so
    silently by mangling the name; refusing outright is the behaviour that
    matches the tar path.
    """
    root = dest.resolve()
    for name in archive.namelist():
        target = (root / name).resolve()
        if not target.is_relative_to(root):
            raise ValueError(f"archive member escapes the destination: {name}")
    archive.extractall(dest)  # noqa: S202 - every member checked above


def _safe_extract(tar: tarfile.TarFile, dest: Path) -> None:
    """Extract, refusing any member that would write outside ``dest``.

    The name check alone is not enough, which is what CodeQL flagged. A member
    can sit inside ``dest`` by name and still write outside it: a symlink or
    hardlink entry whose *linkname* points up and out, followed by a second
    member that writes through it. `member.name` is innocent in both.

    PEP 706's ``data`` filter is the check that covers the whole family — link
    escape, absolute paths, device nodes, setuid bits — and it is applied by
    the extraction itself rather than in a separate pass, so there is no window
    between validating and writing. The explicit loop is kept in front of it
    because it names the offending member in the error, which the filter's own
    exception does not always do as clearly.
    """
    root = dest.resolve()
    for member in tar.getmembers():
        target = (root / member.name).resolve()
        if not target.is_relative_to(root):
            raise ValueError(f"archive member escapes the destination: {member.name}")
        if member.islnk() or member.issym():
            link = (target.parent / member.linkname).resolve()
            if not link.is_relative_to(root):
                raise ValueError(
                    f"archive member links outside the destination: "
                    f"{member.name} -> {member.linkname}"
                )
    tar.extractall(dest, filter="data")


def ensure(
    source: Source,
    cache: Path | None = None,
    offline: bool = False,
    refresh: bool = False,
) -> Fetched | None:
    """Make ``source`` available locally, leaving an existing copy untouched."""
    cache = cache or CACHE
    target = _target(source, cache)
    if target.exists() and not refresh:
        digest, size = _digest(target) if target.is_file() else ("", _tree_bytes(target))
        return Fetched(source, target, digest, size, from_cache=True)
    if offline:
        return None
    path = _download(source, cache)
    digest, size = _digest(path) if path.is_file() else ("", _tree_bytes(path))
    if source.sha256 and digest and digest != source.sha256:
        raise ValueError(f"{source.filename}: expected sha256 {source.sha256}, got {digest}")
    return Fetched(
        source,
        path,
        digest,
        size,
        from_cache=False,
        fetched_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )


def _tree_bytes(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def provision(
    sources: Sequence[Source],
    cache: Path | None = None,
    offline: bool = False,
    refresh: bool = False,
) -> Provisioning:
    """Fetch everything a selection needs, then record what was pulled."""
    cache = cache or CACHE
    result = Provisioning()
    for source in sources:
        if offline and not _target(source, cache).exists():
            result.skipped_offline.append(source)
            continue
        try:
            got = ensure(source, cache, offline=offline, refresh=refresh)
        except (URLError, OSError, ValueError, zipfile.BadZipFile, tarfile.TarError) as exc:
            result.failed.append((source, f"{type(exc).__name__}: {exc}"))
            continue
        if got is None:
            result.skipped_offline.append(source)
        else:
            result.fetched.append(got)
    _write_manifest(result, cache)
    return result


def _write_manifest(result: Provisioning, cache: Path) -> None:
    """Record URL, digest, size and licence for everything present.

    The manifest is the audit trail: it is what lets a figure in a document be
    traced back to the exact bytes it was computed from.
    """
    if not result.fetched:
        return
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / MANIFEST
    existing: dict[str, object] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            existing = {}
    for item in result.fetched:
        prior = existing.get(item.source.filename)
        was = prior.get("fetched_at", "") if isinstance(prior, dict) else ""
        existing[item.source.filename] = {
            "url": item.source.url,
            "licence": item.source.licence,
            "sha256": item.sha256,
            "bytes": item.bytes,
            "path": str(item.path),
            # A cached artifact keeps the timestamp of the run that pulled it.
            "fetched_at": item.fetched_at or was,
            "note": item.source.note,
        }
    path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
