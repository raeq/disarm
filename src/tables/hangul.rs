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
static COMPAT_JAMO: &[(char, &str)] = &[
    ('ㄱ', "g"),
    ('ㄲ', "kk"),
    ('ㄳ', "gs"),
    ('ㄴ', "n"),
    ('ㄵ', "nj"),
    ('ㄶ', "nh"),
    ('ㄷ', "d"),
    ('ㄸ', "tt"),
    ('ㄹ', "r"),
    ('ㄺ', "lg"),
    ('ㄻ', "lm"),
    ('ㄼ', "lb"),
    ('ㄽ', "ls"),
    ('ㄾ', "lt"),
    ('ㄿ', "lp"),
    ('ㅀ', "lh"),
    ('ㅁ', "m"),
    ('ㅂ', "b"),
    ('ㅃ', "pp"),
    ('ㅄ', "bs"),
    ('ㅅ', "s"),
    ('ㅆ', "ss"),
    ('ㅇ', ""),
    ('ㅈ', "j"),
    ('ㅉ', "jj"),
    ('ㅊ', "ch"),
    ('ㅋ', "k"),
    ('ㅌ', "t"),
    ('ㅍ', "p"),
    ('ㅎ', "h"),
    ('ㅏ', "a"),
    ('ㅐ', "ae"),
    ('ㅑ', "ya"),
    ('ㅒ', "yae"),
    ('ㅓ', "eo"),
    ('ㅔ', "e"),
    ('ㅕ', "yeo"),
    ('ㅖ', "ye"),
    ('ㅗ', "o"),
    ('ㅘ', "wa"),
    ('ㅙ', "wae"),
    ('ㅚ', "oe"),
    ('ㅛ', "yo"),
    ('ㅜ', "u"),
    ('ㅝ', "wo"),
    ('ㅞ', "we"),
    ('ㅟ', "wi"),
    ('ㅠ', "yu"),
    ('ㅡ', "eu"),
    ('ㅢ', "ui"),
    ('ㅣ', "i"),
];

/// Romanize a single Hangul syllable or compatibility jamo character.
/// Returns None if the character is not in the Hangul range.
pub fn romanize_hangul(ch: char) -> Option<String> {
    let code = ch as u32;

    // Precomposed Hangul syllables (U+AC00–U+D7A3)
    if code >= HANGUL_BASE && code <= HANGUL_END {
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

    // Compatibility Jamo (U+3131–U+3163)
    if ('\u{3131}'..='\u{3163}').contains(&ch) {
        for &(jamo, roman) in COMPAT_JAMO {
            if jamo == ch {
                return Some(roman.to_string());
            }
        }
    }

    None
}

#[cfg(test)]
mod tests {
    use super::*;

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
