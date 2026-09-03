"""Tests for the disarm CLI interface.

Exercises all subcommands, short aliases, flags, stdin piping,
error handling, and malformed/malicious input.

Most of these call ``main()`` in-process (#658). Every test used to spawn
``python -m disarm``, which made this file 2.73s of a 6.16s suite — about 4.6s of
the 5.2s measured in that issue was interpreter startup, for tests that are about
argument parsing rather than about processes.

``TestProcessEntryPoint`` keeps a handful of real subprocesses, and is the reason
this is a split rather than a wholesale conversion: an in-process-only suite would
pass even if ``python -m disarm`` no longer resolved, or if the console script
were broken. Those are the assertions a subprocess is genuinely required for.
"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
from unittest import mock

import disarm.__main__


def run_cli(
    *args: str, input_text: str | None = None, timeout: float = 10
) -> subprocess.CompletedProcess[str]:
    """Run the CLI in-process and return a subprocess-shaped result.

    ``main()`` reads ``sys.argv`` and writes to ``sys.stdout``/``sys.stderr``, so
    all three are patched for the call. Exit status comes from ``SystemExit``:
    the CLI raises it explicitly on an input error, argparse raises it with an
    integer status on a bad argument, and a clean return means 0.

    ``timeout`` is accepted and ignored. It exists so call sites do not have to
    change, and in-process there is no process to time out — a hang here hangs
    pytest, which is a louder failure than a timeout anyway.
    """
    del timeout

    stdout, stderr = io.StringIO(), io.StringIO()
    # StringIO.isatty() is False, which is what `_read_input` checks before
    # reading stdin. A test that passes no input_text and no positional argument
    # therefore reads "" rather than taking the "no input provided" branch —
    # matching the subprocess behaviour under pytest, where stdin is not a tty.
    stdin = io.StringIO(input_text if input_text is not None else "")

    code = 0
    with (
        contextlib.redirect_stdout(stdout),
        contextlib.redirect_stderr(stderr),
        mock.patch.object(sys, "argv", ["disarm", *args]),
        mock.patch.object(sys, "stdin", stdin),
    ):
        try:
            disarm.__main__.main()
        except SystemExit as exc:
            if exc.code is None:
                code = 0
            elif isinstance(exc.code, int):
                code = exc.code
            else:
                # `sys.exit("message")` — CPython prints the object to stderr and
                # exits 1. Not argparse, which exits with an int (2) after
                # printing its own message; this branch is here because any code
                # under main() may raise SystemExit carrying a non-int.
                code = 1
                stderr.write(f"{exc.code}\n")

    return subprocess.CompletedProcess(
        args=["disarm", *args],
        returncode=code,
        stdout=stdout.getvalue(),
        stderr=stderr.getvalue(),
    )


def run_cli_subprocess(
    *args: str, input_text: str | None = None, timeout: float = 10
) -> subprocess.CompletedProcess[str]:
    """Spawn a real ``python -m disarm``. Used only by TestProcessEntryPoint."""
    env = {**os.environ, "PYTHONUTF8": "1"}
    return subprocess.run(
        [sys.executable, "-m", "disarm", *args],
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        env=env,
    )


# ---------------------------------------------------------------------------
# Basic subcommands
# ---------------------------------------------------------------------------


class TestTransliterate:
    def test_basic(self):
        r = run_cli("transliterate", "café")
        assert r.returncode == 0
        assert r.stdout.strip() == "cafe"

    def test_short_alias(self):
        r = run_cli("t", "café")
        assert r.returncode == 0
        assert r.stdout.strip() == "cafe"

    def test_lang_flag(self):
        r = run_cli("t", "--lang", "de", "Ärger")
        assert r.returncode == 0
        assert "Aerger" in r.stdout

    def test_target_flag(self):
        r = run_cli("t", "--target", "ru", "Moskva")
        assert r.returncode == 0
        assert "Москва" in r.stdout

    def test_strict_iso9(self):
        r = run_cli("t", "--strict-iso9", "Юрий")
        assert r.returncode == 0
        assert r.stdout.strip()  # Should produce some output

    def test_tones_flag(self):
        r = run_cli("t", "--tones", "北京")
        assert r.returncode == 0
        assert r.stdout.strip()  # Should produce toned pinyin

    def test_gost7034_flag(self):
        r = run_cli("t", "--gost7034", "Москва")
        assert r.returncode == 0
        assert r.stdout.strip()

    def test_multiword(self):
        r = run_cli("t", "café", "résumé")
        assert r.returncode == 0
        assert "cafe" in r.stdout
        assert "resume" in r.stdout


class TestSlugify:
    def test_basic(self):
        r = run_cli("slugify", "Hello World!")
        assert r.returncode == 0
        assert r.stdout.strip() == "hello-world"

    def test_short_alias(self):
        r = run_cli("s", "Hello World!")
        assert r.returncode == 0
        assert r.stdout.strip() == "hello-world"

    def test_separator(self):
        r = run_cli("s", "--separator", "_", "Hello World")
        assert r.returncode == 0
        assert r.stdout.strip() == "hello_world"

    def test_max_length(self):
        r = run_cli("s", "--max-length", "5", "Hello World")
        assert r.returncode == 0
        assert len(r.stdout.strip()) <= 5

    def test_lang_flag(self):
        # #250 C3: --lang must be honored (German ä→ae), not silently ignored.
        r = run_cli("s", "--lang", "de", "Ärger")
        assert r.returncode == 0
        assert r.stdout.strip() == "aerger"


class TestNormalize:
    def test_nfc(self):
        # e + combining acute → precomposed é
        r = run_cli("normalize", "cafe\u0301")
        assert r.returncode == 0
        assert r.stdout.strip() == "caf\u00e9"

    def test_short_alias(self):
        r = run_cli("n", "café")
        assert r.returncode == 0

    def test_form_nfkc(self):
        r = run_cli("n", "--form", "NFKC", "\ufb01")  # ﬁ ligature
        assert r.returncode == 0
        assert r.stdout.strip() == "fi"


class TestPipeline:
    def test_basic(self):
        r = run_cli("pipeline", "--steps", "normalize,fold_case", "CAFÉ")
        assert r.returncode == 0
        assert "caf" in r.stdout.lower()

    def test_short_alias(self):
        r = run_cli("p", "--steps", "fold_case", "HELLO")
        assert r.returncode == 0
        assert r.stdout.strip() == "hello"

    def test_unknown_step_errors(self):
        r = run_cli("p", "--steps", "bogus_step", "text")
        assert r.returncode != 0
        assert "unknown" in r.stderr.lower()

    def test_strip_bidi_step(self):
        # #250 C6: strip_bidi was supported by TextPipeline but unreachable.
        r = run_cli("p", "--steps", "strip_bidi", "a\u202eb")  # RLO override
        assert r.returncode == 0
        assert "\u202e" not in r.stdout
        assert r.stdout.strip() == "ab"

    def test_strip_zalgo_step(self):
        # #250 C6: strip_zalgo takes --zalgo-max-marks (default 0 = strip all).
        r = run_cli("p", "--steps", "strip_zalgo", "--zalgo-max-marks", "0", "a\u0301\u0301\u0301")
        assert r.returncode == 0
        assert r.stdout.strip() == "a"


class TestDemojize:
    def test_basic(self):
        r = run_cli("demojize", "Hello 😀")
        assert r.returncode == 0
        assert r.stdout.strip()  # Should contain text description

    def test_short_alias(self):
        r = run_cli("d", "Hello 😀")
        assert r.returncode == 0


# ---------------------------------------------------------------------------
# Stdin piping
# ---------------------------------------------------------------------------


class TestStdin:
    def test_pipe_transliterate(self):
        r = run_cli("t", input_text="café\n")
        assert r.returncode == 0
        assert r.stdout.strip() == "cafe"

    def test_pipe_slugify(self):
        r = run_cli("s", input_text="Hello World!\n")
        assert r.returncode == 0
        assert r.stdout.strip() == "hello-world"

    def test_pipe_normalize(self):
        r = run_cli("n", input_text="cafe\u0301\n")
        assert r.returncode == 0

    def test_pipe_empty(self):
        r = run_cli("t", input_text="")
        assert r.returncode == 0

    def test_pipe_multiline(self):
        r = run_cli("t", input_text="café\nrésumé\n")
        assert r.returncode == 0
        output = r.stdout.strip()
        assert "cafe" in output


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrors:
    def test_no_command(self):
        r = run_cli()
        assert r.returncode != 0

    def test_invalid_command(self):
        r = run_cli("nonexistent")
        assert r.returncode != 0

    def test_lang_and_target_mutual_exclusion(self):
        r = run_cli("t", "--lang", "de", "--target", "ru", "hello")
        assert r.returncode != 0

    def test_invalid_normalize_form(self):
        r = run_cli("n", "--form", "INVALID", "text")
        assert r.returncode != 0

    def test_pipeline_missing_steps(self):
        r = run_cli("p", "text")
        assert r.returncode != 0

    def test_unsupported_reverse_target(self):
        r = run_cli("t", "--target", "de", "hello")
        assert r.returncode != 0

    def test_api_error_is_clean_not_traceback(self):
        # #250 C7: an API error (here an unknown --lang, now fail-closed by #257)
        # prints "Error: ..." + exit 1, not a raw Python traceback.
        r = run_cli("s", "--lang", "zzz", "hello")
        assert r.returncode == 1
        assert r.stderr.startswith("Error:")
        assert "Traceback" not in r.stderr


# ---------------------------------------------------------------------------
# Malformed and malicious input
# ---------------------------------------------------------------------------


class TestMalformedInput:
    def test_null_bytes(self):
        # Null bytes can't be passed as argv; test via stdin
        r = run_cli("t", input_text="hello\x00world")
        # Should not crash; may strip or pass through null
        assert r.returncode == 0

    def test_very_long_input(self):
        long_text = "café " * 10000
        # Pass via stdin to avoid Windows ~8191-char command-line limit
        r = run_cli("t", input_text=long_text)
        assert r.returncode == 0

    def test_only_whitespace(self):
        r = run_cli("t", "   ")
        assert r.returncode == 0

    def test_only_newlines(self):
        r = run_cli("t", input_text="\n\n\n")
        assert r.returncode == 0

    def test_unicode_replacement_char(self):
        r = run_cli("t", "\ufffd\ufffd\ufffd")
        assert r.returncode == 0

    def test_bom(self):
        r = run_cli("t", "\ufeff" + "café")
        assert r.returncode == 0

    def test_rtl_override(self):
        """Right-to-left override should not crash CLI."""
        r = run_cli("t", "\u202e" + "hello" + "\u202c")
        assert r.returncode == 0

    def test_zalgo_text(self):
        zalgo = "h\u0335\u0321\u0324e\u0336\u0320l\u0337\u0318l\u0334o\u0335"
        r = run_cli("t", zalgo)
        assert r.returncode == 0

    def test_emoji_sequence(self):
        r = run_cli("t", "👨\u200d👩\u200d👧\u200d👦 family")
        assert r.returncode == 0

    def test_mixed_scripts(self):
        r = run_cli("t", "Hello Москва 北京 서울")
        assert r.returncode == 0

    def test_surrogate_pair_region(self):
        """SMP characters (outside BMP) should not crash."""
        r = run_cli("t", "𐌰𐌱𐌲")  # Gothic
        assert r.returncode == 0

    def test_private_use_area(self):
        r = run_cli("t", "\ue000\ue001\ue002")
        assert r.returncode == 0


class TestMaliciousInput:
    def test_path_traversal_in_text(self):
        """Path traversal strings are just text, not security issues for CLI."""
        r = run_cli("t", "../../etc/passwd")
        assert r.returncode == 0

    def test_shell_injection_attempt(self):
        r = run_cli("t", "$(rm -rf /)")
        assert r.returncode == 0
        # Should just transliterate the literal text
        assert "rm" in r.stdout or r.stdout.strip()

    def test_backtick_injection(self):
        r = run_cli("t", "`echo pwned`")
        assert r.returncode == 0

    def test_pipe_injection(self):
        r = run_cli("t", "hello | rm -rf /")
        assert r.returncode == 0

    def test_semicolon_injection(self):
        r = run_cli("t", "hello; rm -rf /")
        assert r.returncode == 0

    def test_newline_injection(self):
        r = run_cli("t", "line1\nline2\nline3")
        assert r.returncode == 0

    def test_ansi_escape_codes(self):
        r = run_cli("t", "\x1b[31mred\x1b[0m")
        assert r.returncode == 0

    def test_confusable_homoglyphs(self):
        """Cyrillic 'а' (U+0430) looks like Latin 'a'."""
        r = run_cli("t", "pаypal")  # Cyrillic а
        assert r.returncode == 0

    def test_extremely_long_flag_value(self):
        r = run_cli("s", "--separator", "x" * 1000, "hello world")
        assert r.returncode == 0

    def test_negative_max_length(self):
        r = run_cli("s", "--max-length", "-1", "hello world")
        # Should handle gracefully (empty or error)
        # The important thing is no crash
        assert isinstance(r.returncode, int)

    def test_zero_max_length(self):
        r = run_cli("s", "--max-length", "0", "hello world")
        assert isinstance(r.returncode, int)


# ---------------------------------------------------------------------------
# The process boundary itself (#658)
# ---------------------------------------------------------------------------


class TestProcessEntryPoint:
    """The few assertions a real subprocess is required for.

    Everything above calls ``main()`` in-process, which is 34x faster and tests
    the same argument parsing. What it cannot test is that there is a process to
    call: an in-process suite passes just as happily when ``python -m disarm`` no
    longer resolves, when ``__main__.py`` fails to import under a fresh
    interpreter, or when the console-script entry point is wrong.

    Four subprocesses, not fifty-eight. That is the whole trade.
    """

    def test_module_invocation_resolves(self):
        """`python -m disarm` finds and runs the module."""
        r = run_cli_subprocess("--help")
        assert r.returncode == 0
        assert "transliterate" in r.stdout

    def test_a_real_process_transliterates(self):
        """End to end through a fresh interpreter: argv in, stdout out."""
        r = run_cli_subprocess("t", "Москва")
        assert r.returncode == 0
        assert r.stdout.strip() == "Moskva"

    def test_a_real_process_reads_stdin(self):
        """The pipe, through actual OS plumbing rather than a StringIO."""
        r = run_cli_subprocess("t", input_text="café")
        assert r.returncode == 0
        assert r.stdout.strip() == "cafe"

    def test_a_real_process_exits_nonzero_on_error(self):
        """The exit status a shell or CI step would actually observe."""
        r = run_cli_subprocess("s", "--lang", "zzz", "hello")
        assert r.returncode == 1
        assert r.stderr.startswith("Error:")


# ---------------------------------------------------------------------------
# scan (#704)
# ---------------------------------------------------------------------------


class TestScan:
    """`disarm scan`, driven through argv the way a user or CI would."""

    PLANTED = "user\u202egpj.exe\n"  # escapes, never literals (#802)

    def _tree(self, tmp_path):
        (tmp_path / "bad.txt").write_text(self.PLANTED, encoding="utf-8")
        (tmp_path / "ok.txt").write_text("nothing here\n", encoding="utf-8")
        return tmp_path

    def test_prints_a_located_finding_and_a_summary(self, tmp_path):
        r = run_cli("scan", str(self._tree(tmp_path)))
        assert r.returncode == 0, r.stderr
        assert "bad.txt:1:1: bidi:" in r.stdout
        assert "scanned 2 file(s), 1 finding(s)" in r.stdout

    def test_short_form(self, tmp_path):
        assert run_cli("sc", str(self._tree(tmp_path))).returncode == 0

    def test_fail_exits_one_only_when_something_is_found(self, tmp_path):
        assert run_cli("scan", "--fail", str(self._tree(tmp_path))).returncode == 1
        clean = tmp_path / "clean"
        clean.mkdir()
        (clean / "a.txt").write_text("fine\n")
        assert run_cli("scan", "--fail", str(clean)).returncode == 0

    def test_json_is_parseable_and_located(self, tmp_path):
        import json

        r = run_cli("scan", "--json", str(self._tree(tmp_path)))
        doc = json.loads(r.stdout)
        [f] = doc["findings"]
        assert f["kind"] == "bidi" and (f["line"], f["column"]) == (1, 1)
        assert doc["scanned"] == 2

    def test_a_missing_path_is_three_and_says_so(self, tmp_path):
        """Something failed to read is not something found, and not a usage error."""
        r = run_cli("scan", str(tmp_path / "nope"))
        assert r.returncode == 3
        assert "nope" in r.stderr

    def test_a_usage_error_is_still_argparses_two(self):
        assert run_cli("scan").returncode == 2  # paths is required

    def test_help_names_the_contract(self):
        r = run_cli("scan", "--help")
        assert "--fail" in r.stdout and "--json" in r.stdout and "--no-gitignore" in r.stdout
        assert "--sarif" in r.stdout and "--baseline" in r.stdout and "--write-baseline" in r.stdout

    # ---- #705

    def test_sarif_is_a_parseable_2_1_0_document(self, tmp_path):
        import json

        r = run_cli("scan", "--sarif", str(self._tree(tmp_path)))
        assert r.returncode == 0, r.stderr
        doc = json.loads(r.stdout)
        assert doc["version"] == "2.1.0"
        [result] = doc["runs"][0]["results"]
        assert result["ruleId"] == "bidi" and result["partialFingerprints"]["disarm/v1"]

    def test_sarif_and_json_are_mutually_exclusive(self, tmp_path):
        assert run_cli("scan", "--sarif", "--json", str(tmp_path)).returncode == 2

    def test_a_baseline_lets_the_check_go_on_before_the_tree_is_clean(self, tmp_path):
        root = self._tree(tmp_path)
        bl = tmp_path / ".disarm-baseline.json"
        assert run_cli("scan", "--fail", str(root)).returncode == 1
        w = run_cli("scan", "--write-baseline", str(bl), str(root))
        assert w.returncode == 0 and "wrote 1 fingerprint" in w.stdout
        assert run_cli("scan", "--fail", "--baseline", str(bl), str(root)).returncode == 0
        # ...and something new still fails.
        (root / "new.txt").write_text(self.PLANTED, encoding="utf-8")
        r = run_cli("scan", "--fail", "--baseline", str(bl), str(root))
        assert r.returncode == 1 and "new.txt" in r.stdout and "bad.txt" not in r.stdout

    def test_a_missing_baseline_is_a_read_error_not_a_traceback(self, tmp_path):
        r = run_cli("scan", "--baseline", str(tmp_path / "nope.json"), str(tmp_path))
        assert r.returncode == 3 and "nope.json" in r.stderr and "Traceback" not in r.stderr

    def test_a_baseline_of_the_wrong_version_is_refused(self, tmp_path):
        bl = tmp_path / "bl.json"
        bl.write_text('{"version": 99, "fingerprints": []}')
        r = run_cli("scan", "--baseline", str(bl), str(tmp_path))
        assert r.returncode == 1 and "baseline version" in r.stderr
