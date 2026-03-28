//! Exhaustive domain tests for translit.
//!
//! These tests cover every element in bounded Unicode domains, leaving zero
//! untested inputs within each domain. This is stronger than property-based
//! testing because it eliminates sampling gaps.
//!
//! All tests are `#[ignore]` by default so they don't slow everyday development.
//! Run before release with: `cargo test --test exhaustive_transliterate -- --ignored`

use _translit::tables::hangul::{lookup_compat_jamo, romanize_hangul};
use _translit::transliterate::{
    balinese_char_role, indic_char_role, javanese_char_role, khmer_char_role, myanmar_char_role,
    sinhala_char_role, tibetan_char_role, transliterate_impl, IndicRole,
};
use _translit::ErrorMode;

// ── Hangul syllables (U+AC00–U+D7A3): all 11,172 ──────────────────────

#[test]
#[ignore]
fn exhaustive_hangul_syllables_return_some() {
    for cp in 0xAC00_u32..=0xD7A3 {
        let ch = char::from_u32(cp).unwrap();
        assert!(
            romanize_hangul(ch).is_some(),
            "romanize_hangul returned None for U+{cp:04X}"
        );
    }
}

#[test]
#[ignore]
fn exhaustive_hangul_syllables_ascii_output() {
    for cp in 0xAC00_u32..=0xD7A3 {
        let ch = char::from_u32(cp).unwrap();
        let result = romanize_hangul(ch).unwrap();
        assert!(
            result.is_ascii(),
            "romanize_hangul(U+{cp:04X}) = {result:?} is not ASCII"
        );
        assert!(
            !result.is_empty(),
            "romanize_hangul(U+{cp:04X}) returned empty string"
        );
    }
}

#[test]
#[ignore]
fn exhaustive_hangul_decomposition_indices_in_bounds() {
    for cp in 0xAC00_u32..=0xD7A3 {
        let index = cp - 0xAC00;
        let cho = index / (21 * 28);
        let jung = (index % (21 * 28)) / 28;
        let jong = index % 28;

        assert!(cho < 19, "U+{cp:04X}: cho={cho} >= 19");
        assert!(jung < 21, "U+{cp:04X}: jung={jung} >= 21");
        assert!(jong < 28, "U+{cp:04X}: jong={jong} >= 28");

        // Round-trip: verify the decomposition formula is invertible
        let reconstructed = cho * 21 * 28 + jung * 28 + jong;
        assert_eq!(
            reconstructed, index,
            "U+{cp:04X}: decomposition round-trip failed"
        );
    }
}

// ── Compatibility jamo (U+3131–U+3163): all 51 ────────────────────────

#[test]
#[ignore]
fn exhaustive_compat_jamo_return_some() {
    for cp in 0x3131_u32..=0x3163 {
        let ch = char::from_u32(cp).unwrap();
        assert!(
            lookup_compat_jamo(ch).is_some(),
            "lookup_compat_jamo returned None for U+{cp:04X}"
        );
    }
}

#[test]
#[ignore]
fn exhaustive_compat_jamo_ascii_output() {
    for cp in 0x3131_u32..=0x3163 {
        let ch = char::from_u32(cp).unwrap();
        let result = lookup_compat_jamo(ch).unwrap();
        assert!(
            result.is_ascii(),
            "lookup_compat_jamo(U+{cp:04X}) = {result:?} is not ASCII"
        );
    }
}

// ── Full BMP ASCII output (U+0080–U+FFFF): ErrorMode::Ignore ──────────

#[test]
#[ignore]
fn exhaustive_bmp_ignore_produces_ascii() {
    let mut failures = Vec::new();
    for cp in 0x0080_u32..=0xFFFF {
        // Skip surrogate range (not valid Unicode scalar values)
        if (0xD800..=0xDFFF).contains(&cp) {
            continue;
        }
        let ch = char::from_u32(cp).unwrap();
        let input = ch.to_string();
        let output = transliterate_impl(&input, None, ErrorMode::Ignore, "", false, false, false);
        if !output.is_ascii() {
            failures.push(format!("U+{cp:04X} → {output:?}"));
        }
    }
    assert!(
        failures.is_empty(),
        "ErrorMode::Ignore produced non-ASCII output for {} codepoints:\n{}",
        failures.len(),
        failures[..failures.len().min(20)].join("\n")
    );
}

// ── Full BMP idempotence (U+0080–U+FFFF) ──────────────────────────────

#[test]
#[ignore]
fn exhaustive_bmp_idempotence() {
    let mut failures = Vec::new();
    for cp in 0x0080_u32..=0xFFFF {
        if (0xD800..=0xDFFF).contains(&cp) {
            continue;
        }
        let ch = char::from_u32(cp).unwrap();
        let input = ch.to_string();
        let once = transliterate_impl(&input, None, ErrorMode::Ignore, "", false, false, false)
            .into_owned();
        let twice = transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false)
            .into_owned();
        if once != twice {
            failures.push(format!("U+{cp:04X}: once={once:?}, twice={twice:?}"));
        }
    }
    assert!(
        failures.is_empty(),
        "Idempotence violated for {} codepoints:\n{}",
        failures.len(),
        failures[..failures.len().min(20)].join("\n")
    );
}

// ── Indic block structure verification ─────────────────────────────────

/// Core Indic scripts: Devanagari, Bengali, Gurmukhi, Gujarati, Oriya,
/// Tamil, Telugu, Kannada, Malayalam.
#[test]
#[ignore]
fn exhaustive_core_indic_block_structure() {
    let blocks: &[(u32, &str)] = &[
        (0x0900, "Devanagari"),
        (0x0980, "Bengali"),
        (0x0A00, "Gurmukhi"),
        (0x0A80, "Gujarati"),
        (0x0B00, "Oriya"),
        (0x0B80, "Tamil"),
        (0x0C00, "Telugu"),
        (0x0C80, "Kannada"),
        (0x0D00, "Malayalam"),
    ];

    for &(base, name) in blocks {
        // Virama at offset 0x4D
        let virama_cp = base + 0x4D;
        assert_eq!(
            indic_char_role(virama_cp),
            IndicRole::Virama,
            "{name} virama (U+{virama_cp:04X}) not classified as Virama"
        );

        // Consonant range: offsets 0x15–0x39
        for offset in 0x15..=0x39 {
            let cp = base + offset;
            assert_eq!(
                indic_char_role(cp),
                IndicRole::Consonant,
                "{name} consonant (U+{cp:04X}, offset 0x{offset:02X}) not classified as Consonant"
            );
        }

        // Dependent vowel range: offsets 0x3E–0x4C
        for offset in 0x3E..=0x4C {
            let cp = base + offset;
            assert_eq!(
                indic_char_role(cp),
                IndicRole::DependentVowel,
                "{name} dependent vowel (U+{cp:04X}, offset 0x{offset:02X}) not classified as DependentVowel"
            );
        }
    }
}

#[test]
#[ignore]
fn exhaustive_sinhala_block_structure() {
    // Virama (al-lakuna)
    assert_eq!(sinhala_char_role(0x0DCA), IndicRole::Virama);

    // Consonants
    for cp in 0x0D9A..=0x0DC6 {
        assert_eq!(
            sinhala_char_role(cp),
            IndicRole::Consonant,
            "Sinhala U+{cp:04X} not classified as Consonant"
        );
    }

    // Dependent vowels
    for cp in 0x0DCF..=0x0DDF {
        assert_eq!(
            sinhala_char_role(cp),
            IndicRole::DependentVowel,
            "Sinhala U+{cp:04X} not classified as DependentVowel"
        );
    }
    for cp in 0x0DF2..=0x0DF3 {
        assert_eq!(
            sinhala_char_role(cp),
            IndicRole::DependentVowel,
            "Sinhala U+{cp:04X} not classified as DependentVowel"
        );
    }
}

#[test]
#[ignore]
fn exhaustive_tibetan_block_structure() {
    assert_eq!(tibetan_char_role(0x0F84), IndicRole::Virama);

    for cp in 0x0F40..=0x0F69 {
        assert_eq!(
            tibetan_char_role(cp),
            IndicRole::Consonant,
            "Tibetan U+{cp:04X} not classified as Consonant"
        );
    }
    for cp in 0x0F90..=0x0FBC {
        assert_eq!(
            tibetan_char_role(cp),
            IndicRole::Consonant,
            "Tibetan subjoined U+{cp:04X} not classified as Consonant"
        );
    }
    for cp in 0x0F71..=0x0F7D {
        assert_eq!(
            tibetan_char_role(cp),
            IndicRole::DependentVowel,
            "Tibetan U+{cp:04X} not classified as DependentVowel"
        );
    }
}

#[test]
#[ignore]
fn exhaustive_myanmar_block_structure() {
    assert_eq!(myanmar_char_role(0x1039), IndicRole::Virama);
    assert_eq!(myanmar_char_role(0x103A), IndicRole::Virama);

    for cp in 0x1000..=0x1021 {
        assert_eq!(
            myanmar_char_role(cp),
            IndicRole::Consonant,
            "Myanmar U+{cp:04X} not classified as Consonant"
        );
    }
    for cp in 0x102B..=0x1035 {
        assert_eq!(
            myanmar_char_role(cp),
            IndicRole::DependentVowel,
            "Myanmar U+{cp:04X} not classified as DependentVowel"
        );
    }
    for cp in 0x103B..=0x103E {
        assert_eq!(
            myanmar_char_role(cp),
            IndicRole::DependentVowel,
            "Myanmar U+{cp:04X} not classified as DependentVowel"
        );
    }
}

#[test]
#[ignore]
fn exhaustive_khmer_block_structure() {
    assert_eq!(khmer_char_role(0x17D2), IndicRole::Virama);

    for cp in 0x1780..=0x17A2 {
        assert_eq!(
            khmer_char_role(cp),
            IndicRole::Consonant,
            "Khmer U+{cp:04X} not classified as Consonant"
        );
    }
    for cp in 0x17B6..=0x17C5 {
        assert_eq!(
            khmer_char_role(cp),
            IndicRole::DependentVowel,
            "Khmer U+{cp:04X} not classified as DependentVowel"
        );
    }
}

#[test]
#[ignore]
fn exhaustive_balinese_block_structure() {
    assert_eq!(balinese_char_role(0x1B44), IndicRole::Virama);

    for cp in 0x1B13..=0x1B33 {
        assert_eq!(
            balinese_char_role(cp),
            IndicRole::Consonant,
            "Balinese U+{cp:04X} not classified as Consonant"
        );
    }
    for cp in 0x1B35..=0x1B43 {
        assert_eq!(
            balinese_char_role(cp),
            IndicRole::DependentVowel,
            "Balinese U+{cp:04X} not classified as DependentVowel"
        );
    }
}

#[test]
#[ignore]
fn exhaustive_javanese_block_structure() {
    assert_eq!(javanese_char_role(0xA9C0), IndicRole::Virama);

    for cp in 0xA990..=0xA9B2 {
        assert_eq!(
            javanese_char_role(cp),
            IndicRole::Consonant,
            "Javanese U+{cp:04X} not classified as Consonant"
        );
    }
    for cp in 0xA9B4..=0xA9BC {
        assert_eq!(
            javanese_char_role(cp),
            IndicRole::DependentVowel,
            "Javanese U+{cp:04X} not classified as DependentVowel"
        );
    }
}

// ── Determinism ────────────────────────────────────────────────────────

#[test]
#[ignore]
fn deterministic_100x_repeat() {
    let inputs = [
        "北京市 서울 Москва café ひらがな",
        "नमस्ते مرحبا שלום Αθήνα",
        "混合テスト αβγ δεζ",
        "U+FFFF edge: \u{FFFE}\u{FFFF}",
        "Ünïcödé Ärger straße",
        "カタカナ ひらがな 漢字",
        "대한민국 한글 テスト",
        "กรุงเทพ ลาว ថ្នាក់",
        "සිංහල མཁའ་འགྲོ ម៉ាស៊ីន",
        "ꦗꦮ ᬅᬓ᭄ᬱᬭ emoji: 🎉",
    ];

    for input in &inputs {
        let first = transliterate_impl(input, None, ErrorMode::Ignore, "", false, false, false)
            .into_owned();
        for run in 1..=100 {
            let result =
                transliterate_impl(input, None, ErrorMode::Ignore, "", false, false, false)
                    .into_owned();
            assert_eq!(
                first, result,
                "Determinism violated on run {run} for input {input:?}"
            );
        }
    }
}

// ── CJK Unified Ideographs (U+4E00–U+9FFF) ───────────────────────────

#[test]
#[ignore]
fn exhaustive_cjk_ideographs_ascii_output() {
    let mut non_ascii = Vec::new();
    let mut unmapped = 0_u32;
    for cp in 0x4E00_u32..=0x9FFF {
        let ch = char::from_u32(cp).unwrap();
        let input = ch.to_string();
        let output = transliterate_impl(&input, None, ErrorMode::Ignore, "", false, false, false);
        if !output.is_ascii() {
            non_ascii.push(format!("U+{cp:04X} → {output:?}"));
        }
        if output.is_empty() {
            unmapped += 1;
        }
    }
    // Some CJK ideographs lack kMandarin readings in Unihan — ErrorMode::Ignore
    // correctly produces empty output for these. We allow a small number of gaps
    // but flag any non-ASCII output as a data integrity error.
    assert!(
        non_ascii.is_empty(),
        "CJK ideographs produced non-ASCII output ({}):\n{}",
        non_ascii.len(),
        non_ascii[..non_ascii.len().min(20)].join("\n")
    );
    // Expect at most ~1% unmapped (currently ~68 out of 20,992)
    assert!(
        unmapped < 200,
        "Too many unmapped CJK ideographs: {unmapped}"
    );
}
