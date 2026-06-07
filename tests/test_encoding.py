"""Tests for translit encoding detection and decoding.

Covers UTF-8, UTF-16, Windows-1252, ISO-8859-1, Shift_JIS, EUC-JP,
EUC-KR, Big5, GB18030, and edge cases.
"""

from __future__ import annotations

import pytest

from translit import decode_to_utf8, detect_encoding


class TestDetectEncoding:
    """Encoding detection tests."""

    def test_utf8_ascii(self) -> None:
        enc, conf = detect_encoding(b"Hello World")
        assert enc.upper() in ("UTF-8", "ASCII", "WINDOWS-1252")

    def test_utf8_with_bom(self) -> None:
        data = b"\xef\xbb\xbf" + "café".encode()
        enc, conf = detect_encoding(data)
        assert "UTF" in enc.upper()

    def test_utf8_multibyte(self) -> None:
        data = "北京是中国的首都".encode()
        enc, conf = detect_encoding(data)
        assert enc.upper() == "UTF-8"

    def test_utf8_cyrillic(self) -> None:
        data = "Москва — столица России".encode()
        enc, conf = detect_encoding(data)
        assert enc.upper() == "UTF-8"

    def test_windows_1252(self) -> None:
        # Classic Windows-1252 text with smart quotes and em-dash
        data = b"caf\xe9 r\xe9sum\xe9"  # café résumé in windows-1252
        enc, _conf = detect_encoding(data)
        # chardetng may detect as windows-1252 or ISO-8859-1
        assert enc.upper() in ("WINDOWS-1252", "ISO-8859-1")

    def test_shift_jis(self) -> None:
        data = "東京タワー".encode("shift_jis")
        enc, _conf = detect_encoding(data)
        assert "SHIFT" in enc.upper() or "SJIS" in enc.upper() or "JIS" in enc.upper()

    def test_euc_jp(self) -> None:
        data = "日本語テスト".encode("euc_jp")
        enc, _conf = detect_encoding(data)
        assert "EUC" in enc.upper() or "JP" in enc.upper()

    def test_euc_kr(self) -> None:
        data = "한국어 테스트".encode("euc_kr")
        enc, _conf = detect_encoding(data)
        # chardetng may report as EUC-KR or windows-949
        assert "EUC" in enc.upper() or "KR" in enc.upper() or "949" in enc.upper()

    def test_big5(self) -> None:
        # Longer text needed for accurate detection — short Big5 is ambiguous
        data = "中文測試繁體字編碼偵測範例資料".encode("big5")
        enc, _conf = detect_encoding(data)
        assert "BIG5" in enc.upper() or "BIG" in enc.upper()

    def test_gb18030(self) -> None:
        data = "中文测试数据".encode("gb18030")
        enc, _conf = detect_encoding(data)
        # chardetng may report GBK, GB2312, or GB18030
        assert "GB" in enc.upper()

    def test_iso_8859_1(self) -> None:
        data = "Ångström café naïve".encode("iso-8859-1")
        enc, _conf = detect_encoding(data)
        assert enc.upper() in ("WINDOWS-1252", "ISO-8859-1")

    def test_empty_bytes(self) -> None:
        enc, conf = detect_encoding(b"")
        assert isinstance(enc, str)
        assert isinstance(conf, float)

    def test_confidence_range(self) -> None:
        enc, conf = detect_encoding(b"Hello World")
        assert 0.0 <= conf <= 1.0


class TestDecodeToUtf8:
    """Decoding tests."""

    def test_utf8_roundtrip(self) -> None:
        text, had_errors = decode_to_utf8("café résumé".encode(), "utf-8")
        assert text == "café résumé"
        assert not had_errors

    def test_windows_1252_decode(self) -> None:
        data = b"caf\xe9 r\xe9sum\xe9"
        text, had_errors = decode_to_utf8(data, "windows-1252")
        assert text == "café résumé"
        assert not had_errors

    def test_shift_jis_decode(self) -> None:
        original = "東京タワー"
        data = original.encode("shift_jis")
        text, had_errors = decode_to_utf8(data, "shift_jis")
        assert text == original
        assert not had_errors

    def test_euc_jp_decode(self) -> None:
        original = "日本語テスト"
        data = original.encode("euc_jp")
        text, had_errors = decode_to_utf8(data, "euc-jp")
        assert text == original
        assert not had_errors

    def test_euc_kr_decode(self) -> None:
        original = "한국어 테스트"
        data = original.encode("euc_kr")
        text, had_errors = decode_to_utf8(data, "euc-kr")
        assert text == original
        assert not had_errors

    def test_big5_decode(self) -> None:
        original = "中文測試"
        data = original.encode("big5")
        text, had_errors = decode_to_utf8(data, "big5")
        assert text == original
        assert not had_errors

    def test_gb18030_decode(self) -> None:
        original = "中文测试数据"
        data = original.encode("gb18030")
        text, had_errors = decode_to_utf8(data, "gb18030")
        assert text == original
        assert not had_errors

    def test_iso_8859_1_decode(self) -> None:
        original = "Ångström café naïve"
        data = original.encode("iso-8859-1")
        text, had_errors = decode_to_utf8(data, "windows-1252")
        assert text == original
        assert not had_errors

    def test_auto_detect_utf8(self) -> None:
        original = "北京是中国的首都"
        data = original.encode("utf-8")
        text, had_errors = decode_to_utf8(data)
        assert text == original

    def test_auto_detect_windows_1252(self) -> None:
        # Long enough for detection
        data = b"caf\xe9 r\xe9sum\xe9 na\xefve \xc5ngstr\xf6m"
        text, _had_errors = decode_to_utf8(data)
        assert "café" in text

    def test_empty_bytes(self) -> None:
        text, had_errors = decode_to_utf8(b"", "utf-8")
        assert text == ""
        assert not had_errors

    def test_invalid_bytes_lossy(self) -> None:
        # Invalid UTF-8 continuation bytes (0x80-0xBF without a leading byte)
        data = b"\xc3\x28\xc3\x28"  # broken UTF-8 sequences
        text, had_errors = decode_to_utf8(data, "utf-8")
        assert isinstance(text, str)
        assert had_errors  # replacement characters used

    def test_latin1_with_special_chars(self) -> None:
        # Characters that differ between ISO-8859-1 and Windows-1252
        data = bytes(range(0xA0, 0x100))
        text, had_errors = decode_to_utf8(data, "windows-1252")
        assert isinstance(text, str)
        assert len(text) > 0

    def test_min_confidence_explicit_encoding_ignores_threshold(self) -> None:
        # Explicit encoding always succeeds regardless of min_confidence.
        text, had_errors = decode_to_utf8(b"hello", "UTF-8", min_confidence=1.0)
        assert text == "hello"
        assert not had_errors

    def test_min_confidence_low_threshold_accepts(self) -> None:
        # Default threshold (0.0) never rejects auto-detection.
        text, _ = decode_to_utf8(b"hello world")
        assert "hello world" in text

    def test_min_confidence_high_threshold_rejects(self) -> None:
        # detect_encoding returns at most 0.95; threshold of 1.0 always rejects.
        from translit import TranslitError

        with pytest.raises(TranslitError, match="below the required minimum"):
            decode_to_utf8(b"hi", min_confidence=1.0)

    def test_min_confidence_high_threshold_explicit_encoding_ok(self) -> None:
        # Explicit encoding is never affected by min_confidence.
        text, _ = decode_to_utf8(b"hi", "UTF-8", min_confidence=0.9)
        assert text == "hi"


class TestAdversarialDecodePath:
    """No-panic + invariant preservation for hostile raw bytes (#78).

    Per THREAT_MODEL.md, detection *accuracy* on ambiguous bytes is a quality
    property, not a security one. These assert the security bar: no panic, a
    valid `str` out, confidence in range, and `had_errors`/`min_confidence`
    semantics — never a stronger promise.
    """

    ADVERSARIAL = {
        "truncated_utf8_lead": b"\xc3",
        "truncated_3byte_utf8": b"\xe2\x82",
        "overlong_nul": b"\xc0\x80",
        "overlong_slash": b"\xe0\x80\xaf",
        "cesu8_surrogate": b"\xed\xa0\x80",
        "utf16le_bom": b"\xff\xfe\x41\x00",
        "utf16be_bom": b"\xfe\xff\x00\x41",
        "utf8_bom_then_latin1": b"\xef\xbb\xbf\xff",
        "embedded_nul": b"a\x00b",
        "c1_controls": b"\x80\x81\x82\x9f",
        "all_high_bytes": bytes(range(0x80, 0x100)),
        "invalid_lossy": b"\xc3\x28\xc3\x28",
        "fe_ff_noise": b"\xfe\xff\xfe\xff",
    }
    EDGE = {"empty": b"", "one_ff": b"\xff", "one_nul": b"\x00", "one_ascii": b"A"}

    SUPPORTED_ENCODINGS = [
        "utf-8",
        "utf-16",
        "shift_jis",
        "euc-jp",
        "euc-kr",
        "big5",
        "gb18030",
        "windows-1252",
    ]

    @staticmethod
    def _assert_invariants(data: bytes) -> None:
        enc, conf = detect_encoding(data)
        assert isinstance(enc, str) and enc
        assert 0.0 <= conf <= 1.0, f"confidence {conf} out of range for {data!r}"
        s, had_errors = decode_to_utf8(data, min_confidence=0.0)
        assert isinstance(s, str)
        assert isinstance(had_errors, bool)
        # A Rust String cannot hold lone surrogates; assert it explicitly anyway.
        assert not any(0xD800 <= ord(c) <= 0xDFFF for c in s), f"surrogate leak: {data!r}"

    @pytest.mark.parametrize("name,data", list(ADVERSARIAL.items()) + list(EDGE.items()))
    def test_auto_detect_no_panic_and_invariants(self, name, data) -> None:
        self._assert_invariants(data)

    @pytest.mark.parametrize("encoding", SUPPORTED_ENCODINGS)
    @pytest.mark.parametrize("name,data", list(ADVERSARIAL.items()))
    def test_explicit_encoding_no_panic(self, encoding, name, data) -> None:
        # Each explicit encoding must decode hostile bytes to a valid str
        # without panicking (lossy is fine; that is what had_errors reports).
        s, had_errors = decode_to_utf8(data, encoding=encoding)
        assert isinstance(s, str)
        assert isinstance(had_errors, bool)
        assert not any(0xD800 <= ord(c) <= 0xDFFF for c in s)

    def test_min_confidence_rejects_low_confidence(self) -> None:
        from translit import TranslitError

        # An unreachable confidence floor must raise, not silently guess (#66).
        with pytest.raises(TranslitError, match="confidence"):
            decode_to_utf8(b"\xff\xfe\x80\x81", min_confidence=1.0)

    def test_unknown_encoding_raises(self) -> None:
        from translit import TranslitError

        with pytest.raises(TranslitError, match="[Uu]nknown encoding"):
            decode_to_utf8(b"x", encoding="no-such-encoding")

    def test_large_hostile_input_is_linear(self) -> None:
        # Guard against super-linear blowup on the decode path: a 1 MiB hostile
        # buffer must complete quickly and return a str.
        data = b"\xc3\x28" * 524_288  # 1 MiB of invalid UTF-8
        s, had_errors = decode_to_utf8(data, encoding="utf-8")
        assert isinstance(s, str)
