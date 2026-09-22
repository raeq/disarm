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
`wrap = false` keeps the first off (it is towncrier's default; `pyproject.toml` states it
anyway). `changelog.d/_template.md` stops the other two: it renders no issue reference,
and it adds no bullet — the stock towncrier markdown template does, whatever
`all_bullets` says. This module is what keeps all three true.

The assertions:

* every fragment is named for a **pull request**, not an issue — towncrier's default
  would have put #973, #975, #976 and #989 at one filename, since they all close #972 —
  and "every fragment" means every file towncrier would consume, not only `*.md`;
* every type used is one the configuration declares;
* assembly reproduces the fragment verbatim, in a scratch tree, with no dependence on
  what happens to be in `changelog.d/` today — compared as the whole file, so the stock
  template fails it;
* the headings come out in the order the releases use, *Upgrade notes* first;
* `CHANGELOG.md` still carries the marker towncrier inserts each release below, and no
  hand-maintained `## [Unreleased]` section for an entry to be prepended to;
* the configured type names cover every `###` heading the latest release uses, so the
  vocabulary cannot drift away from the file it describes. (Only the latest: the 7,600
  lines below it are frozen history with one-off headings nothing should reproduce.)
* towncrier is in the `test` extra, which is what CI's test job installs — so the
  assembly tests above run on every pull request rather than skipping — and the
  *Changelog fragment* job installs the same pin.
"""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
FRAGMENTS = ROOT / "changelog.d"
CHANGELOG = ROOT / "CHANGELOG.md"

#: towncrier inserts each release directly below this line — above the previous
#: release — and changes nothing already in the file.
MARKER = "<!-- towncrier release notes start -->"

#: `<pull-request>.<type>.md`, or `+<slug>.<type>.md` before the number exists.
FRAGMENT_NAME = re.compile(r"^(?:\d+|\+[a-z0-9][a-z0-9-]*)\.([a-z]+)\.md$")

#: Files in `changelog.d/` that are not fragments. towncrier ignores them too.
NOT_FRAGMENTS = {"README.md", "_template.md"}

#: A fixed date, so an assembled file can be compared whole rather than searched.
DATE = "2000-01-01"

#: Skipped where towncrier is absent — except under CI, where it has to be present.
#: towncrier used to be in the `dev` extra only, CI's test job installs `.[test]`, and
#: so the assembly test skipped on every pull request without anyone noticing (#994
#: review). On CI a missing towncrier now fails the test instead of skipping it.
needs_towncrier = pytest.mark.skipif(
    shutil.which("towncrier") is None
    and not (ROOT / ".venv/bin/towncrier").exists()
    and not os.environ.get("CI"),
    reason="towncrier is in the `test` extra; a runner without it is a legitimate setup",
)


#: The header opening one `[[tool.towncrier.type]]` entry in `pyproject.toml`.
TYPE_HEADER = "[[tool.towncrier.type]]"

#: The two keys of one, as written: `directory = "fixed"` / `name = "Fixed"`.
TYPE_KEY = re.compile(r'^(directory|name)\s*=\s*"([^"]+)"')


def declared_types() -> dict[str, str]:
    """directory -> display name, e.g. `{"fixed": "Fixed"}`, scanned not parsed.

    `tomllib` is 3.11+ and `requires-python` is `>=3.10`, so importing it would make
    this whole module uncollectable on the floor — not one skipped test. It is the
    same trap `scripts/mkdocs_build_banner.py` documents, and the same answer: two
    keys from one known array of tables do not need a parser, and walking to the
    header is what stops a `name` in some other table being picked up.
    """
    types: dict[str, str] = {}
    entry: dict[str, str] = {}
    inside = False

    def flush() -> None:
        if inside and {"directory", "name"} <= entry.keys():
            types[entry["directory"]] = entry["name"]

    for line in (ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            flush()
            inside = stripped == TYPE_HEADER
            entry = {}
        elif inside and (match := TYPE_KEY.match(stripped)):
            entry[match.group(1)] = match.group(2)
    flush()
    return types


def fragments(directory: Path = FRAGMENTS) -> list[Path]:
    """Every file towncrier would consume, whatever its suffix — not only `*.md`."""
    return sorted(p for p in directory.glob("*") if p.is_file() and p.name not in NOT_FRAGMENTS)


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


def test_a_fragment_without_the_md_suffix_is_still_checked(tmp_path: Path) -> None:
    """towncrier consumes `1003.fixed` and `1004.fixed.txt` as readily as `.md`.

    It keys on the type segment, not the suffix, so both land in the release. A scan of
    `*.md` alone let them past the naming test while the build shipped them (#994
    review).
    """
    for name in ("991.fixed.md", "1003.fixed", "1004.fixed.txt", *NOT_FRAGMENTS):
        (tmp_path / name).write_text("- **x (#1).** y\n", encoding="utf-8")
    found = {p.name for p in fragments(tmp_path)}
    assert found == {"991.fixed.md", "1003.fixed", "1004.fixed.txt"}
    assert not FRAGMENT_NAME.match("1003.fixed")
    assert not FRAGMENT_NAME.match("1004.fixed.txt")


def test_every_fragment_type_is_declared() -> None:
    known = declared_types()
    used = {m.group(1) for p in fragments() if (m := FRAGMENT_NAME.match(p.name))}
    assert used <= set(known), (
        f"undeclared fragment type(s) {sorted(used - set(known))}; declared: {sorted(known)}"
    )


def scratch_tree(tmp_path: Path, fragments: dict[str, str]) -> Path:
    """This repository's towncrier config, with only `fragments` in `changelog.d/`."""
    (tmp_path / "changelog.d").mkdir()
    for name, text in fragments.items():
        (tmp_path / "changelog.d" / name).write_text(text, encoding="utf-8")
    shutil.copy(FRAGMENTS / "_template.md", tmp_path / "changelog.d" / "_template.md")
    (tmp_path / "CHANGELOG.md").write_text(f"# Changelog\n\n{MARKER}\n\n## [0.1.0]\n")
    shutil.copy(ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    return tmp_path


@needs_towncrier
def test_assembly_reproduces_the_fragment_verbatim(tmp_path: Path) -> None:
    """A fragment is the entry, byte for byte — no re-wrap, no bullet, no `(#123)`.

    Compared as the whole file, not searched for. The stock template's output *contains*
    the entry — its doubled bullet is `- ` followed by the entry — so a substring check
    passes against it (#994 review). With `template =` removed from `pyproject.toml`
    this fails on the doubled bullet and the extra blank line; with `wrap = true`, on
    the re-wrap. Asserting the output rather than the configuration is what catches
    whichever of them regresses.
    """
    entry = (
        "- **A lead-in whose line is deliberately longer than towncrier's default "
        "wrap width of 79 columns (#1).** Body text.\n"
        "\n"
        "  A second paragraph, indented two spaces the way every entry in this file is.\n"
    )
    tree = scratch_tree(tmp_path, {"1.fixed.md": entry})

    towncrier("build", "--version", "9.9.9", "--date", DATE, "--yes", cwd=tree)
    built = (tree / "CHANGELOG.md").read_text(encoding="utf-8")

    expected = (
        f"# Changelog\n\n{MARKER}\n\n## [9.9.9] — {DATE}\n\n### Fixed\n\n{entry}\n## [0.1.0]\n"
    )
    hint = " (doubled bullet: the stock template is in use)" if "- - " in built else ""
    assert built == expected, f"assembly reformatted the fragment{hint}:\n{built}"


@needs_towncrier
def test_upgrade_notes_come_first(tmp_path: Path) -> None:
    """`0.16.0`, `0.15.0` and `0.14.0` all open on *Upgrade notes*, before *Added*.

    towncrier writes headings in the order `[[tool.towncrier.type]]` declares them, and
    `upgrade` was declared last — so the first release assembled from fragments would
    have put the notes a reader must act on below everything else (#994 review).
    """
    tree = scratch_tree(
        tmp_path,
        {
            "1.fixed.md": "- **A fix (#1).**\n",
            "2.added.md": "- **A feature (#2).**\n",
            "3.upgrade.md": "- **A key moved (#3).**\n",
        },
    )
    draft = towncrier("build", "--draft", "--version", "9.9.9", cwd=tree).stdout
    assert re.findall(r"^### (.+)$", draft, flags=re.MULTILINE) == [
        "Upgrade notes",
        "Added",
        "Fixed",
    ]


def test_the_configured_order_is_the_latest_release_order() -> None:
    """The same, for every heading, and without needing towncrier installed."""
    latest = latest_release_headings()
    declared = [name for name in declared_types().values() if name in latest]
    assert declared == latest, (
        f"[[tool.towncrier.type]] order {declared} does not match the latest release's "
        f"heading order {latest}; towncrier writes headings in the declared order"
    )


def test_changelog_has_the_marker_and_no_hand_written_unreleased_section() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    assert text.count(MARKER) == 1, f"expected exactly one {MARKER!r}"
    assert "## [Unreleased]" not in text, (
        "`## [Unreleased]` is back in CHANGELOG.md. Unreleased content lives in "
        "changelog.d/ now; read it with `towncrier build --draft --version NEXT`."
    )


def latest_release_headings() -> list[str]:
    """The `###` headings of the most recent release in `CHANGELOG.md`, in order."""
    text = CHANGELOG.read_text(encoding="utf-8")
    releases = re.split(r"^## \[", text, flags=re.MULTILINE)
    latest = next(r for r in releases[1:] if not r.startswith("Unreleased"))
    return re.findall(r"^### (.+)$", latest, flags=re.MULTILINE)


def test_the_configured_types_cover_the_latest_release_headings() -> None:
    """The vocabulary in `pyproject.toml` has to be the one the changelog actually uses.

    Scoped to the most recent release, not the whole file. The 7,600 lines below it are
    frozen history and were written before any of this existed — they carry one-off
    headings (*Maintenance*, *Notes*, *Upgrade notes (output-affecting fix)*) that
    nothing should reproduce. The latest release is the live vocabulary, and a
    `[[tool.towncrier.type]]` whose name drifts from it (`Bugfixes` for *Fixed*) would
    silently start a second heading for the same thing.
    """
    used = set(latest_release_headings())
    names = set(declared_types().values())
    assert used, "found no `###` headings in the latest release section"
    assert used <= names, (
        f"heading(s) {sorted(used - names)} appear in the latest release with no "
        f"[[tool.towncrier.type]] that produces them; declared: {sorted(names)}"
    )


def extra(name: str) -> list[str]:
    """The requirements of one `[project.optional-dependencies]` extra, scanned."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(rf"^{name} = \[\n(.*?)^\]", text, flags=re.MULTILINE | re.DOTALL)
    assert block, f"pyproject.toml has no `{name}` extra"
    return re.findall(r'^\s*"([^"]+)"', block.group(1), flags=re.MULTILINE)


def test_towncrier_is_in_the_extra_ci_tests_with() -> None:
    """CI's test job installs `.[test]`; towncrier in `dev` alone meant it never ran.

    The assembly tests above are the only ones that exercise the template, and they
    skipped on every pull request after #994 (#994 review). One pin, in `test`: `dev`
    includes `disarm[test]`, so a second copy would only be somewhere to disagree.
    """
    pins = [req for req in extra("test") if req.startswith("towncrier")]
    assert len(pins) == 1, f"the `test` extra should pin towncrier once, not {pins}"
    assert re.fullmatch(r"towncrier==\d+\.\d+\.\d+", pins[0]), (
        f"{pins[0]}: pin it exactly, for the reason the `dev` extra pins ruff"
    )
    assert not [req for req in extra("dev") if req.startswith("towncrier")], (
        "towncrier is pinned in `dev` as well as `test`"
    )


def ci() -> dict:
    return yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))


def changelog_step(name: str) -> dict:
    steps = [s for s in ci()["jobs"]["changelog"]["steps"] if s.get("name") == name]
    assert len(steps) == 1, f"the changelog job has {len(steps)} steps named {name!r}"
    return steps[0]


def test_a_binding_change_owes_a_fragment_and_a_docs_change_does_not() -> None:
    """The gate keyed on `code` — `.py`/`.rs`/`.toml`/`.tsv` — so a Java, Kotlin, Ruby,
    TypeScript or C change in `bindings/` owed no fragment (#994 review). The binding
    filters `ruby` and `node` are not the answer: they include `docs/**`.
    """
    (paths_filter,) = [
        s
        for s in ci()["jobs"]["changes"]["steps"]
        if s.get("uses", "").startswith("dorny/paths-filter")
    ]
    filters = yaml.safe_load(paths_filter["with"]["filters"])
    shipped = set(filters["shipped"])
    assert set(filters["code"]) <= shipped
    assert "bindings/**" in shipped
    assert not {"docs/**", "**.md"} & shipped, "a docs-only change owes no fragment"
    gate = changelog_step("A shipped change carries a changelog fragment")
    assert "needs.changes.outputs.shipped == 'true'" in gate["if"]


def test_the_label_is_read_when_the_job_runs_not_from_the_event() -> None:
    """The `no changelog` label has to work when it is added after the push.

    A label change starts no run (ci.yml keeps the default `pull_request` types, since
    `labeled` would restart the whole matrix), so the route is: add it, re-run the job.
    A re-run replays the original event, whose label list predates the label, so the
    event payload can never see it (#994 review). The job asks the API instead.
    """
    job = ci()["jobs"]["changelog"]
    assert "github.event.pull_request.labels" not in yaml.safe_dump(job)
    assert "gh api" in changelog_step("Read the `no changelog` label")["run"]
    assert job["permissions"].get("pull-requests") == "read"


def git(*args: str, cwd: Path) -> None:
    subprocess.run(  # noqa: S603 — fixed argv
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("git") is None,
    reason="the step is a bash script over git; CI runs it on ubuntu",
)
@pytest.mark.parametrize(
    ("change", "allowed"),
    [
        ({"changelog.d/2.fixed.md": "- **New (#2).**\n"}, True),
        ({"CHANGELOG.md": "# Changelog\n\n- **Hand-written (#2).**\n"}, False),
        ({"CHANGELOG.md": "# Changelog\n\n## [9.9.9]\n", "changelog.d/1.fixed.md": None}, True),
        ({"CHANGELOG.md": "# Changelog\n\n## [9.9.9]\n", "changelog.d/README.md": None}, False),
        (
            {
                "CHANGELOG.md": "# Changelog\n\n- **Hand-written (#2).**\n",
                "changelog.d/1.fixed.md": None,
                "changelog.d/5.fixed.md": "- **Old (#1).**\n",
            },
            False,
        ),
    ],
    ids=[
        "fragment-only",
        "hand-edit",
        "release-assembly",
        "readme-deletion-is-not-a-release",
        "rename-is-not-a-release",
    ],
)
def test_changelog_md_is_written_only_by_a_release(
    tmp_path: Path, change: dict[str, str | None], allowed: bool
) -> None:
    """`towncrier check` passes on any edit to CHANGELOG.md, so a hand-written entry got
    through the gate (#994 review). The release pull request is the one legitimate
    edit, and it is recognisable: `towncrier build` also deletes what it consumed.
    ci.yml's own step, run over a throwaway repository with an `origin/main`.
    """
    (tmp_path / "changelog.d").mkdir()
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (tmp_path / "changelog.d" / "README.md").write_text("docs\n", encoding="utf-8")
    (tmp_path / "changelog.d" / "1.fixed.md").write_text("- **Old (#1).**\n", encoding="utf-8")
    git("init", "-q", "-b", "main", cwd=tmp_path)
    git("add", "-A", cwd=tmp_path)
    git("commit", "-q", "-m", "base", cwd=tmp_path)
    git("update-ref", "refs/remotes/origin/main", "HEAD", cwd=tmp_path)
    for name, text in change.items():
        if text is None:
            (tmp_path / name).unlink()
        else:
            (tmp_path / name).write_text(text, encoding="utf-8")
    git("add", "-A", cwd=tmp_path)
    git("commit", "-q", "-m", "pr", cwd=tmp_path)

    result = subprocess.run(  # noqa: S603 — fixed argv; the script is ci.yml's own
        [
            "bash",
            "--noprofile",
            "--norc",
            "-eo",
            "pipefail",
            "-c",
            changelog_step("CHANGELOG.md is written only by a release")["run"],
        ],
        cwd=tmp_path,
        env={**os.environ, "BASE": "main"},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert (result.returncode == 0) is allowed, result.stdout + result.stderr


@pytest.mark.skipif(
    sys.platform == "win32" or sys.version_info < (3, 11),
    reason="the step is a bash script that reads pyproject.toml with tomllib (3.11+); "
    "CI runs it on ubuntu with Python 3.12",
)
def test_the_changelog_job_installs_the_pinned_towncrier(tmp_path: Path) -> None:
    """ci.yml's own install script, run against a `pip` that prints its arguments."""
    script = changelog_step("Install towncrier")["run"]
    for name, body in (
        ("pip", 'printf "%s\\n" "$@"'),
        ("python", f'exec "{sys.executable}" "$@"'),
    ):
        stub = tmp_path / name
        stub.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
        stub.chmod(0o755)
    result = subprocess.run(  # noqa: S603 — fixed argv; the script is ci.yml's own
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
        cwd=ROOT,
        env={**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    (pin,) = [req for req in extra("test") if req.startswith("towncrier")]
    assert result.stdout.split() == ["install", pin]


def test_this_module_does_not_need_tomllib() -> None:
    """`tomllib` is 3.11+; `requires-python` is `>=3.10`.

    An unconditional import here fails at *collection* on the floor, taking every
    test in the module with it. `scripts/mkdocs_build_banner.py` carries the same
    rule for the same reason, pinned by `test_docs_release_drift.py`; this is that
    test for this module. Caught by Copilot on #994 — the first version of this file
    imported `tomllib` to read the type table, and ruff sorted it as third-party,
    which is the tell.
    """
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "tomllib" not in imported, "3.10 cannot import this module"
    assert "tomli" not in imported, "not a dependency; scan pyproject.toml instead"


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v"]))
