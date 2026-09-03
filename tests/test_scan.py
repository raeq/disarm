"""#704 — `disarm scan`: the one API built for scanning, pointed at files.

`inspect_anomalies` returns findings with byte spans, a kind, evidence and a reason —
everything a scanner needs — and there was no way to run it over a file. The plumbing is
the easy part; the four rules #704 takes from `juriku/untrace` are where scanners go wrong:

1. git's ignore rules come from **three** sources, and reading only the nearest
   `.gitignore` makes `scan src/` and `scan .` disagree on one tree.
2. `build`, `dist`, `out`, `target`, `bin`, `vendor` are **not** safe to skip by name.
3. Never follow symlinks.
4. Something found is not something failed to read.
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from disarm.scan import (
    BASELINE_VERSION,
    DEFAULT_SKIP_DIRS,
    EXIT_FINDINGS,
    EXIT_OK,
    EXIT_READ_ERROR,
    MAX_FILE_BYTES,
    SARIF_LEVELS,
    _portable,
    fingerprint_for,
    iter_files,
    load_baseline,
    run,
    scan_paths,
    to_sarif,
    write_baseline,
)

#: Escapes, never literals (#802).
ZWSP = "\u200b"
RLO = "\u202e"
PLANTED = f"user{RLO}gpj.exe\n"  # a bidi override — kind `bidi`, always fires


def _git(tmp: Path, *args: str) -> None:
    subprocess.run(
        ["git", "--no-optional-locks", *args],
        cwd=tmp,
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "HOME": str(tmp)},
    )


def _repo(tmp: Path) -> Path:
    _git(tmp, "init", "-q")
    return tmp


def _plant(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PLANTED, encoding="utf-8")
    return path


def _scanned(root: Path, **kw: object) -> set[str]:
    return {Path(p).name for p in map(str, iter_files([root], **kw))}  # type: ignore[arg-type]


class TestGitIgnoreReadsAllThreeSources:
    """Rule 1. Delegated to `git check-ignore`, so each source works by construction."""

    def test_the_nearest_gitignore(self, tmp_path: Path) -> None:
        root = _repo(tmp_path)
        _plant(root / "keep.txt")
        _plant(root / "drop.log")
        (root / ".gitignore").write_text("*.log\n")
        assert _scanned(root) == {"keep.txt", ".gitignore"}

    def test_a_parent_gitignore_applies_to_a_subdirectory_scan(self, tmp_path: Path) -> None:
        """The bug users report as flakiness: `scan src/` and `scan .` must agree."""
        root = _repo(tmp_path)
        (root / ".gitignore").write_text("*.log\n")
        _plant(root / "src" / "keep.txt")
        _plant(root / "src" / "drop.log")
        whole = _scanned(root)
        sub = _scanned(root / "src")
        assert "drop.log" not in whole
        assert "drop.log" not in sub, "a scanner reading only the nearest file gets this wrong"
        assert "keep.txt" in sub

    def test_git_info_exclude(self, tmp_path: Path) -> None:
        root = _repo(tmp_path)
        (root / ".git" / "info").mkdir(exist_ok=True)
        (root / ".git" / "info" / "exclude").write_text("secret.txt\n")
        _plant(root / "secret.txt")
        _plant(root / "public.txt")
        assert _scanned(root) == {"public.txt"}

    def test_no_gitignore_scans_everything(self, tmp_path: Path) -> None:
        root = _repo(tmp_path)
        (root / ".gitignore").write_text("*.log\n")
        _plant(root / "drop.log")
        assert "drop.log" in _scanned(root, use_gitignore=False)

    def test_outside_a_repository_there_is_nothing_to_ask(self, tmp_path: Path) -> None:
        """Not an error — a scan with no ignore rules."""
        _plant(tmp_path / "a.log")
        (tmp_path / ".gitignore").write_text("*.log\n")
        assert "a.log" in _scanned(tmp_path)


class TestTheDefaultSkipList:
    """Rule 2. Skipping is only safe where nothing hand-written can live."""

    @pytest.mark.parametrize("name", ["node_modules", "__pycache__", ".venv", ".terraform"])
    def test_a_generated_directory_is_skipped(self, tmp_path: Path, name: str) -> None:
        _plant(tmp_path / name / "x.py")
        _plant(tmp_path / "real.py")
        assert _scanned(tmp_path) == {"real.py"}

    @pytest.mark.parametrize("name", ["build", "dist", "out", "target", "bin", "vendor"])
    def test_an_ambiguous_directory_is_not(self, tmp_path: Path, name: str) -> None:
        """Generated in some projects and hand-written in others. A scanner that skips
        them by name reports clean on a tree it never read."""
        assert name not in DEFAULT_SKIP_DIRS
        _plant(tmp_path / name / "x.py")
        assert "x.py" in _scanned(tmp_path)


class TestSymlinksAreNeverFollowed:
    """Rule 3. A scan stays inside the tree it was pointed at."""

    def test_a_directory_link_out_of_the_tree(self, tmp_path: Path) -> None:
        outside = tmp_path / "outside"
        _plant(outside / "leak.txt")
        root = tmp_path / "root"
        root.mkdir()
        (root / "link").symlink_to(outside, target_is_directory=True)
        _plant(root / "inside.txt")
        assert _scanned(root) == {"inside.txt"}

    def test_a_root_that_is_itself_a_link_is_refused_and_reported(self, tmp_path: Path) -> None:
        """`is_dir()` resolves links, so the first version followed a symlinked ROOT while
        refusing symlinked entries — `disarm scan <link>` walked outside the tree
        (caught in review on #944). Refused, and reported: silence looks like clean."""
        outside = tmp_path / "outside"
        _plant(outside / "leak.txt")
        link = tmp_path / "link"
        link.symlink_to(outside, target_is_directory=True)
        result = scan_paths([link])
        assert result.findings == [] and result.scanned == 0
        assert any("symlink" in reason for _, reason in result.unreadable), result.unreadable
        assert run([link], out=io.StringIO()) == EXIT_READ_ERROR
        # ...and a link to a single file, the other half of the same hole.
        file_link = tmp_path / "file_link.txt"
        file_link.symlink_to(_plant(tmp_path / "real.txt"))
        assert scan_paths([file_link]).findings == []

    def test_a_file_link(self, tmp_path: Path) -> None:
        """Would report a finding against a path whose content lives elsewhere."""
        target = _plant(tmp_path / "elsewhere.txt")
        root = tmp_path / "root"
        root.mkdir()
        (root / "alias.txt").symlink_to(target)
        assert _scanned(root) == set()


class TestWhatIsNotAnError:
    def test_a_binary_file_is_skipped_silently(self, tmp_path: Path) -> None:
        (tmp_path / "blob.bin").write_bytes(b"\x89PNG\x00\x00" + PLANTED.encode())
        result = scan_paths([tmp_path])
        assert result.scanned == 0
        assert result.unreadable == []

    def test_an_oversize_file_is_skipped_silently(self, tmp_path: Path) -> None:
        (tmp_path / "huge.txt").write_text("x" * (MAX_FILE_BYTES + 1) + PLANTED)
        result = scan_paths([tmp_path])
        assert result.scanned == 0
        assert result.findings == []

    def test_non_utf8_is_skipped_silently(self, tmp_path: Path) -> None:
        """`decode_to_utf8` is a different job; a scanner is not a charset detector."""
        (tmp_path / "latin1.txt").write_bytes("caf\xe9".encode("latin-1"))
        assert scan_paths([tmp_path]).scanned == 0


class TestLineAndColumn:
    def test_line_and_column_are_one_based(self, tmp_path: Path) -> None:
        _plant(tmp_path / "f.txt").write_text(f"clean\n  {PLANTED}", encoding="utf-8")
        [f] = scan_paths([tmp_path]).findings
        assert (f.line, f.column) == (2, 3)

    def test_column_counts_characters_not_bytes(self, tmp_path: Path) -> None:
        """`Finding.start` is a byte offset; an editor's gutter is not. Pinned with a
        non-ASCII prefix, where the two diverge — the trap #940's spans set."""
        prefix = "café "  # 5 characters, 6 bytes
        (tmp_path / "f.txt").write_text(prefix + PLANTED, encoding="utf-8")
        [f] = scan_paths([tmp_path]).findings
        assert f.column == len(prefix) + 1
        assert f.column != len(prefix.encode()) + 1, "otherwise the test proves nothing"


class TestTheExitCodeContract:
    """Rule 4, and why `2` is skipped: argparse owns it."""

    def test_clean_is_zero(self, tmp_path: Path) -> None:
        (tmp_path / "clean.txt").write_text("nothing here\n")
        assert run([tmp_path], out=io.StringIO()) == EXIT_OK

    def test_findings_are_zero_without_fail_and_one_with_it(self, tmp_path: Path) -> None:
        _plant(tmp_path / "f.txt")
        assert run([tmp_path], out=io.StringIO()) == EXIT_OK
        assert run([tmp_path], fail=True, out=io.StringIO()) == EXIT_FINDINGS

    def test_a_path_that_cannot_be_read_is_three(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Not the same as a finding, and not the same as a usage error."""
        missing = tmp_path / "gone.txt"
        assert run([missing], out=io.StringIO()) == EXIT_READ_ERROR
        assert "gone.txt" in capsys.readouterr().err

    def test_read_error_outranks_findings(self, tmp_path: Path) -> None:
        """A tree that could not be fully read must not look like one that scanned
        cleanly, even if the readable part had findings."""
        _plant(tmp_path / "f.txt")
        assert (
            run([tmp_path, tmp_path / "gone.txt"], fail=True, out=io.StringIO()) == EXIT_READ_ERROR
        )

    # `hasattr` first: `os.geteuid` does not exist on Windows, and a `skipif` expression
    # runs at import — so the bare call raised before any test could be skipped (caught
    # in review on #944). On Windows the test is skipped, which is right: `chmod 000`
    # does not lock a directory there either.
    @pytest.mark.skipif(
        not hasattr(os, "geteuid") or os.geteuid() == 0,
        reason="needs POSIX permissions, and root can read anything",
    )
    def test_an_unlistable_subdirectory_is_three_not_silence(self, tmp_path: Path) -> None:
        """`os.walk` swallows a directory it cannot list unless told otherwise, so the
        first version scanned around it and reported clean. Silence looks like clean."""
        locked = tmp_path / "locked"
        _plant(locked / "hidden.txt")
        _plant(tmp_path / "open.txt")
        locked.chmod(0o000)
        try:
            result = scan_paths([tmp_path])
            assert result.scanned == 1, "the readable file is still scanned"
            assert any("locked" in path for path, _ in result.unreadable), result.unreadable
            assert run([tmp_path], out=io.StringIO()) == EXIT_READ_ERROR
        finally:
            locked.chmod(0o755)

    def test_the_codes_are_distinct_and_skip_argparses(self) -> None:
        assert len({EXIT_OK, EXIT_FINDINGS, EXIT_READ_ERROR}) == 3
        assert 2 not in {EXIT_OK, EXIT_FINDINGS, EXIT_READ_ERROR}


class TestJson:
    def test_the_shape(self, tmp_path: Path) -> None:
        _plant(tmp_path / "f.txt")
        out = io.StringIO()
        run([tmp_path], as_json=True, out=out)
        doc = json.loads(out.getvalue())
        assert set(doc) == {"findings", "scanned", "unreadable"}
        assert doc["scanned"] == 1 and doc["unreadable"] == []
        [f] = doc["findings"]
        # `detail` and `fingerprint` joined in #705; the exact set is deliberate, so a key
        # cannot appear or vanish without this line moving.
        assert set(f) == {
            "path",
            "line",
            "column",
            "kind",
            "reason",
            "token",
            "detail",
            "fingerprint",
        }
        assert f["kind"] == "bidi" and f["line"] == 1

    def test_unreadable_paths_are_in_the_document_too(self, tmp_path: Path) -> None:
        out = io.StringIO()
        code = run([tmp_path / "gone.txt"], as_json=True, out=out)
        doc = json.loads(out.getvalue())
        assert code == EXIT_READ_ERROR
        assert doc["unreadable"][0]["path"].endswith("gone.txt")


def test_a_single_file_path_is_scanned_directly(tmp_path: Path) -> None:
    f = _plant(tmp_path / "one.txt")
    assert [p.name for p in iter_files([f])] == ["one.txt"]


# ---------------------------------------------------------------------------
# #705 — fingerprints, baseline, SARIF
# ---------------------------------------------------------------------------


class TestFingerprints:
    """File, what was found, and which occurrence — never the line (#705)."""

    def test_an_inserted_paragraph_above_does_not_change_it(self, tmp_path: Path) -> None:
        """The naive fingerprint (file + line + column) breaks here. This one must not."""
        f = tmp_path / "f.txt"
        f.write_text("intro\n" + PLANTED, encoding="utf-8")
        [before] = scan_paths([tmp_path]).findings
        f.write_text("a new paragraph\nand another line\n\nintro\n" + PLANTED, encoding="utf-8")
        [after] = scan_paths([tmp_path]).findings
        assert after.line != before.line, "the finding really did move"
        assert after.fingerprint == before.fingerprint, "and its identity did not"

    def test_it_never_encodes_the_line(self) -> None:
        a = fingerprint_for("f.txt", "bidi", "U+202E", 0)
        assert a == fingerprint_for("f.txt", "bidi", "U+202E", 0)
        assert a != fingerprint_for("f.txt", "bidi", "U+202E", 1), "occurrence is part of it"
        assert a != fingerprint_for("g.txt", "bidi", "U+202E", 0), "so is the file"
        assert a != fingerprint_for("f.txt", "bidi", "U+202D", 0), "so is what was found"

    def test_the_documented_caveat_and_that_the_count_stays_right(self, tmp_path: Path) -> None:
        """Inserting a SECOND occurrence above a recorded first: the new one is accepted,
        the old one reported. Which is named can swap; nothing is dropped. Asserted because
        it is the stated limit of the rule, not a bug to be fixed later."""
        f = tmp_path / "f.txt"
        f.write_text("x\n" + PLANTED, encoding="utf-8")
        [first] = scan_paths([tmp_path]).findings
        f.write_text(PLANTED + "x\n" + PLANTED, encoding="utf-8")
        now = scan_paths([tmp_path]).findings
        assert len(now) == 2, "the count is right"
        fps = {x.fingerprint for x in now}
        assert first.fingerprint in fps, "the recorded identity is still among them"
        matched = [x for x in now if x.fingerprint == first.fingerprint]
        assert matched[0].line == 1, "...but it now names the NEW occurrence, the caveat"

    def test_two_kinds_at_one_place_are_two_fingerprints(self, tmp_path: Path) -> None:
        (tmp_path / "f.txt").write_text("ad" + ZWSP + "min " + PLANTED, encoding="utf-8")
        fps = {x.fingerprint for x in scan_paths([tmp_path]).findings}
        assert len(fps) == 2

    def test_the_path_is_posix_separated_on_every_host(self) -> None:
        # Copilot on #947: `str(path)` on Windows carries backslashes, so the same tree
        # scanned on two hosts produced two baselines. One form everywhere.
        assert _portable(PureWindowsPath(r"src\auth.py")) == "src/auth.py"
        assert _portable(PurePosixPath("src/auth.py")) == "src/auth.py"
        # On POSIX a backslash is a filename character, and it stays one.
        assert _portable(PurePosixPath("odd\\name.py")) == "odd\\name.py"

    def test_a_windows_scan_and_a_posix_scan_share_a_fingerprint(self) -> None:
        win = fingerprint_for(_portable(PureWindowsPath(r"src\auth.py")), "bidi", "U+202E", 0)
        posix = fingerprint_for(_portable(PurePosixPath("src/auth.py")), "bidi", "U+202E", 0)
        assert win == posix

    def test_scanned_findings_carry_the_portable_form(self, tmp_path: Path) -> None:
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "a.txt").write_text("x\u202ey", encoding="utf-8")
        result = scan_paths([tmp_path], use_gitignore=False)
        assert [f.path for f in result.findings] == [(tmp_path / "sub" / "a.txt").as_posix()]


class TestBaseline:
    def _tree(self, tmp_path: Path) -> Path:
        _plant(tmp_path / "old.txt")
        return tmp_path

    def test_write_then_apply_makes_fail_pass(self, tmp_path: Path) -> None:
        """A repository with history is not clean on its first scan; this is how the check
        goes on at all."""
        root = self._tree(tmp_path)
        bl = tmp_path / ".disarm-baseline.json"
        assert run([root], fail=True, out=io.StringIO()) == EXIT_FINDINGS
        assert run([root], write_baseline_to=bl, out=io.StringIO()) == EXIT_OK
        assert run([root], fail=True, baseline=bl, out=io.StringIO()) == EXIT_OK

    def test_a_baselined_finding_is_counted_and_not_shown(self, tmp_path: Path) -> None:
        root = self._tree(tmp_path)
        bl = tmp_path / "bl.json"
        run([root], write_baseline_to=bl, out=io.StringIO())
        out = io.StringIO()
        run([root], baseline=bl, out=out)
        text = out.getvalue()
        assert "old.txt" not in text and "1 baselined" in text

    def test_something_new_still_fails(self, tmp_path: Path) -> None:
        root = self._tree(tmp_path)
        bl = tmp_path / "bl.json"
        run([root], write_baseline_to=bl, out=io.StringIO())
        _plant(root / "new.txt")
        out = io.StringIO()
        assert run([root], fail=True, baseline=bl, out=out) == EXIT_FINDINGS
        assert "new.txt" in out.getvalue() and "old.txt" not in out.getvalue()

    def test_a_fixed_finding_is_reported_stale_not_kept(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """So the file shrinks as the tree is cleaned instead of accumulating acceptances."""
        root = self._tree(tmp_path)
        bl = tmp_path / "bl.json"
        run([root], write_baseline_to=bl, out=io.StringIO())
        (root / "old.txt").write_text("fixed\n", encoding="utf-8")
        assert run([root], baseline=bl, out=io.StringIO()) == EXIT_OK
        assert "stale: baseline entry" in capsys.readouterr().err
        # Rewriting drops it.
        run([root], write_baseline_to=bl, out=io.StringIO())
        assert load_baseline(bl) == set()

    def test_the_file_is_sorted_and_versioned(self, tmp_path: Path) -> None:
        root = self._tree(tmp_path)
        _plant(root / "b.txt")
        _plant(root / "a.txt")
        bl = tmp_path / "bl.json"
        n = write_baseline(bl, scan_paths([root]).findings)
        doc = json.loads(bl.read_text())
        assert doc["version"] == BASELINE_VERSION and n == 3
        assert doc["fingerprints"] == sorted(doc["fingerprints"])

    def test_an_unknown_version_is_refused(self, tmp_path: Path) -> None:
        bl = tmp_path / "bl.json"
        bl.write_text('{"version": 99, "fingerprints": []}')
        with pytest.raises(ValueError, match="baseline version"):
            load_baseline(bl)

    def test_a_read_error_still_outranks_a_clean_baseline(self, tmp_path: Path) -> None:
        root = self._tree(tmp_path)
        bl = tmp_path / "bl.json"
        run([root], write_baseline_to=bl, out=io.StringIO())
        assert run([root, root / "gone"], baseline=bl, out=io.StringIO()) == EXIT_READ_ERROR

    @pytest.mark.parametrize(
        "body",
        [
            '{"version": 1, "fingerprints": "abc"}',
            '{"version": 1, "fingerprints": [1, 2]}',
            '{"version": 1, "fingerprints": {"a": 1}}',
        ],
    )
    def test_a_malformed_fingerprint_list_is_refused_by_name(
        self, tmp_path: Path, body: str
    ) -> None:
        # Copilot on #947: these raised TypeError — a traceback through the CLI — where
        # a wrong version was refused cleanly. Same refusal, same type.
        bl = tmp_path / "bl.json"
        bl.write_text(body, encoding="utf-8")
        with pytest.raises(ValueError, match="list of strings"):
            load_baseline(bl)

    @pytest.mark.parametrize("body", ["[]", "42", "{not json"])
    def test_a_document_that_is_not_a_baseline_is_refused_by_name(
        self, tmp_path: Path, body: str
    ) -> None:
        bl = tmp_path / "bl.json"
        bl.write_text(body, encoding="utf-8")
        with pytest.raises(ValueError, match="not a baseline file"):
            load_baseline(bl)

    def test_a_missing_fingerprint_list_is_an_empty_baseline(self, tmp_path: Path) -> None:
        # Both halves: the check refuses the wrong shape and still accepts the absent one.
        bl = tmp_path / "bl.json"
        bl.write_text('{"version": 1}', encoding="utf-8")
        assert load_baseline(bl) == set()


class TestSarif:
    def test_the_shape(self, tmp_path: Path) -> None:
        _plant(tmp_path / "f.txt")
        doc = to_sarif(scan_paths([tmp_path]), version="0.0.0-test")
        assert doc["version"] == "2.1.0" and doc["$schema"].endswith("sarif-2.1.0.json")
        [run_] = doc["runs"]
        assert run_["tool"]["driver"]["name"] == "disarm"
        [rule] = run_["tool"]["driver"]["rules"]
        [result] = run_["results"]
        assert rule["id"] == result["ruleId"] == "bidi"
        region = result["locations"][0]["physicalLocation"]["region"]
        assert (region["startLine"], region["startColumn"]) == (1, 1)
        assert result["partialFingerprints"]["disarm/v1"]

    def test_it_is_valid_json_end_to_end(self, tmp_path: Path) -> None:
        _plant(tmp_path / "f.txt")
        out = io.StringIO()
        run([tmp_path], as_sarif=True, out=out)
        assert json.loads(out.getvalue())["runs"][0]["results"]

    def test_the_level_map_covers_every_kind_the_library_can_produce(self) -> None:
        """Hard-coded here rather than on `AnomalyKind` (#705 item 4), so this is what
        keeps it from falling behind the enum: the kinds are read from the Rust source."""
        src = (Path(__file__).resolve().parent.parent / "src" / "anomalies.rs").read_text(
            encoding="utf-8"
        )
        block = re.search(r"pub fn as_str\(self\) -> &'static str \{.*?\n    \}", src, re.S)
        assert block, "as_str() not found — update this gate"
        kinds = set(re.findall(r'=> "([a-z_]+)"', block.group(0)))
        assert kinds, "no kinds parsed"
        assert set(SARIF_LEVELS) == kinds, {
            "kinds with no level": sorted(kinds - set(SARIF_LEVELS)),
            "levels for no kind": sorted(set(SARIF_LEVELS) - kinds),
        }

    def test_a_decoded_payload_is_the_one_error(self) -> None:
        """The one finding that needs no threshold to interpret."""
        assert SARIF_LEVELS["smuggled"] == "error"
        assert {v for k, v in SARIF_LEVELS.items() if k != "smuggled"} == {"warning"}
