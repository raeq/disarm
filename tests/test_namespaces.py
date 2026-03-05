"""Verify that the structured namespace imports work correctly."""

from __future__ import annotations


class TestCodecNamespace:
    def test_import_detect_encoding(self) -> None:
        from translit.codec import detect_encoding

        enc, conf = detect_encoding(b"hello world")
        assert isinstance(enc, str)
        assert isinstance(conf, float)

    def test_import_decode_to_utf8(self) -> None:
        from translit.codec import decode_to_utf8

        text, had_errors = decode_to_utf8(b"caf\xc3\xa9", encoding="UTF-8")
        assert text == "cafe\u0301" or text == "caf\u00e9" or text == "café"
        assert isinstance(had_errors, bool)

    def test_codec_all(self) -> None:
        import translit.codec

        assert "decode_to_utf8" in translit.codec.__all__
        assert "detect_encoding" in translit.codec.__all__


class TestSecurityNamespace:
    def test_import_is_confusable(self) -> None:
        from translit.security import is_confusable

        assert isinstance(is_confusable("a"), bool)

    def test_import_is_mixed_script(self) -> None:
        from translit.security import is_mixed_script

        assert isinstance(is_mixed_script("hello"), bool)

    def test_import_is_safe_hostname(self) -> None:
        from translit.security import is_safe_hostname

        safe, details = is_safe_hostname("example.com")
        assert isinstance(safe, bool)

    def test_import_detect_scripts(self) -> None:
        from translit.security import Script, detect_scripts

        scripts = detect_scripts("hello")
        assert isinstance(scripts, list)
        assert all(isinstance(s, Script) for s in scripts)

    def test_import_security_clean(self) -> None:
        from translit.security import security_clean

        assert isinstance(security_clean("test"), str)

    def test_import_strip_bidi(self) -> None:
        from translit.security import strip_bidi

        assert isinstance(strip_bidi("test"), str)

    def test_security_all(self) -> None:
        import translit.security

        for name in (
            "is_confusable",
            "is_mixed_script",
            "is_safe_hostname",
            "detect_scripts",
            "normalize_confusables",
            "security_clean",
            "strip_bidi",
        ):
            assert name in translit.security.__all__, f"{name} missing from __all__"


class TestFilesNamespace:
    def test_import_sanitize_filename(self) -> None:
        from translit.files import sanitize_filename

        result = sanitize_filename("hello.txt")
        assert isinstance(result, str)

    def test_files_all(self) -> None:
        import translit.files

        assert "sanitize_filename" in translit.files.__all__


class TestNormalizeNamespace:
    def test_import_normalize(self) -> None:
        from translit.normalization import normalize

        result = normalize("cafe\u0301", form="NFC")
        assert isinstance(result, str)

    def test_import_strip_accents(self) -> None:
        from translit.normalization import strip_accents

        assert strip_accents("cafe\u0301") == "cafe"

    def test_import_fold_case(self) -> None:
        from translit.normalization import fold_case

        assert fold_case("ABC") == "abc"

    def test_import_collapse_whitespace(self) -> None:
        from translit.normalization import collapse_whitespace

        assert collapse_whitespace("  a  b  ") == "a b"

    def test_import_is_normalized(self) -> None:
        from translit.normalization import is_normalized

        assert isinstance(is_normalized("abc", form="NFC"), bool)

    def test_normalize_all(self) -> None:
        import translit.normalization

        for name in (
            "normalize",
            "strip_accents",
            "fold_case",
            "collapse_whitespace",
            "is_normalized",
            "normalize_batch",
            "strip_accents_batch",
        ):
            assert name in translit.normalization.__all__, f"{name} missing from __all__"


class TestBackwardCompatibility:
    """Top-level imports must continue to work."""

    def test_top_level_decode_to_utf8(self) -> None:
        from translit import decode_to_utf8

        assert callable(decode_to_utf8)

    def test_top_level_is_confusable(self) -> None:
        from translit import is_confusable

        assert callable(is_confusable)

    def test_top_level_sanitize_filename(self) -> None:
        from translit import sanitize_filename

        assert callable(sanitize_filename)

    def test_top_level_fold_case(self) -> None:
        from translit import fold_case

        assert callable(fold_case)

    def test_identical_decode_to_utf8(self) -> None:
        from translit import decode_to_utf8 as top
        from translit.codec import decode_to_utf8 as sub

        assert top is sub

    def test_identical_is_confusable(self) -> None:
        from translit import is_confusable as top
        from translit.security import is_confusable as sub

        assert top is sub

    def test_identical_sanitize_filename(self) -> None:
        from translit import sanitize_filename as top
        from translit.files import sanitize_filename as sub

        assert top is sub

    def test_identical_fold_case(self) -> None:
        from translit import fold_case as top
        from translit.normalization import fold_case as sub

        assert top is sub
