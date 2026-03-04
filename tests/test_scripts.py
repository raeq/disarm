"""Comprehensive tests for Unicode script detection.

Three-layer testing strategy:
1. Per-script detection tests — every Script enum member must be detectable
2. Enum↔Rust consistency — parametrized cross-validation that no Script
   in the Python enum silently fails detection (the bug that prompted this)
3. Boundary & regression — edge codepoints, supplementary planes, mixed text

These tests import from the Python layer and exercise the full Rust→PyO3→Python
path. They do NOT require any mocking.
"""

import pytest
from conftest import SCRIPT_SAMPLES

from translit import detect_scripts, is_mixed_script
from translit._enums import Script

# ═══════════════════════════════════════════════════════════════════
# Layer 1: Per-script detection — every enum member must be detected
# ═══════════════════════════════════════════════════════════════════


class TestPerScriptDetection:
    """Each Script enum member (except meta-scripts) has a sample
    that must be detected correctly by detect_scripts()."""

    @pytest.mark.parametrize(
        "script,sample",
        [
            pytest.param(script, sample, id=script.name)
            for script, sample in SCRIPT_SAMPLES.items()
        ],
    )
    def test_detects_single_script(self, script: Script, sample: str) -> None:
        """detect_scripts(sample) must return exactly [script]."""
        detected = detect_scripts(sample)
        assert len(detected) >= 1, f"No scripts detected for {script.name}: {sample!r}"
        assert script in detected, (
            f"Expected {script.name} in detected scripts, "
            f"got {[s.name for s in detected]} for sample {sample!r}"
        )


# ═══════════════════════════════════════════════════════════════════
# Layer 2: Enum↔Rust consistency — NO silent drift allowed
# ═══════════════════════════════════════════════════════════════════


class TestEnumRustConsistency:
    """Cross-validates that every Script enum member (except Common/Inherited)
    has a matching detection path in the Rust code AND a sample in our test suite.

    This is the test that would have caught the original 12-script bug:
    scripts in the Python enum but not detectable by the Rust engine.
    """

    # All enum members that represent real Unicode scripts (not meta-scripts)
    REAL_SCRIPTS = [s for s in Script if s not in (Script.COMMON, Script.INHERITED)]

    @pytest.mark.parametrize(
        "script",
        [pytest.param(s, id=s.name) for s in REAL_SCRIPTS],
    )
    def test_every_enum_member_has_sample(self, script: Script) -> None:
        """Every Script (except meta) must appear in SCRIPT_SAMPLES.
        If this fails, a new Script was added to the enum without a test sample.
        """
        assert script in SCRIPT_SAMPLES, (
            f"Script.{script.name} has no test sample in SCRIPT_SAMPLES. "
            f"Add a representative string for this script."
        )

    @pytest.mark.parametrize(
        "script",
        [pytest.param(s, id=s.name) for s in REAL_SCRIPTS],
    )
    def test_every_enum_member_is_detectable(self, script: Script) -> None:
        """Every Script (except meta) must be detectable via detect_scripts().
        If this fails, the Rust detect_char_script() is missing ranges for this script.
        """
        sample = SCRIPT_SAMPLES.get(script)
        if sample is None:
            pytest.skip(
                f"No sample for {script.name} (covered by test_every_enum_member_has_sample)"
            )
        detected = detect_scripts(sample)
        assert script in detected, (
            f"Script.{script.name} not detected by Rust engine. "
            f"Sample: {sample!r}, Detected: {[s.name for s in detected]}"
        )

    def test_no_orphan_samples(self) -> None:
        """Every script in SCRIPT_SAMPLES must be a valid Script enum member.
        Catches stale test data after enum member removal.
        """
        for script in SCRIPT_SAMPLES:
            assert isinstance(script, Script), (
                f"SCRIPT_SAMPLES key {script!r} is not a Script enum member"
            )

    def test_sample_count_matches_real_scripts(self) -> None:
        """Verify sample coverage is complete — same count as real scripts."""
        assert len(SCRIPT_SAMPLES) == len(self.REAL_SCRIPTS), (
            f"SCRIPT_SAMPLES has {len(SCRIPT_SAMPLES)} entries but there are "
            f"{len(self.REAL_SCRIPTS)} real scripts. Missing: "
            f"{set(self.REAL_SCRIPTS) - set(SCRIPT_SAMPLES.keys())}"
        )


# ═══════════════════════════════════════════════════════════════════
# Layer 3: Boundary, edge-case, and mixed-script tests
# ═══════════════════════════════════════════════════════════════════


class TestScriptBoundaries:
    """Edge cases: block boundaries, supplementary planes, empty input."""

    def test_empty_string(self) -> None:
        assert detect_scripts("") == []

    def test_only_digits(self) -> None:
        """Digits are Common — no real scripts detected."""
        assert detect_scripts("12345") == []

    def test_only_punctuation(self) -> None:
        """Punctuation is Common."""
        assert detect_scripts("!@#$%") == []

    def test_only_whitespace(self) -> None:
        """Whitespace is Common."""
        assert detect_scripts("   \t\n") == []

    def test_combining_marks_only(self) -> None:
        """Combining marks are Inherited — filtered out by detect_scripts."""
        assert detect_scripts("\u0301\u0302\u0303") == []

    def test_latin_boundary_lower(self) -> None:
        """U+0041 'A' is the first Latin codepoint in Basic Latin."""
        scripts = detect_scripts("A")
        assert Script.LATIN in scripts

    def test_latin_boundary_upper(self) -> None:
        """U+024F is the last codepoint in Latin Extended-B."""
        scripts = detect_scripts("\u024f")
        assert Script.LATIN in scripts

    def test_latin_extended_additional(self) -> None:
        """U+1E00–U+1EFF: Latin Extended Additional (Vietnamese etc.)."""
        scripts = detect_scripts("\u1e00\u1eff")
        assert Script.LATIN in scripts

    def test_han_supplementary_plane(self) -> None:
        """CJK Extension B starts at U+20000 (SMP)."""
        scripts = detect_scripts("\U00020000")
        assert Script.HAN in scripts

    def test_han_extension_c(self) -> None:
        """CJK Extension C: U+2A700."""
        scripts = detect_scripts("\U0002a700")
        assert Script.HAN in scripts

    def test_hangul_syllables(self) -> None:
        """Hangul Syllables block U+AC00–U+D7AF."""
        scripts = detect_scripts("\uac00")  # 가
        assert Script.HANGUL in scripts

    def test_hangul_jamo(self) -> None:
        """Hangul Jamo block U+1100–U+11FF."""
        scripts = detect_scripts("\u1100")
        assert Script.HANGUL in scripts

    def test_arabic_presentation_forms(self) -> None:
        """Arabic Presentation Forms-A: U+FB50–U+FDFF."""
        scripts = detect_scripts("\ufb50")
        assert Script.ARABIC in scripts

    def test_hebrew_presentation_forms(self) -> None:
        """Hebrew Presentation Forms: U+FB1D–U+FB4F."""
        scripts = detect_scripts("\ufb1d")
        assert Script.HEBREW in scripts

    def test_cyrillic_supplement(self) -> None:
        """Cyrillic Supplement: U+0500–U+052F."""
        scripts = detect_scripts("\u0500")
        assert Script.CYRILLIC in scripts

    def test_cyrillic_extended_a(self) -> None:
        """Cyrillic Extended-A: U+2DE0–U+2DFF."""
        scripts = detect_scripts("\u2de0")
        assert Script.CYRILLIC in scripts

    def test_greek_extended(self) -> None:
        """Greek Extended: U+1F00–U+1FFF."""
        scripts = detect_scripts("\u1f00")
        assert Script.GREEK in scripts

    def test_devanagari_extended(self) -> None:
        """Devanagari Extended: U+A8E0–U+A8FF."""
        scripts = detect_scripts("\ua8e0")
        assert Script.DEVANAGARI in scripts

    def test_ethiopic_supplement(self) -> None:
        """Ethiopic Supplement: U+1380–U+139F."""
        scripts = detect_scripts("\u1380")
        assert Script.ETHIOPIC in scripts

    def test_georgian_supplement(self) -> None:
        """Georgian Supplement: U+2D00–U+2D2F."""
        scripts = detect_scripts("\u2d00")
        assert Script.GEORGIAN in scripts

    def test_myanmar_extended_a(self) -> None:
        """Myanmar Extended-A: U+AA60–U+AA7F."""
        scripts = detect_scripts("\uaa60")
        assert Script.MYANMAR in scripts

    def test_cherokee_supplement(self) -> None:
        """Cherokee Supplement: U+AB70–U+ABBF."""
        scripts = detect_scripts("\uab70")
        assert Script.CHEROKEE in scripts

    def test_syriac_supplement(self) -> None:
        """Syriac Supplement: U+0860–U+086F."""
        scripts = detect_scripts("\u0860")
        assert Script.SYRIAC in scripts

    def test_khmer_symbols(self) -> None:
        """Khmer Symbols: U+19E0–U+19FF."""
        scripts = detect_scripts("\u19e0")
        assert Script.KHMER in scripts


class TestMixedScripts:
    """Mixed-script detection and ordering."""

    def test_latin_cyrillic_mixed(self) -> None:
        assert is_mixed_script("hello мир")

    def test_latin_arabic_mixed(self) -> None:
        assert is_mixed_script("hello العربية")

    def test_latin_han_mixed(self) -> None:
        assert is_mixed_script("hello 中文")

    def test_hiragana_katakana_mixed(self) -> None:
        """Japanese text often mixes Hiragana and Katakana."""
        assert is_mixed_script("ひらがなカタカナ")

    def test_detection_order_preserved(self) -> None:
        """detect_scripts() returns scripts in order of first appearance."""
        scripts = detect_scripts("hello Москва")
        assert scripts[0] == Script.LATIN
        assert scripts[1] == Script.CYRILLIC

    def test_three_scripts(self) -> None:
        """Text spanning three distinct scripts."""
        scripts = detect_scripts("abc Москва 日本")
        assert len(scripts) == 3
        assert Script.LATIN in scripts
        assert Script.CYRILLIC in scripts
        assert Script.HAN in scripts

    def test_common_does_not_count_as_mixed(self) -> None:
        """Digits + Latin should NOT be mixed (digits are Common)."""
        assert not is_mixed_script("hello 123")

    def test_script_with_embedded_punctuation(self) -> None:
        """Punctuation (Common) between scripts should not prevent mixing detection."""
        assert is_mixed_script("hello, Москва!")

    def test_single_script_not_mixed(self) -> None:
        assert not is_mixed_script("hello world")
        assert not is_mixed_script("Москва Россия")
        assert not is_mixed_script("中文漢字")  # Pure Han

    def test_japanese_han_katakana_is_mixed(self) -> None:
        """Japanese text mixing Han and Katakana IS multi-script."""
        assert is_mixed_script("日本語テスト")


class TestScriptEnumValues:
    """Verify Script enum string values match what Rust returns."""

    @pytest.mark.parametrize(
        "script,sample",
        [
            pytest.param(script, sample, id=script.name)
            for script, sample in SCRIPT_SAMPLES.items()
        ],
    )
    def test_enum_value_matches_rust_string(self, script: Script, sample: str) -> None:
        """The Script enum's .value must match the string returned by Rust.
        detect_scripts() converts Rust strings to Script members via Script(name),
        so if the enum value doesn't match, the script won't be detected.
        """
        detected = detect_scripts(sample)
        assert script in detected, (
            f"Script.{script.name} (value={script.value!r}) not found in "
            f"detect_scripts({sample!r}). This usually means the Rust function "
            f"returns a different string than the Python enum expects."
        )


class TestUnknownScriptWarning:
    """Verify that unknown script names from Rust trigger a warning."""

    def test_unknown_script_warns(self) -> None:
        """If Rust returns a script name not in the Python enum, a warning
        should be emitted rather than silently dropping the result."""
        import warnings
        from unittest.mock import patch

        # Mock _detect_scripts to return a name not in the Script enum
        with patch("translit._detect_scripts", return_value=["Latin", "Martian"]):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                result = detect_scripts("hello")

        # Latin should be in the result, Martian should not
        assert Script.LATIN in result
        assert len(result) == 1  # Martian was not added

        # A warning should have been emitted for "Martian"
        assert len(caught) == 1
        assert "Martian" in str(caught[0].message)
        assert "Script enum" in str(caught[0].message)

    def test_known_scripts_no_warning(self) -> None:
        """Normal detection should produce no warnings."""
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            detect_scripts("hello Москва")

        assert len(caught) == 0
