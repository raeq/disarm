"""Tests for strip_log_injection — log-line / terminal-control neutralization (#307)."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from disarm import DisarmError, strip_log_injection

REPL = "�"


class TestStripLogInjection:
    def test_crlf_and_nul(self) -> None:
        assert strip_log_injection("a\r\nb\x00c") == f"a{REPL}{REPL}b{REPL}c"

    def test_forged_log_line(self) -> None:
        out = strip_log_injection("user=admin\nFAKE 500 ERROR")
        assert "\n" not in out
        assert out == f"user=admin{REPL}FAKE 500 ERROR"

    def test_ansi_introducer_replaced_residue_kept(self) -> None:
        # ESC -> replacement; the inert "[31m" residue stays (audit-visible).
        assert strip_log_injection("a\x1b[31mred") == f"a{REPL}[31mred"

    def test_nel_ls_ps_and_c1(self) -> None:
        s = "a\x85b\u2028c\u2029d\x9be"  # NEL, LS, PS, C1 CSI
        assert strip_log_injection(s) == f"a{REPL}b{REPL}c{REPL}d{REPL}e"

    def test_del(self) -> None:
        assert strip_log_injection("a\x7fb") == f"a{REPL}b"

    def test_tab_neutralized_by_default(self) -> None:
        assert strip_log_injection("a\tb") == f"a{REPL}b"

    def test_keep_tab_opt_in(self) -> None:
        assert strip_log_injection("a\tb", keep_tab=True) == "a\tb"

    def test_clean_line_returns_original_object(self) -> None:
        clean = "plain ascii log line"
        assert strip_log_injection(clean) is clean

    def test_preserves_printable_and_non_ascii(self) -> None:
        s = "café ☕ — 北京 weiß"
        assert strip_log_injection(s) == s

    def test_does_not_html_escape(self) -> None:
        # Makes no HTML-viewer-safety claim: < > & " are preserved verbatim.
        s = '<script>alert(1)</script> & "x"'
        assert strip_log_injection(s) == s

    def test_output_has_no_raw_cr_lf_esc(self) -> None:
        out = strip_log_injection("x\r\n\x1b\x85 y")
        assert not any(c in out for c in ("\r", "\n", "\x1b"))

    def test_idempotent(self) -> None:
        s = "a\r\nb\x1b\tc\x85"
        once = strip_log_injection(s)
        assert strip_log_injection(once) == once

    def test_custom_replacement(self) -> None:
        assert strip_log_injection("a\nb", replacement="?") == "a?b"
        assert strip_log_injection("a\nb", replacement="") == "ab"  # drop

    def test_replacement_with_control_rejected(self) -> None:
        with pytest.raises(DisarmError):
            strip_log_injection("x", replacement="\n")
        # A tab replacement is rejected too under the default keep_tab=False.
        with pytest.raises(DisarmError):
            strip_log_injection("x", replacement="\t")


@pytest.mark.hypothesis
class TestStripLogInjectionProperties:
    @given(st.text())
    def test_no_record_or_terminal_break(self, s: str) -> None:
        out = strip_log_injection(s)
        forbidden = ("\r", "\n", "\x1b", "\x00", "\u2028", "\u2029")
        assert not any(c in out for c in forbidden)

    @given(st.text())
    def test_idempotent(self, s: str) -> None:
        once = strip_log_injection(s)
        assert strip_log_injection(once) == once

    @given(st.text())
    def test_makes_no_html_claim(self, s: str) -> None:
        # The HTML metacharacters are never escaped (that is the viewer's job).
        out = strip_log_injection(s)
        assert out.count("<") == s.count("<")
        assert out.count(">") == s.count(">")
        assert out.count("&") == s.count("&")
