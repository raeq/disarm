"""Tests for translit encoding detection and decoding.

Covers UTF-8, UTF-16, Windows-1252, ISO-8859-1, Shift_JIS, EUC-JP,
EUC-KR, Big5, GB18030, and edge cases.
"""

from __future__ import annotations

from translit import detect_encoding, decode_to_utf8


class TestDetectEncoding:
    """Encoding detection tests."""

    def test_utf8_ascii(self) -> None:
        enc, conf = detect_encoding(b"Hello World")
        assert enc.upper() in ("UTF-8", "ASCII", "WINDOWS-1252")

    def test_utf8_with_bom(self) -> None:
        data = b"\xef\xbb\xbf" + "café".encode("utf-8")
        enc, conf = detect_encoding(data)
        assert "UTF" in enc.upper()

    def test_utf8_multibyte(self) -> None:
        data = "北京是中国的首都".encode("utf-8")
        enc, conf = detect_encoding(data)
        assert enc.upper() == "UTF-8"

    def test_utf8_cyrillic(self) -> None:
        data = "Москва — столица России".encode("utf-8")
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
        enc, conf = detect_encoding("Hello World".encode("utf-8"))
        assert 0.0 <= conf <= 1.0


class TestDecodeToUtf8:
    """Decoding tests."""

    def test_utf8_roundtrip(self) -> None:
        text, had_errors = decode_to_utf8("café résumé".encode("utf-8"), "utf-8")
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
