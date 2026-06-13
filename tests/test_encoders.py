"""Tests for the context-explicit output encoders: escape_html, percent_encode.

These are terminal output encoders (not pipeline steps); see #311.
"""

import html
import urllib.parse

import pytest
from hypothesis import given
from hypothesis import strategies as st

from disarm import Component, DisarmError, escape_html, percent_encode


class TestEscapeHtml:
    def test_five_metacharacters(self) -> None:
        assert escape_html("&") == "&amp;"
        assert escape_html("<") == "&lt;"
        assert escape_html(">") == "&gt;"
        assert escape_html('"') == "&quot;"
        assert escape_html("'") == "&#x27;"

    def test_script_payload(self) -> None:
        assert escape_html("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"

    def test_ampersand_escaped_first(self) -> None:
        # `&` is itself a metacharacter, so it is always escaped first — including
        # the `&` of a pre-existing entity (this encoder is not idempotent; an
        # already-escaped `&lt;` becomes `&amp;lt;`, by design — encode once).
        assert escape_html("a & b") == "a &amp; b"
        assert escape_html("&lt;") == "&amp;lt;"

    def test_passthrough_non_metacharacters(self) -> None:
        assert escape_html("café 北京 — plain") == "café 北京 — plain"

    def test_no_raw_metacharacter_in_output(self) -> None:
        out = escape_html("a<b>c&d\"e'f")
        # The four non-ampersand metacharacters must not survive raw. `&` is not
        # asserted away: it legitimately remains as every entity's leading `&`.
        for ch, ent in [("<", "&lt;"), (">", "&gt;"), ('"', "&quot;"), ("'", "&#x27;")]:
            assert ch not in out
            assert ent in out
        assert "&amp;" in out  # the input `&` is entity-escaped

    def test_fast_path_returns_original_object(self) -> None:
        clean = "nothing to escape here"
        assert escape_html(clean) is clean

    def test_not_idempotent_by_design(self) -> None:
        # Encoding twice double-encodes the ampersand — encode once.
        assert escape_html(escape_html("&")) == "&amp;amp;"

    def test_round_trips_via_stdlib_unescape(self) -> None:
        for s in ["<b>a & b</b>", "x \"y\" 'z'", "plain", "a<>&\"'b"]:
            assert html.unescape(escape_html(s)) == s


class TestPercentEncode:
    def test_unreserved_untouched(self) -> None:
        unreserved = "ABCabc012-._~"
        for comp in Component:
            assert percent_encode(unreserved, component=comp) == unreserved

    def test_query_encodes_reserved(self) -> None:
        assert percent_encode("a b&c=d+e", component=Component.QUERY) == "a%20b%26c%3Dd%2Be"

    def test_form_space_to_plus(self) -> None:
        # space → '+'; a literal '+' → %2B (so it round-trips unambiguously)
        assert percent_encode("a b+c", component=Component.FORM) == "a+b%2Bc"

    def test_path_keeps_slash_segment_encodes_it(self) -> None:
        assert percent_encode("a/b c", component=Component.PATH) == "a/b%20c"
        assert percent_encode("a/b c", component=Component.SEGMENT) == "a%2Fb%20c"

    def test_utf8_byte_expansion(self) -> None:
        assert percent_encode("é", component=Component.QUERY) == "%C3%A9"
        assert percent_encode("☕", component=Component.QUERY) == "%E2%98%95"

    def test_output_is_ascii(self) -> None:
        for comp in Component:
            out = percent_encode("Москва café ☕ a b", component=comp)
            assert out.isascii()

    def test_uppercase_hex(self) -> None:
        # RFC 3986 §6.2.2.1: producers should use uppercase hex.
        assert percent_encode("\x1b", component=Component.QUERY) == "%1B"

    def test_round_trips_via_stdlib(self) -> None:
        s = "Москва: a/b?c=d&e f+g ☕"
        # PATH/SEGMENT/QUERY reverse via unquote; FORM via unquote_plus (space→+).
        for comp in (Component.PATH, Component.SEGMENT, Component.QUERY):
            assert urllib.parse.unquote(percent_encode(s, component=comp)) == s
        assert urllib.parse.unquote_plus(percent_encode(s, component=Component.FORM)) == s

    def test_unknown_component_string_raises(self) -> None:
        # Bare-string misuse reaches the core, which raises a clear error.
        with pytest.raises(DisarmError):
            percent_encode("x", component="nonsense")  # type: ignore[arg-type]


# --- Property tests (fuzz the full input space) ---


@pytest.mark.hypothesis
class TestEncoderProperties:
    @given(st.text())
    def test_escape_html_no_raw_lt_gt(self, s: str) -> None:
        out = escape_html(s)
        assert "<" not in out
        assert ">" not in out

    @given(st.text())
    def test_escape_html_roundtrips(self, s: str) -> None:
        assert html.unescape(escape_html(s)) == s

    @given(st.text())
    def test_percent_encode_output_ascii_and_roundtrips(self, s: str) -> None:
        for comp in Component:
            out = percent_encode(s, component=comp)
            assert out.isascii()
        # PATH/SEGMENT/QUERY round-trip via unquote; FORM via unquote_plus.
        for comp in (Component.PATH, Component.SEGMENT, Component.QUERY):
            assert urllib.parse.unquote(percent_encode(s, component=comp)) == s
        assert urllib.parse.unquote_plus(percent_encode(s, component=Component.FORM)) == s
