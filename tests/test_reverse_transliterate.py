"""Tests for reverse transliteration (A1): romanized Latin → native script."""

import pytest

from translit import reverse_langs, transliterate


class TestReverseLangs:
    def test_returns_list(self):
        result = reverse_langs()
        assert isinstance(result, list)

    def test_contains_expected_langs(self):
        langs = reverse_langs()
        assert "ru" in langs
        assert "uk" in langs
        assert "el" in langs

    def test_unsupported_lang_not_present(self):
        assert "de" not in reverse_langs()


class TestReverseRussian:
    def test_basic_word(self):
        assert transliterate("Moskva", target="ru") == "Москва"

    def test_digraph_zh(self):
        assert transliterate("zh", target="ru") == "ж"

    def test_digraph_sh(self):
        assert transliterate("sh", target="ru") == "ш"

    def test_digraph_ch(self):
        assert transliterate("ch", target="ru") == "ч"

    def test_trigraph_shch(self):
        assert transliterate("shch", target="ru") == "щ"

    def test_digraph_yu(self):
        assert transliterate("yu", target="ru") == "ю"

    def test_digraph_ya(self):
        assert transliterate("ya", target="ru") == "я"

    def test_passthrough_numbers(self):
        assert transliterate("123!", target="ru") == "123!"

    def test_mixed_text(self):
        result = transliterate("Privet, mir!", target="ru")
        assert "П" in result or "п" in result  # at least some conversion


class TestReverseAllCapsMultigraph:
    """#255 C4: all-caps romanizations of multigraphs (no cased table entry —
    only Shch/shch etc.) recover the native form by falling back to the
    lowercase key and re-uppercasing, instead of decomposing char-by-char."""

    def test_trigraph_all_caps(self):
        assert transliterate("SHCH", target="ru") == "Щ"

    def test_digraphs_all_caps(self):
        assert transliterate("SH", target="ru") == "Ш"
        assert transliterate("ZH", target="ru") == "Ж"
        assert transliterate("CH", target="ru") == "Ч"
        assert transliterate("YU", target="ru") == "Ю"

    def test_all_caps_word(self):
        assert transliterate("MOSKVA", target="ru") == "МОСКВА"

    def test_title_and_lower_unchanged(self):
        # The fix must not disturb the cased entries that already worked.
        assert transliterate("Shch", target="ru") == "Щ"
        assert transliterate("shch", target="ru") == "щ"
        assert transliterate("Moskva", target="ru") == "Москва"
        assert transliterate("moskva", target="ru") == "москва"


class TestReverseUkrainian:
    def test_basic_word(self):
        result = transliterate("Kyiv", target="uk")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_digraph_zh(self):
        assert transliterate("zh", target="uk") == "ж"

    def test_digraph_shch(self):
        assert transliterate("shch", target="uk") == "щ"

    def test_yi_mapping(self):
        assert transliterate("yi", target="uk") == "ї"

    def test_ye_mapping(self):
        assert transliterate("ye", target="uk") == "є"


class TestReverseGreek:
    def test_digraph_th(self):
        assert transliterate("th", target="el") == "θ"

    def test_digraph_ph(self):
        assert transliterate("ph", target="el") == "φ"

    def test_digraph_ch(self):
        assert transliterate("ch", target="el") == "χ"

    def test_digraph_ps(self):
        assert transliterate("ps", target="el") == "ψ"

    def test_single_char(self):
        assert transliterate("a", target="el") == "α"

    def test_uppercase(self):
        assert transliterate("A", target="el") == "Α"


class TestReverseErrors:
    def test_unsupported_lang_raises(self):
        with pytest.raises(ValueError, match="not supported"):
            transliterate("hello", target="de")

    def test_empty_string(self):
        assert transliterate("", target="ru") == ""


class TestMutualExclusion:
    def test_lang_and_target_raises(self):
        with pytest.raises(ValueError, match="mutually exclusive"):
            transliterate("hello", lang="ru", target="ru")


class TestForwardOnlyParamError:
    def test_errors_with_target_raises(self):
        with pytest.raises(ValueError, match="errors"):
            transliterate("hello", target="ru", errors="ignore")

    def test_strict_iso9_with_target_raises(self):
        with pytest.raises(ValueError, match="strict_iso9"):
            transliterate("hello", target="ru", strict_iso9=True)

    def test_gost7034_with_target_raises(self):
        with pytest.raises(ValueError, match="gost7034"):
            transliterate("hello", target="ru", gost7034=True)

    def test_tones_with_target_raises(self):
        with pytest.raises(ValueError, match="tones"):
            transliterate("hello", target="ru", tones=True)

    def test_replace_with_with_target_raises(self):
        with pytest.raises(ValueError, match="replace_with"):
            transliterate("hello", target="ru", replace_with="?")


class TestBatchWithTarget:
    def test_batch_reverse(self):

        result = transliterate(["Moskva", "Kyiv"], target="ru")
        assert result[0] == "Москва"
