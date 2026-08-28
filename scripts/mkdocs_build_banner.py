"""MkDocs hook: stamp every page with the commit it was built from and the
version a reader can actually install (#641).

The site deploys from ``main`` on every push (``.github/workflows/docs.yml``);
the package a reader installs comes from the newest tag. Between releases those
are different code, and no page said so. At the worst point ``main`` was 68
commits ahead of ``v0.13.0`` and ``docs/security/cve-validation.md`` named four
entry points that did not exist in the release it was describing.

This is the reader-facing half of #641. The machine-facing half is
``scripts/check_docs_against_release.py``, which names the gap out loud.

Wired in through ``mkdocs.yml``'s ``hooks:`` list, so it needs no plugin and no
theme override — the banner is injected as Markdown and rendered by the
``admonition`` extension that is already enabled.

Both facts come from the environment when CI supplies them and are worked out
locally otherwise, so ``mkdocs serve`` shows the same banner a deploy does.
"""

from __future__ import annotations

import os
import re
import subprocess  # noqa: S404 — reading our own git metadata, no user input
from pathlib import Path
from typing import Any

import tomllib

_ROOT = Path(__file__).resolve().parent.parent

#: The banner is about the gap between the site and the released package, which
#: is a Python-package statement. The changelog carries its own version history
#: on every line, so a banner above it is noise.
_SKIP_PAGES = frozenset({"CHANGELOG.md"})

#: Matches the first ATX H1 so the banner lands under the page title rather than
#: above it. Pages that open with something else get it prepended.
_FIRST_H1 = re.compile(r"^# .*$", re.MULTILINE)


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
    """
    value = os.environ.get("DISARM_DOCS_RELEASE", "").strip()
    if value:
        return value
    try:
        data = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    version = data.get("project", {}).get("version")
    return str(version) if version else None


def _banner(commit: str | None, released: str | None) -> str | None:
    """Render the admonition, or ``None`` when there is nothing true to say."""
    if commit is None and released is None:
        return None

    repo = "https://github.com/raeq/disarm"
    if released:
        title = f"Built from `main`. The published release is `{released}`."
    else:
        title = "Built from `main`, not from a release."

    lines = [f'!!! info "{title}"']
    if commit:
        lines.append(
            f"    This page describes [`{commit}`]({repo}/commit/{commit}) on `main`. "
            "The site deploys on every push; the package deploys on a tag."
        )
    if released:
        lines.append(
            f"    Anything documented here that landed after `{released}` is **not** in "
            f"the package you get from `pip install disarm`. The "
            f"[changelog](https://docs.disarm.dev/CHANGELOG.html) says what is in which "
            f"release, and [releases]({repo}/releases) is the tag list."
        )
    else:
        lines.append(
            "    This build could not determine the published version, so treat every "
            "claim on this page as describing `main` rather than a release."
        )
    return "\n".join(lines) + "\n\n"


# Computed once per build rather than per page: neither answer can change while
# mkdocs is running, and `mkdocs serve` would otherwise shell out to git on
# every rebuild of every page.
_BANNER = _banner(_build_commit(), _released_version())


def on_page_markdown(
    markdown: str,
    page: Any,  # noqa: ANN401 — mkdocs.structure.pages.Page, not importable cheaply
    config: Any,  # noqa: ANN401 — mkdocs.config.defaults.MkDocsConfig
    files: Any,  # noqa: ANN401 — mkdocs.structure.files.Files
) -> str:
    """Insert the banner under the page's first H1 (mkdocs hook entry point)."""
    del config, files  # part of the hook signature; unused here

    if _BANNER is None:
        return markdown
    if getattr(page.file, "src_uri", None) in _SKIP_PAGES:
        return markdown

    match = _FIRST_H1.search(markdown)
    if match is None:
        return _BANNER + markdown
    cut = match.end()
    return f"{markdown[:cut]}\n\n{_BANNER}{markdown[cut:].lstrip(chr(10))}"
