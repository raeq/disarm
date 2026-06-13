"""Tests for features inspired by HN Unicode discussion: grapheme clusters,
hostname safety, NFC in filenames, and encoding detection."""

import pytest

from disarm import (
    DisarmError,
    decode_to_utf8,
    detect_encoding,
    grapheme_len,
    grapheme_split,
    grapheme_truncate,
    is_suspicious_hostname,
    sanitize_filename,
)

# ===== Grapheme Cluster Functions =====


class TestGraphemeLen:
    def test_ascii(self) -> None:
        assert grapheme_len("hello") == 5

    def test_empty(self) -> None:
        assert grapheme_len("") == 0

    def test_nfc_accented(self) -> None:
        assert grapheme_len("caf\u00e9") == 4  # precomposed é

    def test_nfd_accented(self) -> None:
        assert grapheme_len("cafe\u0301") == 4  # base e + combining accent = 1 grapheme

    def test_family_emoji(self) -> None:
        # 👩‍👩‍👧‍👦 = 4 person codepoints + 3 ZWJ
        family = "\U0001f469\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466"
        assert grapheme_len(family) == 1

    def test_flag_emoji(self) -> None:
        # 🇬🇧 = 2 regional indicators, 1 grapheme
        assert grapheme_len("\U0001f1ec\U0001f1e7") == 1

    def test_skin_tone_emoji(self) -> None:
        # 👋🏽 = wave + skin tone modifier = 1 grapheme
        assert grapheme_len("\U0001f44b\U0001f3fd") == 1

    def test_hangul_precomposed(self) -> None:
        assert grapheme_len("\uac01") == 1  # precomposed syllable

    def test_hangul_decomposed(self) -> None:
        # ㄱ + ㅏ + ㄱ (jamo) should form 1 grapheme cluster
        assert grapheme_len("\u1100\u1161\u11a8") == 1

    def test_zalgo_text(self) -> None:
        # h + 10 combining marks = still 1 grapheme
        zalgo = "h" + "\u0335" * 10
        assert grapheme_len(zalgo) == 1

    def test_cuneiform(self) -> None:
        # 𒈙 is a single SMP character = 1 grapheme, 4 UTF-8 bytes
        assert grapheme_len("\U00012219") == 1

    def test_mixed_emoji_and_text(self) -> None:
        assert grapheme_len("hi 👋") == 4  # h, i, space, wave


class TestGraphemeSplit:
    def test_ascii(self) -> None:
        assert grapheme_split("abc") == ["a", "b", "c"]

    def test_nfd_keeps_cluster(self) -> None:
        parts = grapheme_split("cafe\u0301")
        assert len(parts) == 4
        assert parts[3] == "e\u0301"  # combining accent stays with base

    def test_emoji_family_is_one(self) -> None:
        family = "\U0001f469\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466"
        parts = grapheme_split(family)
        assert len(parts) == 1

    def test_flag_is_one(self) -> None:
        parts = grapheme_split("\U0001f1ec\U0001f1e7")
        assert len(parts) == 1

    def test_empty(self) -> None:
        assert grapheme_split("") == []


class TestGraphemeTruncate:
    def test_basic_truncation(self) -> None:
        assert grapheme_truncate("hello world", 5) == "hello"

    def test_within_limit_unchanged(self) -> None:
        assert grapheme_truncate("hi", 10) == "hi"

    def test_zero_limit(self) -> None:
        assert grapheme_truncate("hello", 0) == ""

    def test_nfd_preserves_cluster(self) -> None:
        # "cafés" in NFD = 5 graphemes; truncate to 4 should keep accent with e
        nfd = "cafe\u0301s"
        result = grapheme_truncate(nfd, 4)
        assert result == "cafe\u0301"

    def test_emoji_not_split(self) -> None:
        family = "\U0001f469\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466"
        text = family + " family"
        result = grapheme_truncate(text, 1)
        assert result == family

    def test_flag_not_split(self) -> None:
        text = "\U0001f1ec\U0001f1e7 UK"
        result = grapheme_truncate(text, 1)
        assert result == "\U0001f1ec\U0001f1e7"

    def test_hangul_not_split(self) -> None:
        # Decomposed Hangul should not be split mid-syllable
        jamo = "\u1100\u1161\u11a8"  # 1 grapheme
        text = jamo + "x"
        result = grapheme_truncate(text, 1)
        assert result == jamo


# ===== Hostname Safety =====


class TestIsSuspiciousHostname:
    def test_clean_ascii_domain_not_suspicious(self) -> None:
        suspicious, details = is_suspicious_hostname("paypal.com")
        assert not suspicious
        assert not details.has_confusables
        assert not details.mixed_script

    def test_cyrillic_homoglyph_attack(self) -> None:
        suspicious, details = is_suspicious_hostname("\u0440\u0430ypal.com")
        assert suspicious
        assert details.has_confusables
        assert details.mixed_script
        assert details.canonical == "paypal.com"

    def test_full_cyrillic_google(self) -> None:
        # gооgle with Cyrillic о
        suspicious, details = is_suspicious_hostname("g\u043e\u043egle.com")
        assert suspicious
        assert details.has_confusables

    def test_punycode_not_suspicious(self) -> None:
        suspicious, _ = is_suspicious_hostname("xn--n3h.com")
        assert not suspicious

    def test_subdomain_checked(self) -> None:
        suspicious, details = is_suspicious_hostname("www.\u0440\u0430ypal.com")
        assert suspicious

    def test_all_latin_not_suspicious(self) -> None:
        suspicious, details = is_suspicious_hostname("example.org")
        assert not suspicious
        assert details.scripts == ["Latin"]

    def test_mixed_non_latin_scripts_suspicious(self) -> None:
        # #254: a label mixing two non-Latin scripts (Cyrillic я + Greek ψ) with
        # no Latin confusable used to report not-suspicious. The conservative
        # policy now flags any mixed-script label as suspicious.
        suspicious, details = is_suspicious_hostname("яψ.com")
        assert suspicious
        assert details.mixed_script
        # The mixed-script rule, not the confusable check, is what catches this.
        assert not details.has_confusables

    def test_analysis_attributes(self) -> None:
        _, details = is_suspicious_hostname("test.com")
        assert hasattr(details, "suspicious")
        assert hasattr(details, "scripts")
        assert hasattr(details, "mixed_script")
        assert hasattr(details, "has_confusables")
        assert hasattr(details, "canonical")

    # --- Regression: fix #3 — IPv6 literals must not trigger script analysis ---

    def test_ipv6_loopback_not_suspicious(self) -> None:
        """[::1] is an IPv6 literal — not an IDN hostname, must not be flagged."""
        suspicious, details = is_suspicious_hostname("[::1]")
        assert not suspicious
        assert not details.mixed_script
        assert not details.has_confusables

    def test_ipv6_full_address_not_suspicious(self) -> None:
        """[2001:db8::1] must be treated as not-suspicious without script analysis."""
        suspicious, details = is_suspicious_hostname("[2001:db8::1]")
        assert not suspicious
        assert details.scripts == []

    def test_ipv6_with_port_like_syntax_not_suspicious(self) -> None:
        """Bracket + colon is the distinguishing pattern for IPv6 literals."""
        suspicious, _ = is_suspicious_hostname("[fe80::1%eth0]")
        assert not suspicious


# ===== Encoding Detection =====


class TestDetectEncoding:
    def test_utf8_detection(self) -> None:
        enc, conf = detect_encoding("café résumé".encode())
        assert enc == "UTF-8"
        assert conf > 0.0

    def test_utf8_bom(self) -> None:
        enc, _ = detect_encoding(b"\xef\xbb\xbfhello")
        assert enc == "UTF-8"

    def test_ascii_detection(self) -> None:
        enc, _ = detect_encoding(b"hello world")
        # Pure ASCII may be detected as windows-1252 or UTF-8
        assert enc in ("UTF-8", "windows-1252")

    def test_returns_tuple(self) -> None:
        result = detect_encoding(b"test")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], float)


class TestDecodeToUtf8:
    def test_utf8_explicit(self) -> None:
        text, had_errors = decode_to_utf8("café".encode(), encoding="UTF-8")
        assert text == "café"
        assert not had_errors

    def test_latin1_explicit(self) -> None:
        latin1 = bytes([0x63, 0x61, 0x66, 0xE9])  # café in ISO-8859-1
        text, had_errors = decode_to_utf8(latin1, encoding="ISO-8859-1")
        assert text == "café"
        assert not had_errors

    def test_windows1252_explicit(self) -> None:
        # "smart quotes" in windows-1252: \x93 = ", \x94 = "
        data = bytes([0x93, 0x68, 0x65, 0x6C, 0x6C, 0x6F, 0x94])
        text, had_errors = decode_to_utf8(data, encoding="windows-1252")
        assert "\u201c" in text  # left double quote
        assert "hello" in text

    def test_shift_jis_explicit(self) -> None:
        # "テスト" in Shift-JIS
        sjis = "テスト".encode("shift_jis")
        text, had_errors = decode_to_utf8(sjis, encoding="Shift_JIS")
        assert text == "テスト"
        assert not had_errors

    def test_auto_detect(self) -> None:
        text, _ = decode_to_utf8(b"hello world")
        assert text == "hello world"

    def test_unknown_encoding_raises(self) -> None:
        with pytest.raises(DisarmError):
            decode_to_utf8(b"test", encoding="FAKE-999")

    def test_lossy_decode(self) -> None:
        # Invalid UTF-8 byte sequence decoded as UTF-8 should flag errors
        bad_utf8 = bytes([0x63, 0x61, 0x66, 0xC3])  # truncated UTF-8
        text, had_errors = decode_to_utf8(bad_utf8, encoding="UTF-8")
        assert had_errors  # replacement character used


# ===== sanitize_filename NFC normalization =====


class TestFilenameNFC:
    def test_nfd_input_produces_consistent_output(self) -> None:
        """NFD and NFC input should produce the same filename."""
        nfc = "r\u00e9sum\u00e9.pdf"  # NFC: precomposed é
        nfd = "re\u0301sume\u0301.pdf"  # NFD: e + combining accent
        assert sanitize_filename(nfc) == sanitize_filename(nfd)

    def test_macos_nfd_filename(self) -> None:
        """macOS APFS stores filenames in NFD; NFC normalization prevents mismatches."""
        # Simulated macOS NFD filename
        nfd_name = "cafe\u0301.txt"
        result = sanitize_filename(nfd_name)
        # Should produce the same result as NFC input
        nfc_name = "caf\u00e9.txt"
        assert sanitize_filename(nfc_name) == result
