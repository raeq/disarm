"""MkDocs hook: expose the commit a page was built from and the version a reader
can actually install, for the footer to render (#641, #692).

The site deploys from ``main`` on every push (``.github/workflows/docs.yml``);
the package a reader installs comes from the newest tag. Between releases those
are different code, and no page said so. At the worst point ``main`` was 68
commits ahead of ``v0.13.0`` and ``docs/security/cve-validation.md`` named four
entry points that did not exist in the release it was describing.

This is the reader-facing half of #641. The machine-facing half is
``scripts/check_docs_against_release.py``, which names the gap out loud.

Originally this injected an ``!!! info`` admonition under every page's H1. That
put a five-line box above the first sentence of all 91 pages, which is far more
weight than a provenance note earns. The facts are now published into
``config.extra`` and rendered once in the footer by ``overrides/main.html``, so
they stay on every page without displacing the content.

Both facts come from the environment when CI supplies them and are worked out
locally otherwise, so ``mkdocs serve`` shows the same footer a deploy does.
"""

from __future__ import annotations

import os
import re
import subprocess  # noqa: S404 — reading our own git metadata, no user input
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent

#: ``version = "0.14.1"`` inside a TOML table.
_TOML_VERSION = re.compile(r'^version\s*=\s*"([^"]+)"')


def _git(*args: str) -> str | None:
    """Run a read-only git command, or return ``None`` when git cannot answer.

    A docs build from an sdist or a shallow export has no repository, which is a
    reason to omit the commit rather than to fail the build.
    """
    try:
        out = subprocess.run(  # noqa: S603 — fixed argv, no shell
            ["git", "--no-optional-locks", *args],
            cwd=_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def _build_commit() -> str | None:
    """The commit this build describes, shortest reliable form first."""
    for env in ("DISARM_DOCS_COMMIT", "GITHUB_SHA"):
        value = os.environ.get(env, "").strip()
        if value:
            return value[:7]
    return _git("rev-parse", "--short=7", "HEAD")


def _released_version() -> str | None:
    """The newest version a reader can install.

    ``DISARM_DOCS_RELEASE`` is what CI passes after asking PyPI. The fallback is
    ``pyproject.toml``, which on ``main`` holds the version of the last release
    — the release PR is the thing that moves it. That fallback is wrong only
    inside the release PR itself, between the version bump and the publish,
    which is a window of minutes and always overstates by exactly one version.

    Neither source is refreshed by publishing. ``docs.yml`` is path-filtered, so
    a release that touches no ``docs/**`` file never rebuilds the site and the
    footer keeps naming the previous version — which is how the site sat on
    ``0.14.0`` after ``0.14.1`` shipped. ``docs.yml`` now also runs on
    ``release: [published]`` for that reason.
    """
    value = os.environ.get("DISARM_DOCS_RELEASE", "").strip()
    if value:
        return value
    try:
        text = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    except OSError:
        return None
    return _project_version(text)


def _project_version(pyproject: str) -> str | None:
    """``project.version`` from ``pyproject.toml``, scanned rather than parsed.

    ``tomllib`` is Python 3.11+ and this project's floor is 3.10
    (``requires-python``), so a contributor on 3.10 running ``mkdocs serve``
    would take an ``ImportError`` before the build started. One key from one
    known table does not need a parser; walking to the ``[project]`` header is
    what keeps a ``version`` in some other table from being picked up.
    """
    in_project = False
    for line in pyproject.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_project = stripped == "[project]"
            continue
        if in_project:
            match = _TOML_VERSION.match(stripped)
            if match:
                return match.group(1)
    return None


def on_config(config: Any) -> Any:  # noqa: ANN401 — mkdocs.config.defaults.MkDocsConfig
    """Publish the build facts into ``config.extra`` for the footer template.

    Computed once per build rather than per page: neither answer can change
    while mkdocs is running, and the previous per-page hook shelled out to git
    on every rebuild of every page under ``mkdocs serve``.
    """
    extra = config.setdefault("extra", {}) or {}
    extra["build_commit"] = _build_commit()
    extra["released_version"] = _released_version()
    config["extra"] = extra
    return config
