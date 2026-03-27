"""Tests for ancient and historic script transliteration."""

from translit import Script, detect_scripts, slugify, transliterate


class TestRunic:
    def test_elder_futhark(self):
        assert transliterate("ᚠᚢᚦᚨᚱᚲ") == "futhark"

    def test_runic_hello(self):
        assert transliterate("ᚺᛖᛚᛚᛟ") == "hello"

    def test_runic_thorn(self):
        assert transliterate("ᚦ") == "th"

    def test_runic_ng(self):
        assert transliterate("ᛜ") == "ng"

    def test_runic_punctuation(self):
        assert transliterate("᛫") == "."
        assert transliterate("᛬") == ":"

    def test_runic_slug(self):
        assert slugify("ᚠᚢᚦᚨᚱᚲ") == "futhark"

    def test_runic_script_detection(self):
        assert detect_scripts("ᚠᚢᚦ") == [Script.RUNIC]


class TestOgham:
    def test_ogham_aicme(self):
        assert transliterate("ᚁᚂᚃᚄᚅ") == "blfsn"

    def test_ogham_vowels(self):
        assert transliterate("ᚐᚑᚒᚓᚔ") == "aouei"

    def test_ogham_script_detection(self):
        assert detect_scripts("ᚁᚂᚃ") == [Script.OGHAM]


class TestGothic:
    def test_gothic_alphabet_start(self):
        assert transliterate("𐌰𐌱𐌲𐌳") == "abgd"

    def test_gothic_hails(self):
        assert transliterate("𐌷𐌰𐌹𐌻𐍃") == "hails"

    def test_gothic_thiuth(self):
        assert transliterate("𐌸") == "th"

    def test_gothic_hwair(self):
        assert transliterate("𐍈") == "hw"

    def test_gothic_slug(self):
        assert slugify("𐌷𐌰𐌹𐌻𐍃") == "hails"

    def test_gothic_script_detection(self):
        assert detect_scripts("𐌰𐌱𐌲") == [Script.GOTHIC]


class TestOldPersian:
    def test_old_persian_vowels(self):
        assert transliterate("𐎠𐎡𐎢") == "aiu"

    def test_old_persian_darius(self):
        # Approximation of "Dārayavauš" in Old Persian cuneiform
        assert transliterate("𐎭𐎠𐎼𐎹𐎺𐎢𐏁") == "daarayavausha"

    def test_old_persian_syllables(self):
        assert transliterate("𐎣𐎠") == "kaa"
        assert transliterate("𐎰𐎠") == "thaa"

    def test_old_persian_slug(self):
        assert slugify("𐎭𐎠𐎼𐎹𐎺𐎢𐏁") == "daarayavausha"

    def test_old_persian_script_detection(self):
        assert detect_scripts("𐎠𐎡𐎢") == [Script.OLD_PERSIAN]


class TestLinearB:
    def test_linear_b_vowels(self):
        assert transliterate("𐀀𐀁𐀂𐀃𐀄") == "aeiou"

    def test_linear_b_syllables(self):
        assert transliterate("𐀅𐀆𐀇𐀈𐀉") == "dadedido" + "du"

    def test_linear_b_ka_series(self):
        assert transliterate("𐀐𐀑𐀒𐀓𐀔") == "kakekikoku"

    def test_linear_b_script_detection(self):
        assert detect_scripts("𐀀𐀁𐀂") == [Script.LINEAR_B]


class TestCherokee:
    def test_cherokee_vowels(self):
        assert transliterate("ᎠᎡᎢᎣᎤ") == "aeiou"

    def test_cherokee_tsalagi(self):
        """The Cherokee word for 'Cherokee'."""
        assert transliterate("ᏣᎳᎩ") == "tsalagi"

    def test_cherokee_slug(self):
        assert slugify("ᏣᎳᎩ") == "tsalagi"

    def test_cherokee_script_detection(self):
        assert detect_scripts("ᎠᎡᎢ") == [Script.CHEROKEE]

    def test_cherokee_ga_series(self):
        assert transliterate("Ꭶ") == "ga"
        assert transliterate("Ꭷ") == "ka"


class TestCanadianSyllabics:
    def test_cree_vowels(self):
        # U+1401=e, U+1403=i, U+1405=o, U+1407=a
        assert transliterate("\u1401") == "e"
        assert transliterate("\u1403") == "i"
        assert transliterate("\u1405") == "o"
        assert transliterate("\u1407") == "a"

    def test_cree_consonant_series(self):
        # U+1474=ki, U+14C2=ni, U+14EC=si
        assert transliterate("\u1474") == "ki"
        assert transliterate("\u14C2") == "ni"
        assert transliterate("\u14EC") == "si"

    def test_cree_script_detection(self):
        assert detect_scripts("\u1403\u1474\u14C4") == [Script.CANADIAN_ABORIGINAL]


class TestMongolian:
    def test_mongolian_vowels(self):
        assert transliterate("ᠠᠡᠢᠣᠤ") == "aeiou"

    def test_mongolian_consonants(self):
        assert transliterate("ᠨ") == "n"
        assert transliterate("ᠪ") == "b"
        assert transliterate("ᠮ") == "m"

    def test_mongolian_digits(self):
        assert transliterate("᠑᠒᠓") == "123"

    def test_mongolian_script_detection(self):
        assert detect_scripts("ᠠᠡᠢ") == [Script.MONGOLIAN]


class TestScriptEnum:
    def test_gothic_enum(self):
        assert Script.GOTHIC.value == "Gothic"

    def test_old_persian_enum(self):
        assert Script.OLD_PERSIAN.value == "OldPersian"

    def test_linear_b_enum(self):
        assert Script.LINEAR_B.value == "LinearB"

    def test_cuneiform_enum(self):
        assert Script.CUNEIFORM.value == "Cuneiform"
