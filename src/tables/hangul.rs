//! Algorithmic Hangul syllable → Revised Romanization of Korean.
//!
//! Korean Hangul syllables (U+AC00–U+D7AF) are algorithmically composed
//! from three jamo components:
//!   - Choseong (initial consonant): 19 values
//!   - Jungseong (medial vowel): 21 values
//!   - Jongseong (final consonant): 28 values (index 0 = no final)
//!
//! Decomposition formula (Unicode Standard, §3.12):
//!   syllable_index = code - 0xAC00
//!   choseong  = syllable_index / (21 * 28)
//!   jungseong = (syllable_index % (21 * 28)) / 28
//!   jongseong = syllable_index % 28
//!
//! Romanization follows the Revised Romanization of Korean (RR),
//! the official South Korean government standard (2000) and the most
//! widely used system internationally.
//!
//! Limitation: This is a context-free, syllable-by-syllable mapping.
//! Korean phonological rules (연음법칙, 경음화, 비음화, etc.) that change
//! pronunciation based on adjacent syllables are NOT applied.

const HANGUL_BASE: u32 = 0xAC00;
const HANGUL_END: u32 = 0xD7A3;
const JUNGSEONG_COUNT: u32 = 21;
const JONGSEONG_COUNT: u32 = 28;

/// Initial consonants (choseong) — Revised Romanization
static CHOSEONG: &[&str] = &[
    "g",  // ㄱ
    "kk", // ㄲ
    "n",  // ㄴ
    "d",  // ㄷ
    "tt", // ㄸ
    "r",  // ㄹ
    "m",  // ㅁ
    "b",  // ㅂ
    "pp", // ㅃ
    "s",  // ㅅ
    "ss", // ㅆ
    "",   // ㅇ (silent as initial)
    "j",  // ㅈ
    "jj", // ㅉ
    "ch", // ㅊ
    "k",  // ㅋ
    "t",  // ㅌ
    "p",  // ㅍ
    "h",  // ㅎ
];

/// Medial vowels (jungseong) — Revised Romanization
static JUNGSEONG: &[&str] = &[
    "a",   // ㅏ
    "ae",  // ㅐ
    "ya",  // ㅑ
    "yae", // ㅒ
    "eo",  // ㅓ
    "e",   // ㅔ
    "yeo", // ㅕ
    "ye",  // ㅖ
    "o",   // ㅗ
    "wa",  // ㅘ
    "wae", // ㅙ
    "oe",  // ㅚ
    "yo",  // ㅛ
    "u",   // ㅜ
    "wo",  // ㅝ
    "we",  // ㅞ
    "wi",  // ㅟ
    "yu",  // ㅠ
    "eu",  // ㅡ
    "ui",  // ㅢ
    "i",   // ㅣ
];

/// Final consonants (jongseong) — Revised Romanization
/// Index 0 is the empty final (no trailing consonant).
static JONGSEONG: &[&str] = &[
    "",   // (none)
    "g",  // ㄱ
    "kk", // ㄲ
    "gs", // ㄳ
    "n",  // ㄴ
    "nj", // ㄵ
    "nh", // ㄶ
    "d",  // ㄷ
    "l",  // ㄹ
    "lg", // ㄺ
    "lm", // ㄻ
    "lb", // ㄼ
    "ls", // ㄽ
    "lt", // ㄾ
    "lp", // ㄿ
    "lh", // ㅀ
    "m",  // ㅁ
    "b",  // ㅂ
    "bs", // ㅄ
    "s",  // ㅅ
    "ss", // ㅆ
    "ng", // ㅇ
    "j",  // ㅈ
    "ch", // ㅊ
    "k",  // ㅋ
    "t",  // ㅌ
    "p",  // ㅍ
    "h",  // ㅎ
];

/// Compatibility Jamo (U+3131–U+3163) — standalone consonants and vowels.
/// Used when jamo appear outside syllable blocks (e.g., in abbreviations).
///
/// Flat array indexed by `(ch as u32 - 0x3131)` for O(1) lookup.
/// Covers the contiguous range U+3131..=U+3163 (51 entries).
const COMPAT_JAMO_BASE: u32 = 0x3131;
const COMPAT_JAMO_END: u32 = 0x3163;
static COMPAT_JAMO: &[&str] = &[
    "g",   // ㄱ U+3131
    "kk",  // ㄲ U+3132
    "gs",  // ㄳ U+3133
    "n",   // ㄴ U+3134
    "nj",  // ㄵ U+3135
    "nh",  // ㄶ U+3136
    "d",   // ㄷ U+3137
    "tt",  // ㄸ U+3138
    "r",   // ㄹ U+3139
    "lg",  // ㄺ U+313A
    "lm",  // ㄻ U+313B
    "lb",  // ㄼ U+313C
    "ls",  // ㄽ U+313D
    "lt",  // ㄾ U+313E
    "lp",  // ㄿ U+313F
    "lh",  // ㅀ U+3140
    "m",   // ㅁ U+3141
    "b",   // ㅂ U+3142
    "pp",  // ㅃ U+3143
    "bs",  // ㅄ U+3144
    "s",   // ㅅ U+3145
    "ss",  // ㅆ U+3146
    "",    // ㅇ U+3147
    "j",   // ㅈ U+3148
    "jj",  // ㅉ U+3149
    "ch",  // ㅊ U+314A
    "k",   // ㅋ U+314B
    "t",   // ㅌ U+314C
    "p",   // ㅍ U+314D
    "h",   // ㅎ U+314E
    "a",   // ㅏ U+314F
    "ae",  // ㅐ U+3150
    "ya",  // ㅑ U+3151
    "yae", // ㅒ U+3152
    "eo",  // ㅓ U+3153
    "e",   // ㅔ U+3154
    "yeo", // ㅕ U+3155
    "ye",  // ㅖ U+3156
    "o",   // ㅗ U+3157
    "wa",  // ㅘ U+3158
    "wae", // ㅙ U+3159
    "oe",  // ㅚ U+315A
    "yo",  // ㅛ U+315B
    "u",   // ㅜ U+315C
    "wo",  // ㅝ U+315D
    "we",  // ㅞ U+315E
    "wi",  // ㅟ U+315F
    "yu",  // ㅠ U+3160
    "eu",  // ㅡ U+3161
    "ui",  // ㅢ U+3162
    "i",   // ㅣ U+3163
];

/// Look up a compatibility jamo character (U+3131–U+3163) directly.
///
/// Returns the Revised Romanization string as a `&'static str`, or `None`
/// if `ch` is not in the compat-jamo range.  Unlike `romanize_hangul`, this
/// function never allocates.  O(1) via flat array indexing.
pub fn lookup_compat_jamo(ch: char) -> Option<&'static str> {
    let cp = ch as u32;
    if (COMPAT_JAMO_BASE..=COMPAT_JAMO_END).contains(&cp) {
        Some(COMPAT_JAMO[(cp - COMPAT_JAMO_BASE) as usize])
    } else {
        None
    }
}

/// Romanize a single Hangul syllable or compatibility jamo character.
/// Returns None if the character is not in the Hangul range.
pub fn romanize_hangul(ch: char) -> Option<String> {
    let code = ch as u32;

    // Precomposed Hangul syllables (U+AC00–U+D7A3)
    if (HANGUL_BASE..=HANGUL_END).contains(&code) {
        let index = code - HANGUL_BASE;
        let cho = (index / (JUNGSEONG_COUNT * JONGSEONG_COUNT)) as usize;
        let jung = ((index % (JUNGSEONG_COUNT * JONGSEONG_COUNT)) / JONGSEONG_COUNT) as usize;
        let jong = (index % JONGSEONG_COUNT) as usize;

        let mut result = String::with_capacity(8);
        result.push_str(CHOSEONG[cho]);
        result.push_str(JUNGSEONG[jung]);
        result.push_str(JONGSEONG[jong]);
        return Some(result);
    }

    // Compatibility Jamo (U+3131–U+3163) — delegate to O(1) lookup
    lookup_compat_jamo(ch).map(std::string::ToString::to_string)
}

// Compile-time verification: Hangul algorithm constants match Unicode spec.
// JUNGSEONG_COUNT * JONGSEONG_COUNT = 21 * 28 = 588 (syllables per initial).
// Total syllables: 19 * 588 = 11,172 (U+AC00–U+D7A3).
const _: () = assert!(JUNGSEONG_COUNT == 21);
const _: () = assert!(JONGSEONG_COUNT == 28);
const _: () = assert!(HANGUL_END - HANGUL_BASE + 1 == 19 * JUNGSEONG_COUNT * JONGSEONG_COUNT);
const _: () = assert!(COMPAT_JAMO_END - COMPAT_JAMO_BASE + 1 == 51);

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_jamo_array_lengths() {
        assert_eq!(CHOSEONG.len(), 19, "CHOSEONG must have 19 initial consonants");
        assert_eq!(JUNGSEONG.len(), 21, "JUNGSEONG must have 21 medial vowels");
        assert_eq!(JONGSEONG.len(), 28, "JONGSEONG must have 28 final consonants");
        assert_eq!(COMPAT_JAMO.len(), 51, "COMPAT_JAMO must have 51 entries");
    }

    #[test]
    fn test_all_jamo_entries_are_ascii() {
        for (i, entry) in CHOSEONG.iter().enumerate() {
            assert!(entry.is_ascii(), "CHOSEONG[{i}] = {entry:?} is not ASCII");
        }
        for (i, entry) in JUNGSEONG.iter().enumerate() {
            assert!(entry.is_ascii(), "JUNGSEONG[{i}] = {entry:?} is not ASCII");
        }
        for (i, entry) in JONGSEONG.iter().enumerate() {
            assert!(entry.is_ascii(), "JONGSEONG[{i}] = {entry:?} is not ASCII");
        }
        for (i, entry) in COMPAT_JAMO.iter().enumerate() {
            assert!(entry.is_ascii(), "COMPAT_JAMO[{i}] = {entry:?} is not ASCII");
        }
    }

    #[test]
    fn test_hangul_basic() {
        // 한 = ㅎ(h) + ㅏ(a) + ㄴ(n) = "han"
        assert_eq!(romanize_hangul('한'), Some("han".to_string()));
        // 글 = ㄱ(g) + ㅡ(eu) + ㄹ(l) = "geul"
        assert_eq!(romanize_hangul('글'), Some("geul".to_string()));
    }

    #[test]
    fn test_hangul_no_final() {
        // 가 = ㄱ(g) + ㅏ(a) + (none) = "ga"
        assert_eq!(romanize_hangul('가'), Some("ga".to_string()));
    }

    #[test]
    fn test_hangul_seoul() {
        // 서 = ㅅ(s) + ㅓ(eo) = "seo"
        assert_eq!(romanize_hangul('서'), Some("seo".to_string()));
        // 울 = ㅇ() + ㅜ(u) + ㄹ(l) = "ul"
        assert_eq!(romanize_hangul('울'), Some("ul".to_string()));
    }

    #[test]
    fn test_non_hangul_returns_none() {
        assert_eq!(romanize_hangul('A'), None);
        assert_eq!(romanize_hangul('北'), None);
    }

    #[test]
    fn test_compat_jamo() {
        assert_eq!(romanize_hangul('ㄱ'), Some("g".to_string()));
        assert_eq!(romanize_hangul('ㅏ'), Some("a".to_string()));
    }
}
