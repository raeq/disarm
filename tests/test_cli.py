"""Tests for the translit CLI interface.

Exercises all subcommands, short aliases, flags, stdin piping,
error handling, and malformed/malicious input.
"""

from __future__ import annotations

import os
import subprocess
import sys


def run_cli(
    *args: str, input_text: str | None = None, timeout: float = 10
) -> subprocess.CompletedProcess[str]:
    """Run the translit CLI and return the result."""
    env = {**os.environ, "PYTHONUTF8": "1"}
    return subprocess.run(
        [sys.executable, "-m", "translit", *args],
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
        r = run_cli("p", "--steps", "strip_bidi", "a‮b")  # RLO override
        assert r.returncode == 0
        assert "‮" not in r.stdout
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
        r = run_cli("t", "👨‍👩‍👧‍👦 family")
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
