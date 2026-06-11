//! Integration tests for the transliteration public API — Brahmic / Indic script family.
//!
//! Covers Devanagari, Bengali, Tamil (and the other Indic blocks), Sinhala, Thai,
//! Lao, Myanmar, Khmer, Tibetan, and Ethiopic / Amharic.

mod common;

use _disarm::transliterate;
use _disarm::ErrorMode;
use common::*;
use proptest::prelude::*;

#[test]
fn devanagari_bare_consonant() {
    let result =
        transliterate::transliterate_impl("क", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "ka");
}

#[test]
fn devanagari_virama() {
    let result =
        transliterate::transliterate_impl("क्", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "k");
}

#[test]
fn devanagari_matra() {
    let result =
        transliterate::transliterate_impl("की", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "ki");
}

#[test]
fn devanagari_namaste() {
    let result =
        transliterate::transliterate_impl("नमस्ते", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "namaste");
}

#[test]
fn bengali_basic() {
    let result =
        transliterate::transliterate_impl("কলকাতা", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "kalakata");
}

#[test]
fn tamil_basic() {
    let result =
        transliterate::transliterate_impl("தமிழ்", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "tamizh");
}

#[test]
fn indic_digits() {
    let result =
        transliterate::transliterate_impl("१२३", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "123");
}

#[test]
fn indic_mixed_with_latin() {
    let result = transliterate::transliterate_impl(
        "Hello नमस्ते",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "Hello namaste");
}

#[test]
fn indic_all_scripts_produce_ascii() {
    let samples = [
        "नमस्ते",   // Devanagari
        "কলকাতা",   // Bengali
        "தமிழ்",   // Tamil
        "తెలుగు",  // Telugu
        "ગુજરાતી", // Gujarati
        "ಕನ್ನಡ",   // Kannada
        "മലയാളം",  // Malayalam
        "ଓଡ଼ିଆ",    // Odia
        "ਗੁਰਮੁਖੀ",  // Gurmukhi
    ];
    for sample in &samples {
        let result = transliterate::transliterate_impl(
            sample,
            None,
            ErrorMode::Ignore,
            "",
            false,
            false,
            false,
        );
        assert!(
            result.is_ascii(),
            "Expected ASCII for {sample:?}, got: {result:?}"
        );
        assert!(!result.is_empty(), "Expected non-empty for {sample:?}");
    }
}

#[test]
fn devanagari_dilli() {
    let result = transliterate::transliterate_impl(
        "दिल्ली",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "dilli");
}

#[test]
fn devanagari_mumbai() {
    let result =
        transliterate::transliterate_impl("मुम्बई", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "mumbai");
}

#[test]
fn devanagari_consecutive_consonants() {
    let result =
        transliterate::transliterate_impl("कल", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "kala");
}

#[test]
fn devanagari_independent_vowels() {
    let result =
        transliterate::transliterate_impl("अइउ", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "aiu");
}

#[test]
fn devanagari_multiword() {
    let result = transliterate::transliterate_impl(
        "नमस्ते दुनिया",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "namaste duniya");
}

// --- Sinhala ---

#[test]
fn sinhala_bare_consonant() {
    let result = transliterate::transliterate_impl(
        "\u{0D9A}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "ka");
}

#[test]
fn sinhala_virama() {
    let result = transliterate::transliterate_impl(
        "\u{0D9A}\u{0DCA}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "k");
}

#[test]
fn sinhala_matra() {
    let result = transliterate::transliterate_impl(
        "\u{0D9A}\u{0DD2}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "ki");
}

#[test]
fn sinhala_word() {
    let result =
        transliterate::transliterate_impl("සිංහල", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "simhala");
}

#[test]
fn sinhala_digits() {
    let result =
        transliterate::transliterate_impl("෧෨෩", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "123");
}

#[test]
fn sinhala_produces_ascii() {
    let samples = ["සිංහල", "ලංකා", "කොළඹ"];
    for sample in &samples {
        let result = transliterate::transliterate_impl(
            sample,
            None,
            ErrorMode::Ignore,
            "",
            false,
            false,
            false,
        );
        assert!(
            result.is_ascii(),
            "Expected ASCII for {sample:?}, got: {result:?}"
        );
        assert!(!result.is_empty(), "Expected non-empty for {sample:?}");
    }
}

// ===========================================================================
// Thai example tests
// ===========================================================================

#[test]
fn thai_consonants() {
    let result = transliterate::transliterate_impl(
        "\u{0E01}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "k");
}

#[test]
fn thai_bangkok() {
    let result = transliterate::transliterate_impl(
        "\u{0E01}\u{0E23}\u{0E38}\u{0E07}\u{0E40}\u{0E17}\u{0E1E}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert!(result.is_ascii(), "Expected ASCII, got: {result:?}");
    assert!(result.contains('k'), "Expected 'k' in result: {result:?}");
}

#[test]
fn thai_tone_marks_dropped() {
    // น้ำ = น(n) + ้(tone mark) + ำ(am) → "nam"
    let result = transliterate::transliterate_impl(
        "\u{0E19}\u{0E49}\u{0E33}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "nam");
}

#[test]
fn thai_digits() {
    let result = transliterate::transliterate_impl(
        "\u{0E50}\u{0E51}\u{0E52}\u{0E53}\u{0E54}\u{0E55}\u{0E56}\u{0E57}\u{0E58}\u{0E59}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "0123456789");
}

#[test]
fn thai_produces_ascii() {
    let samples = [
        "\u{0E01}\u{0E23}\u{0E38}\u{0E07}\u{0E40}\u{0E17}\u{0E1E}",
        "\u{0E1B}\u{0E23}\u{0E30}\u{0E40}\u{0E17}\u{0E28}\u{0E44}\u{0E17}\u{0E22}",
        "\u{0E20}\u{0E32}\u{0E29}\u{0E32}\u{0E44}\u{0E17}\u{0E22}",
    ];
    for sample in &samples {
        let result = transliterate::transliterate_impl(
            sample,
            None,
            ErrorMode::Ignore,
            "",
            false,
            false,
            false,
        );
        assert!(
            result.is_ascii(),
            "Expected ASCII for {sample:?}, got: {result:?}"
        );
        assert!(!result.is_empty(), "Expected non-empty for {sample:?}");
    }
}

// ===========================================================================
// Lao example tests
// ===========================================================================

#[test]
fn lao_word_lao() {
    let result = transliterate::transliterate_impl(
        "\u{0EA5}\u{0EB2}\u{0EA7}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "law");
}

#[test]
fn lao_consonants() {
    let result = transliterate::transliterate_impl(
        "\u{0E81}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "k");
}

#[test]
fn lao_digits() {
    let result = transliterate::transliterate_impl(
        "\u{0ED0}\u{0ED1}\u{0ED2}\u{0ED3}\u{0ED4}\u{0ED5}\u{0ED6}\u{0ED7}\u{0ED8}\u{0ED9}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "0123456789");
}

#[test]
fn lao_composite_consonants() {
    assert_eq!(
        transliterate::transliterate_impl(
            "\u{0EDC}",
            None,
            ErrorMode::Ignore,
            "",
            false,
            false,
            false,
        ),
        "hn"
    );
    assert_eq!(
        transliterate::transliterate_impl(
            "\u{0EDD}",
            None,
            ErrorMode::Ignore,
            "",
            false,
            false,
            false,
        ),
        "hm"
    );
}

#[test]
fn lao_produces_ascii() {
    let samples = [
        "\u{0EA5}\u{0EB2}\u{0EA7}",
        "\u{0EA7}\u{0EBD}\u{0E87}\u{0E88}\u{0EB1}\u{0E99}",
    ];
    for sample in &samples {
        let result = transliterate::transliterate_impl(
            sample,
            None,
            ErrorMode::Ignore,
            "",
            false,
            false,
            false,
        );
        assert!(
            result.is_ascii(),
            "Expected ASCII for {sample:?}, got: {result:?}"
        );
        assert!(!result.is_empty(), "Expected non-empty for {sample:?}");
    }
}

// ===========================================================================
// Property-based tests (proptest)
// ===========================================================================

// --- Indic property tests ---

proptest! {
    #![proptest_config(ProptestConfig::with_cases(500))]

    #[test]
    fn prop_devanagari_produces_ascii(s in devanagari_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Devanagari: {:?}", result);
    }

    #[test]
    fn prop_bengali_produces_ascii(s in bengali_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Bengali: {:?}", result);
    }

    #[test]
    fn prop_tamil_produces_ascii(s in tamil_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Tamil: {:?}", result);
    }

    #[test]
    fn prop_any_indic_produces_ascii(s in any_indic_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Indic: {:?}", result);
    }

    #[test]
    fn prop_indic_idempotent(s in any_indic_text()) {
        let once = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&once, &twice);
    }

    #[test]
    fn prop_indic_no_double_spaces(s in any_indic_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(!result.contains("  "), "Double space in: {:?}", result);
    }

    #[test]
    fn prop_devanagari_consonants_end_with_a(s in devanagari_consonants()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        if !result.is_empty() {
            prop_assert!(result.ends_with('a'), "Bare consonants should end with 'a': {:?}", result);
        }
    }
}

// --- Sinhala property tests ---

proptest! {
    #![proptest_config(ProptestConfig::with_cases(500))]

    #[test]
    fn prop_sinhala_produces_ascii(s in sinhala_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Sinhala: {:?}", result);
    }

    #[test]
    fn prop_sinhala_idempotent(s in sinhala_text()) {
        let once = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&once, &twice);
    }
}

// --- Thai property tests ---

proptest! {
    #![proptest_config(ProptestConfig::with_cases(500))]

    #[test]
    fn prop_thai_produces_ascii(s in thai_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Thai: {:?}", result);
    }

    #[test]
    fn prop_thai_idempotent(s in thai_text()) {
        let once = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&once, &twice);
    }

    #[test]
    fn prop_thai_consonants_nonempty(s in thai_consonants_strat()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(!result.is_empty(), "Empty result from Thai consonants: {:?}", s);
    }

    #[test]
    fn prop_thai_no_double_spaces(s in thai_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(!result.contains("  "), "Double space in: {:?}", result);
    }

    #[test]
    fn prop_thai_digits_are_arabic(s in thai_digits_strat()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.chars().all(|c| c.is_ascii_digit()), "Non-digit from Thai digits: {:?}", result);
        prop_assert_eq!(result.len(), s.chars().count());
    }
}

// --- Lao property tests ---

proptest! {
    #![proptest_config(ProptestConfig::with_cases(500))]

    #[test]
    fn prop_lao_produces_ascii(s in lao_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Lao: {:?}", result);
    }

    #[test]
    fn prop_lao_idempotent(s in lao_text()) {
        let once = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&once, &twice);
    }

    #[test]
    fn prop_lao_no_double_spaces(s in lao_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(!result.contains("  "), "Double space in: {:?}", result);
    }
}

// ── Ethiopic tests ──────────────────────────────────────────────────────────

#[test]
fn ethiopic_syllable_orders() {
    let r = |s| {
        transliterate::transliterate_impl(s, None, ErrorMode::Ignore, "", false, false, false)
            .into_owned()
    };
    assert_eq!(r("ሀ"), "he"); // order 1
    assert_eq!(r("ሁ"), "hu"); // order 2
    assert_eq!(r("ሂ"), "hi"); // order 3
    assert_eq!(r("ሃ"), "ha"); // order 4
    assert_eq!(r("ህ"), "h"); // order 6 (bare)
    assert_eq!(r("ሆ"), "ho"); // order 7
}

#[test]
fn ethiopic_ethiopia() {
    let result = transliterate::transliterate_impl(
        "ኢትዮጵያ",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(&*result, "ityopya");
}

#[test]
fn ethiopic_digits() {
    let result =
        transliterate::transliterate_impl("፩፪፫", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "123");
}

#[test]
fn ethiopic_produces_ascii() {
    let result = transliterate::transliterate_impl(
        "ኢትዮጵያ",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert!(result.is_ascii());
}

// ── Amharic language override tests ─────────────────────────────────────────

#[test]
fn amharic_tsade_override() {
    // ጸ (U+1338) → "se" with am lang (not "tse" from default)
    let result = transliterate::transliterate_impl(
        "ጸ",
        Some("am"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(&*result, "se");
}

#[test]
fn amharic_tsade_alt_override() {
    // ፀ (U+1340) → "se" with am lang (ጸ/ፀ merger)
    let result = transliterate::transliterate_impl(
        "ፀ",
        Some("am"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(&*result, "se");
}

#[test]
fn amharic_pharyngeal_override() {
    // ዐ (U+12D0) → "'e" with am lang (pharyngeal marking)
    let result = transliterate::transliterate_impl(
        "ዐ",
        Some("am"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(&*result, "'e");
}

#[test]
fn amharic_sun_word() {
    // ጸሐይ (tsehay/sehay = "sun") — tests ጸ override in context
    let result = transliterate::transliterate_impl(
        "ጸሐይ",
        Some("am"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(&*result, "sehhey");
}

#[test]
fn amharic_default_unchanged() {
    // Without am lang, ጸ still maps to default "tse"
    let result =
        transliterate::transliterate_impl("ጸ", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "tse");
}

// ── Myanmar tests ───────────────────────────────────────────────────────────

#[test]
fn myanmar_consonant() {
    let result =
        transliterate::transliterate_impl("က", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "ka");
}

#[test]
fn myanmar_virama_strips_a() {
    let result =
        transliterate::transliterate_impl("န်", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "n");
}

#[test]
fn myanmar_dependent_vowel() {
    let result =
        transliterate::transliterate_impl("ကိ", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "ki");
}

#[test]
fn myanmar_digits() {
    let result =
        transliterate::transliterate_impl("၀၁၉", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "019");
}

#[test]
fn myanmar_produces_ascii() {
    let result = transliterate::transliterate_impl(
        "မြန်မာ",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert!(result.is_ascii());
}

// ── Khmer tests ─────────────────────────────────────────────────────────────

#[test]
fn khmer_consonant() {
    let result =
        transliterate::transliterate_impl("ក", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "ka");
}

#[test]
fn khmer_cambodia() {
    let result =
        transliterate::transliterate_impl("កម្ពុជា", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "kampucha");
}

#[test]
fn khmer_coeng_stacks() {
    let result =
        transliterate::transliterate_impl("ក្រ", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "kra");
}

#[test]
fn khmer_digits() {
    let result =
        transliterate::transliterate_impl("០១៩", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "019");
}

#[test]
fn khmer_produces_ascii() {
    let result =
        transliterate::transliterate_impl("កម្ពុជា", None, ErrorMode::Ignore, "", false, false, false);
    assert!(result.is_ascii());
}

// ── Tibetan tests ───────────────────────────────────────────────────────────

#[test]
fn tibetan_consonant() {
    let result =
        transliterate::transliterate_impl("ཀ", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "ka");
}

#[test]
fn tibetan_vowel_sign() {
    let result =
        transliterate::transliterate_impl("ཀི", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "ki");
}

#[test]
fn tibetan_om() {
    let result =
        transliterate::transliterate_impl("ༀ", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "om");
}

#[test]
fn tibetan_digits() {
    let result =
        transliterate::transliterate_impl("༠༡༩", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "019");
}

#[test]
fn tibetan_produces_ascii() {
    let result =
        transliterate::transliterate_impl("བོད", None, ErrorMode::Ignore, "", false, false, false);
    assert!(result.is_ascii());
}

// ── Property tests for new scripts ──────────────────────────────────────────

proptest! {
    #![proptest_config(ProptestConfig::with_cases(300))]

    // Ethiopic
    #[test]
    fn prop_ethiopic_produces_ascii(text in ethiopic_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Ethiopic: {:?}", result);
    }

    #[test]
    fn prop_ethiopic_idempotent(text in ethiopic_text()) {
        let once = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    // Myanmar
    #[test]
    fn prop_myanmar_produces_ascii(text in myanmar_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Myanmar: {:?}", result);
    }

    #[test]
    fn prop_myanmar_idempotent(text in myanmar_text()) {
        let once = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    // Khmer
    #[test]
    fn prop_khmer_produces_ascii(text in khmer_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Khmer: {:?}", result);
    }

    #[test]
    fn prop_khmer_idempotent(text in khmer_text()) {
        let once = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    // Tibetan
    #[test]
    fn prop_tibetan_produces_ascii(text in tibetan_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Tibetan: {:?}", result);
    }

    #[test]
    fn prop_tibetan_idempotent(text in tibetan_text()) {
        let once = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }
}

// ── lang="auto" deterministic tests ────────────────────────────────────────

#[test]
fn auto_lang_thai_matches_explicit_th() {
    let text = "ภาษาไทย";
    let auto = transliterate::transliterate_impl(
        text,
        Some("auto"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    let explicit = transliterate::transliterate_impl(
        text,
        Some("th"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(auto, explicit);
}
