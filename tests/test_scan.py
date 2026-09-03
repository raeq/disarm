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
import subprocess
from pathlib import Path

import pytest

from disarm.scan import (
    DEFAULT_SKIP_DIRS,
    EXIT_FINDINGS,
    EXIT_OK,
    EXIT_READ_ERROR,
    MAX_FILE_BYTES,
    iter_files,
    run,
    scan_paths,
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

    @pytest.mark.skipif(os.geteuid() == 0, reason="root can read anything")
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
        assert set(f) == {"path", "line", "column", "kind", "reason", "token"}
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
