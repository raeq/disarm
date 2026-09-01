"""No file in the tree carries an unresolved merge-conflict marker.

Written because a marker was committed and pushed on this very branch. The sequence is
easy: `git merge` reports "Automatic merge failed", the next command is
`git add -A && git commit`, and the markers go in with everything else. Nothing caught it
— the full Python suite passed with three markers sitting in `CHANGELOG.md`, because no
test reads that file as Markdown. Ruff formats the Python blocks inside it and the
changelog test checks heading order; neither cares about a line of angle brackets.

The disarm branches conflict constantly (every one of them edits `CHANGELOG.md`'s
`[Unreleased]` block and most regenerate the key fixture), so this is not a rare shape.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Git's markers, anchored at column 0. `=======` alone is excluded: it is a legitimate
#: Markdown setext heading underline and appears in the docs. `<<<<<<<` and `>>>>>>>`
#: are enough — git writes all three or none.
MARKERS = ("<<<<<<<", ">>>>>>>")


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "--no-optional-locks", "ls-files", "-z"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [ROOT / name for name in out.split("\0") if name]


def test_no_tracked_file_carries_a_conflict_marker() -> None:
    found = []
    for path in tracked_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue  # binary fixtures, and files a checkout has not materialised
        for number, line in enumerate(text.splitlines(), 1):
            if line.startswith(MARKERS):
                found.append(f"{path.relative_to(ROOT)}:{number}: {line[:60]}")
    assert not found, "unresolved merge-conflict markers are committed:\n  " + "\n  ".join(found)


def test_the_gate_can_fail(tmp_path: Path) -> None:
    """A gate that cannot fail is a gate nobody has run."""
    sample = "ok\n<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> other\n"
    hits = [line for line in sample.splitlines() if line.startswith(MARKERS)]
    assert len(hits) == 2, hits


def test_a_setext_heading_is_not_a_marker() -> None:
    """`=======` under a line is ordinary Markdown and must not trip this."""
    sample = "A heading\n=========\n\ntext\n"
    assert not [line for line in sample.splitlines() if line.startswith(MARKERS)]
