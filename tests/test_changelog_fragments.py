"""`changelog.d/` assembles into `CHANGELOG.md` without reformatting anything (#993).

Every entry used to be prepended to the same anchor in `CHANGELOG.md`, so two pull
requests open at once conflicted on it every time, whatever they said. Entries here are
essays — the four that seeded `changelog.d/` average 23 lines — so resolving one was
never a two-line merge, and it landed at exactly the moment a pull request was otherwise
ready. Fragments are separate files, so the class is gone rather than reduced.

What that trades away is proofreading: a fragment is written in one release cycle and
rendered in another, and nobody re-reads it in between. So the contract is that assembly
is a **concatenation** — the fragment is the entry, byte for byte, and `towncrier build`
never re-wraps it, never adds a bullet to it, and never appends an issue reference to it.
The stock towncrier markdown template does all three; `changelog.d/_template.md` exists to
stop it, and this module is what keeps that true.

Five assertions:

* every fragment is named for a **pull request**, not an issue — towncrier's default
  would have put #973, #975, #976 and #989 at one filename, since they all close #972;
* every type used is one the configuration declares;
* assembly reproduces the fragment verbatim, in a scratch tree, with no dependence on
  what happens to be in `changelog.d/` today;
* `CHANGELOG.md` still carries the marker towncrier writes above, and no hand-maintained
  `## [Unreleased]` section for an entry to be prepended to;
* the configured type names cover every `###` heading the latest release uses, so the
  vocabulary cannot drift away from the file it describes. (Only the latest: the 7,600
  lines below it are frozen history with one-off headings nothing should reproduce.)
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import tomllib

ROOT = Path(__file__).resolve().parent.parent
FRAGMENTS = ROOT / "changelog.d"
CHANGELOG = ROOT / "CHANGELOG.md"

#: towncrier writes each release above this line and touches nothing below it.
MARKER = "<!-- towncrier release notes start -->"

#: `<pull-request>.<type>.md`, or `+<slug>.<type>.md` before the number exists.
FRAGMENT_NAME = re.compile(r"^(?:\d+|\+[a-z0-9][a-z0-9-]*)\.([a-z]+)\.md$")

#: Files in `changelog.d/` that are not fragments. towncrier ignores them too.
NOT_FRAGMENTS = {"README.md", "_template.md"}

needs_towncrier = pytest.mark.skipif(
    shutil.which("towncrier") is None and not (ROOT / ".venv/bin/towncrier").exists(),
    reason="towncrier is in the `dev` extra; a runner without it is a legitimate setup",
)


def config() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as f:
        return tomllib.load(f)["tool"]["towncrier"]


def declared_types() -> dict[str, str]:
    """directory -> display name, e.g. `{"fixed": "Fixed"}`."""
    return {t["directory"]: t["name"] for t in config()["type"]}


def fragments() -> list[Path]:
    return sorted(p for p in FRAGMENTS.glob("*.md") if p.name not in NOT_FRAGMENTS)


def towncrier(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    exe = shutil.which("towncrier") or str(ROOT / ".venv/bin/towncrier")
    return subprocess.run([exe, *args], cwd=cwd, capture_output=True, text=True, check=True)


def test_every_fragment_is_named_for_a_pull_request() -> None:
    """`<pr>.<type>.md`. towncrier's default is the ISSUE number, which collides.

    #972 alone produced #973, #975, #976 and #989; #974 produced #979, #977 produced
    #978, #980 produced #982, #816 produced #969. Several pull requests per issue is the
    norm here, so keying on the issue would have rebuilt the conflict on day one.
    """
    bad = [p.name for p in fragments() if not FRAGMENT_NAME.match(p.name)]
    assert not bad, (
        f"not `<pull-request>.<type>.md` (or `+<slug>.<type>.md`): {bad} — "
        "see changelog.d/README.md"
    )


def test_every_fragment_type_is_declared() -> None:
    known = declared_types()
    used = {m.group(1) for p in fragments() if (m := FRAGMENT_NAME.match(p.name))}
    assert used <= set(known), (
        f"undeclared fragment type(s) {sorted(used - set(known))}; declared: {sorted(known)}"
    )


@needs_towncrier
def test_assembly_reproduces_the_fragment_verbatim(tmp_path: Path) -> None:
    """A fragment is the entry, byte for byte — no re-wrap, no bullet, no `(#123)`.

    Run against the stock towncrier template every one of these fails: it prefixes
    `- ` to an entry that already opens with `- `, re-wraps at 79 columns, and appends
    its own issue reference. The whole point of `_template.md` is that none of that
    happens, so this asserts the output rather than the configuration.
    """
    entry = (
        "- **A lead-in whose line is deliberately longer than towncrier's default "
        "wrap width of 79 columns (#1).** Body text.\n"
        "\n"
        "  A second paragraph, indented two spaces the way every entry in this file is.\n"
    )
    (tmp_path / "changelog.d").mkdir()
    (tmp_path / "changelog.d" / "1.fixed.md").write_text(entry, encoding="utf-8")
    shutil.copy(FRAGMENTS / "_template.md", tmp_path / "changelog.d" / "_template.md")
    (tmp_path / "CHANGELOG.md").write_text(f"# Changelog\n\n{MARKER}\n\n## [0.1.0]\n")
    shutil.copy(ROOT / "pyproject.toml", tmp_path / "pyproject.toml")

    towncrier("build", "--version", "9.9.9", "--yes", cwd=tmp_path)
    built = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")

    assert entry in built, f"assembly reformatted the fragment:\n{built}"
    assert "## [9.9.9]" in built
    assert "### Fixed" in built
    assert "- - " not in built, "doubled bullet: the stock template is in use"
    assert built.endswith("## [0.1.0]\n"), "content below the marker moved"


def test_changelog_has_the_marker_and_no_hand_written_unreleased_section() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    assert text.count(MARKER) == 1, f"expected exactly one {MARKER!r}"
    assert "## [Unreleased]" not in text, (
        "`## [Unreleased]` is back in CHANGELOG.md. Unreleased content lives in "
        "changelog.d/ now; read it with `towncrier build --draft --version NEXT`."
    )


def test_the_configured_types_cover_the_latest_release_headings() -> None:
    """The vocabulary in `pyproject.toml` has to be the one the changelog actually uses.

    Scoped to the most recent release, not the whole file. The 7,600 lines below it are
    frozen history and were written before any of this existed — they carry one-off
    headings (*Maintenance*, *Notes*, *Upgrade notes (output-affecting fix)*) that
    nothing should reproduce. The latest release is the live vocabulary, and a
    `[[tool.towncrier.type]]` whose name drifts from it (`Bugfixes` for *Fixed*) would
    silently start a second heading for the same thing.
    """
    text = CHANGELOG.read_text(encoding="utf-8")
    releases = re.split(r"^## \[", text, flags=re.MULTILINE)
    latest = next(r for r in releases[1:] if not r.startswith("Unreleased"))
    used = set(re.findall(r"^### (.+)$", latest, flags=re.MULTILINE))
    names = set(declared_types().values())
    assert used, "found no `###` headings in the latest release section"
    assert used <= names, (
        f"heading(s) {sorted(used - names)} appear in the latest release with no "
        f"[[tool.towncrier.type]] that produces them; declared: {sorted(names)}"
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v"]))
