#!/usr/bin/env python3
"""Assert that every ``disarm`` name the documentation uses exists in the
installed package (#641).

The problem this exists for
---------------------------
``docs/`` is unusually well gated. ``TestDocsMatrixDrift`` derives the CVE
table from the registry, Sybil executes the cookbook pages, ``check_doc_claims``
lints the prose. Every one of those gates runs against ``main``.

A reader runs ``pip install disarm``, which gives them the newest *tag*. At the
worst point ``main`` was 68 commits ahead of ``v0.13.0``, and
``docs/security/cve-validation.md`` named four entry points — ``is_case_fold_stable``,
``find_key_collisions``, ``unmapped_confusables``, ``find_unmapped_confusables``
— that raised ``AttributeError`` on the release it was describing. Nothing was
red, because nothing compared the docs to the artifact.

This script is that comparison. Point it at an interpreter with the newest
published wheel installed and it fails when the docs name something that wheel
does not have.

What counts as "the docs using a name"
--------------------------------------
Three sources, chosen because each one is a claim a reader can act on:

* ``from disarm import ...`` and ``disarm.name`` inside Python fenced blocks —
  code somebody will copy;
* ``::: disarm.name`` mkdocstrings directives — the API reference pages, which
  render nothing at all when the name is gone;
* inline code spans that are exactly ``disarm.name`` — prose naming an entry
  point.

Prose mentioning a bare ``canonicalize`` is deliberately not matched. Without
the ``disarm.`` prefix there is no way to tell an entry point from an English
word, and guessing produces a gate people learn to ignore.

Usage
-----
    python scripts/check_docs_against_release.py
    python scripts/check_docs_against_release.py --root docs --root README.md

Exit status is 1 when any documented name is missing, 0 otherwise.
"""

from __future__ import annotations

import argparse
import ast
import importlib
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

#: Default scan set. README is included because it is the most-read file in the
#: project and it names entry points in prose (#656 covers its other problems).
_DEFAULT_ROOTS = ("docs", "README.md")

#: Fenced blocks whose contents are Python. ``pycon`` is the doctest-style
#: session used across the user guide.
_PY_FENCE_LANGS = frozenset({"python", "py", "python3", "pycon"})

_FENCE_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<ticks>`{3,}|~{3,})[ \t]*(?P<info>[^\n]*)\n"
    r"(?P<body>.*?)"
    r"^(?P=indent)(?P=ticks)[ \t]*$",
    re.DOTALL | re.MULTILINE,
)

#: ``::: disarm.normalize`` — the mkdocstrings identifier form.
_MKDOCSTRINGS_RE = re.compile(
    r"^[ \t]*:::[ \t]+(disarm(?:\.[A-Za-z_][A-Za-z0-9_]*)*)", re.MULTILINE
)

#: An inline code span that is *entirely* a dotted disarm path, with an optional
#: call suffix: `disarm.canonicalize`, `disarm.canonicalize()`. Anchoring both
#: ends is what keeps `docs.disarm.dev` and `pip install disarm` out.
_INLINE_RE = re.compile(r"`(disarm\.[A-Za-z_][A-Za-z0-9_.]*)(?:\(\))?`")

#: `disarm.rb` is a filename and `disarm.dev` is a hostname; neither is an
#: attribute, and no release could make them resolve. Only prose is filtered —
#: inside a Python block a dotted path is unambiguous, so filtering there would
#: hide a genuine wrong name.
_FILENAME_OR_HOST_TAILS = frozenset(
    """
    rb py pyi rs js mjs cjs ts tsx jsx kt java c h go swift
    json toml yml yaml md txt csv tsv html css xml cfg ini lock sh
    so dylib dll whl gem jar node exe
    dev com org io net app sh
    """.split()
)

#: Names that are documented but are not attributes of the module, so looking
#: them up would report a failure that no release could fix.
_NOT_ATTRIBUTES = frozenset(
    {
        # Dunder metadata that `getattr` finds but that says nothing about API.
        "disarm.__doc__",
        "disarm.__file__",
        "disarm.__name__",
        "disarm.__path__",
    }
)

#: Directories under ``docs/`` that are records rather than instructions. They
#: are dated snapshots of a past review, and correcting the API names in them to
#: match today's package would falsify the record. Neither is in ``mkdocs.yml``'s
#: nav, so no reader is routed to them for guidance.
_EXCLUDED_DIRS = frozenset({"reviews", "plans", "__pycache__"})

#: Known gaps, each with the issue that closes it. A gate whose first run is red
#: gets switched off, so the ratchet is: a name may sit here only while an issue
#: is open on it. Two checks stop the list outliving the fixes — ``main`` fails
#: when a listed name starts resolving, and ``test_every_gap_is_actually_named_by
#: _the_docs`` fails when the page that named it is gone.
_KNOWN_GAPS: dict[str, str] = {
    # #660 — `LANG_AUTO` is defined in `disarm._enums` and is the only `LANG_*`
    # constant missing from the package's export list, while three doc blocks
    # tell readers to `from disarm import LANG_AUTO`. Exporting a name is a new
    # capability, so the fix is a minor rather than this patch.
    "disarm.LANG_AUTO": "#660 — documented constant is never re-exported from `disarm`",
}


class Reference:
    """One documented use of a name, kept with where it was written."""

    __slots__ = ("dotted", "path", "line", "source")

    def __init__(self, dotted: str, path: Path, line: int, source: str) -> None:
        self.dotted = dotted
        self.path = path
        self.line = line
        self.source = source

    @property
    def where(self) -> str:
        # `--root` can name a path outside the repo, and `relative_to` raises
        # rather than returning an absolute path when it cannot make one.
        try:
            rel: Path | str = self.path.relative_to(_REPO_ROOT)
        except ValueError:
            rel = self.path
        return f"{rel}:{self.line}"


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _python_blocks(text: str) -> list[tuple[str, int]]:
    """Every Python fenced block, with the line its body starts on."""
    blocks: list[tuple[str, int]] = []
    for match in _FENCE_RE.finditer(text):
        info = match.group("info").strip().lower()
        # ``` python title="x"` and pymdownx's `{.python}` both appear in this tree.
        lang = info.lstrip("{.").split()[0].rstrip("}") if info else ""
        if lang in _PY_FENCE_LANGS:
            body = match.group("body")
            indent = len(match.group("indent"))
            if indent:
                body = "\n".join(
                    line[indent:] if line[:indent].isspace() else line for line in body.split("\n")
                )
            blocks.append((body, _line_of(text, match.start("body"))))
    return blocks


def _strip_pycon(body: str) -> str:
    """Turn a ``>>>`` session into something ``ast`` can parse.

    Output lines are dropped along with the prompts. A block that still fails to
    parse is handled by the caller — a deliberately broken example is a normal
    thing for docs to contain.
    """
    lines: list[str] = []
    for raw in body.split("\n"):
        stripped = raw.lstrip()
        if stripped.startswith((">>> ", "... ")):
            lines.append(raw[: len(raw) - len(stripped)] + stripped[4:])
        elif stripped in (">>>", "..."):
            lines.append("")
        else:
            lines.append("")
    return "\n".join(lines)


def _names_from_python(body: str) -> set[tuple[str, int]]:
    """Dotted disarm paths used by a Python block, with in-block line numbers."""
    found: set[tuple[str, int]] = set()

    source = body
    try:
        tree = ast.parse(source)
    except SyntaxError:
        source = _strip_pycon(body)
        try:
            tree = ast.parse(source)
        except SyntaxError:
            # An intentionally-invalid snippet. The regex pass below still sees
            # `disarm.x`, so nothing is silently skipped.
            tree = None

    if tree is not None:
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.split(".")[0] == "disarm"
            ):
                prefix = node.module
                for alias in node.names:
                    if alias.name != "*":
                        found.add((f"{prefix}.{alias.name}", node.lineno))
            elif isinstance(node, ast.Attribute):
                dotted = _dotted(node)
                if dotted and dotted.split(".")[0] == "disarm":
                    found.add((dotted, node.lineno))

    # Regex backstop for blocks `ast` refused, and for `disarm.x` written inside
    # a string or comment in a block that did parse. Runs against the original
    # body rather than `source`: the pycon fallback blanks every line that is not
    # a prompt, so a block that failed to parse for any *other* reason would come
    # through here empty.
    for match in re.finditer(r"\bdisarm(?:\.[A-Za-z_][A-Za-z0-9_]*)+", body):
        found.add((match.group(0), _line_of(body, match.start())))

    return found


def _dotted(node: ast.expr) -> str | None:
    """Flatten ``a.b.c`` into a string; ``None`` for anything else."""
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return ".".join(reversed(parts))


def prose_names(text: str) -> list[tuple[str, int]]:
    """Dotted disarm paths written as inline code spans, with line numbers.

    Filtered against `_FILENAME_OR_HOST_TAILS`, which is why this is a function
    rather than a bare `finditer` at the call site — the filter is part of what
    the pattern means.
    """
    out: list[tuple[str, int]] = []
    for match in _INLINE_RE.finditer(text):
        dotted = match.group(1)
        if dotted.rsplit(".", 1)[-1].lower() in _FILENAME_OR_HOST_TAILS:
            continue
        out.append((dotted, _line_of(text, match.start())))
    return out


def collect(paths: list[Path]) -> list[Reference]:
    """Every documented disarm name across the given Markdown files."""
    refs: list[Reference] = []
    for path in sorted(paths):
        text = path.read_text(encoding="utf-8")

        for body, first_line in _python_blocks(text):
            for dotted, line in _names_from_python(body):
                refs.append(Reference(dotted, path, first_line + line - 1, "code"))

        for match in _MKDOCSTRINGS_RE.finditer(text):
            refs.append(
                Reference(match.group(1), path, _line_of(text, match.start()), "mkdocstrings")
            )

        for dotted, line in prose_names(text):
            refs.append(Reference(dotted, path, line, "prose"))

    return refs


def resolve(dotted: str) -> bool:
    """Does ``dotted`` name something reachable on the installed package?

    Walks the path one component at a time, falling back to an import when an
    attribute lookup fails — a submodule that has not been imported yet is not
    an attribute of its parent, and ``disarm.exceptions`` is documented that way.
    """
    parts = dotted.split(".")
    try:
        obj = importlib.import_module(parts[0])
    except ImportError:
        return False

    for index, part in enumerate(parts[1:], start=1):
        # A documented private name is out of scope for a release gate: it is
        # not API, so its absence from a release is not a broken promise.
        if part.startswith("_") and not (part.startswith("__") and part.endswith("__")):
            return True
        try:
            obj = getattr(obj, part)
        except AttributeError:
            try:
                obj = importlib.import_module(".".join(parts[: index + 1]))
            except ImportError:
                return False
    return True


def _markdown_files(roots: list[str]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        target = (_REPO_ROOT / root).resolve()
        if target.is_file():
            files.append(target)
        elif target.is_dir():
            for path in target.rglob("*.md"):
                # Symlinks are the repo-root files mirrored into `docs/`
                # (CHANGELOG.md and friends); scanning both ends double-counts.
                if not path.is_file() or path.is_symlink():
                    continue
                if _EXCLUDED_DIRS.intersection(path.relative_to(target).parts[:-1]):
                    continue
                files.append(path)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--root",
        action="append",
        dest="roots",
        metavar="PATH",
        help=f"file or directory to scan; repeatable (default: {', '.join(_DEFAULT_ROOTS)})",
    )
    args = parser.parse_args()
    roots = args.roots or list(_DEFAULT_ROOTS)

    try:
        installed = importlib.import_module("disarm")
    except ImportError:
        print(
            "error: `disarm` is not importable — install the wheel you want to check",
            file=sys.stderr,
        )
        return 2

    version = getattr(installed, "__version__", "unknown")
    files = _markdown_files(roots)
    refs = [r for r in collect(files) if r.dotted not in _NOT_ATTRIBUTES]

    missing: dict[str, list[Reference]] = defaultdict(list)
    for ref in refs:
        if not resolve(ref.dotted):
            missing[ref.dotted].append(ref)

    distinct = {r.dotted for r in refs}
    print(
        f"checked {len(distinct)} distinct disarm names from {len(files)} files against disarm {version}"
    )

    # The ratchet's other direction: an entry that has started resolving is a
    # fix that shipped, and leaving it listed would hide the next regression of
    # the same name.
    stale = sorted(name for name in _KNOWN_GAPS if name in distinct and name not in missing)
    if stale:
        print(
            "\nerror: these names resolve now but are still listed in _KNOWN_GAPS.\n"
            "Delete their entries — the gap is closed:\n",
            file=sys.stderr,
        )
        for name in stale:
            print(f"  {name}  ({_KNOWN_GAPS[name]})", file=sys.stderr)
        return 1

    accepted = {name: refs_for for name, refs_for in missing.items() if name in _KNOWN_GAPS}
    missing = {name: refs_for for name, refs_for in missing.items() if name not in _KNOWN_GAPS}

    if accepted:
        print(f"\n{len(accepted)} known gap(s), each tracked by an open issue:")
        for name in sorted(accepted):
            print(f"  {name}  →  {_KNOWN_GAPS[name]}")

    if not missing:
        print("\nevery other documented name resolves on the installed package")
        return 0

    print(
        f"\n{len(missing)} documented name(s) do not exist in disarm {version}:\n", file=sys.stderr
    )
    for dotted in sorted(missing):
        refs_for = missing[dotted]
        print(f"  {dotted}", file=sys.stderr)
        for ref in sorted(refs_for, key=lambda r: (str(r.path), r.line))[:6]:
            print(f"      {ref.where}  ({ref.source})", file=sys.stderr)
        if len(refs_for) > 6:
            print(f"      … and {len(refs_for) - 6} more", file=sys.stderr)

    print(
        "\nThe documentation describes `main`; this check ran against the installed\n"
        "package. A name here is documented and unreleased, or documented and gone.\n"
        "Cut a release, or correct the pages.",
        file=sys.stderr,
    )

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(f"### Documented but missing from `disarm {version}`\n\n")
            handle.write("| name | first named in |\n|---|---|\n")
            for dotted in sorted(missing):
                first = sorted(missing[dotted], key=lambda r: (str(r.path), r.line))[0]
                handle.write(f"| `{dotted}` | `{first.where}` |\n")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
