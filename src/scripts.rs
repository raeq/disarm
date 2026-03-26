use pyo3::prelude::*;

/// Detect Unicode scripts present in text, in order of first appearance.
///
/// Returns `&'static str` script names, avoiding per-character String
/// allocation.  The `HashSet` and output `Vec` use borrowed static strings.
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _detect_scripts(text: &str) -> Vec<&'static str> {
    let mut scripts: Vec<&'static str> = Vec::new();
    let mut seen = std::collections::HashSet::new();

    for ch in text.chars() {
        let script = detect_char_script(ch);
        if script != "Common" && script != "Inherited" && seen.insert(script) {
            scripts.push(script);
        }
    }

    scripts
}

/// True if text contains characters from more than one script (excluding Common/Inherited).
///
/// Short-circuits after finding the second distinct script, avoiding
/// scanning the rest of the string.
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _is_mixed_script(text: &str) -> bool {
    let mut first_script: Option<&'static str> = None;
    for ch in text.chars() {
        let script = detect_char_script(ch);
        if script == "Common" || script == "Inherited" {
            continue;
        }
        match first_script {
            None => first_script = Some(script),
            Some(s) if s != script => return true,
            _ => {}
        }
    }
    false
}

/// Sorted table of (range_start, range_end_inclusive, script_name) for binary search.
/// Sorted by range_start. All ranges are non-overlapping.
static SCRIPT_RANGES: &[(u32, u32, &str)] = &[
    // Latin
    (0x0041, 0x005A, "Latin"),
    (0x0061, 0x007A, "Latin"),
    (0x00C0, 0x024F, "Latin"),
    (0x0250, 0x02AF, "Latin"), // IPA Extensions
    // Inherited — Combining Diacritical Marks
    (0x0300, 0x036F, "Inherited"),
    // Greek
    (0x0370, 0x03FF, "Greek"),
    // Cyrillic
    (0x0400, 0x04FF, "Cyrillic"),
    (0x0500, 0x052F, "Cyrillic"), // Cyrillic Supplement
    // Armenian
    (0x0530, 0x058F, "Armenian"),
    // Hebrew
    (0x0590, 0x05FF, "Hebrew"),
    // Arabic
    (0x0600, 0x06FF, "Arabic"),
    // Syriac
    (0x0700, 0x074F, "Syriac"),
    // Arabic Supplement
    (0x0750, 0x077F, "Arabic"),
    // Thaana
    (0x0780, 0x07BF, "Thaana"),
    // NKo
    (0x07C0, 0x07FF, "NKo"),
    // Syriac Supplement
    (0x0860, 0x086F, "Syriac"),
    // Arabic Extended-A
    (0x08A0, 0x08FF, "Arabic"),
    // Devanagari
    (0x0900, 0x097F, "Devanagari"),
    // Bengali
    (0x0980, 0x09FF, "Bengali"),
    // Gurmukhi
    (0x0A00, 0x0A7F, "Gurmukhi"),
    // Gujarati
    (0x0A80, 0x0AFF, "Gujarati"),
    // Oriya
    (0x0B00, 0x0B7F, "Oriya"),
    // Tamil
    (0x0B80, 0x0BFF, "Tamil"),
    // Telugu
    (0x0C00, 0x0C7F, "Telugu"),
    // Kannada
    (0x0C80, 0x0CFF, "Kannada"),
    // Malayalam
    (0x0D00, 0x0D7F, "Malayalam"),
    // Sinhala
    (0x0D80, 0x0DFF, "Sinhala"),
    // Thai
    (0x0E00, 0x0E7F, "Thai"),
    // Lao
    (0x0E80, 0x0EFF, "Lao"),
    // Tibetan
    (0x0F00, 0x0FFF, "Tibetan"),
    // Myanmar
    (0x1000, 0x109F, "Myanmar"),
    // Georgian
    (0x10A0, 0x10FF, "Georgian"),
    // Hangul Jamo
    (0x1100, 0x11FF, "Hangul"),
    // Ethiopic
    (0x1200, 0x137F, "Ethiopic"),
    (0x1380, 0x139F, "Ethiopic"), // Ethiopic Supplement
    // Cherokee
    (0x13A0, 0x13FF, "Cherokee"),
    // Canadian Aboriginal Syllabics
    (0x1400, 0x167F, "CanadianAboriginal"),
    // Ogham
    (0x1680, 0x169F, "Ogham"),
    // Runic
    (0x16A0, 0x16FF, "Runic"),
    // Khmer
    (0x1780, 0x17FF, "Khmer"),
    // Mongolian
    (0x1800, 0x18AF, "Mongolian"),
    // Canadian Aboriginal Syllabics Extended
    (0x18B0, 0x18FF, "CanadianAboriginal"),
    // Tai Le
    (0x1950, 0x197F, "TaiLe"),
    // New Tai Lue
    (0x1980, 0x19DF, "NewTaiLue"),
    // Khmer Symbols
    (0x19E0, 0x19FF, "Khmer"),
    // Inherited — Combining Diacritical Marks Extended
    (0x1AB0, 0x1AFF, "Inherited"),
    // Balinese
    (0x1B00, 0x1B7F, "Balinese"),
    // Georgian Extended
    (0x1C90, 0x1CBF, "Georgian"),
    // Latin — Phonetic Extensions
    (0x1D00, 0x1D7F, "Latin"),
    // Latin — Phonetic Extensions Supplement
    (0x1D80, 0x1DBF, "Latin"),
    // Inherited — Combining Diacritical Marks Supplement
    (0x1DC0, 0x1DFF, "Inherited"),
    // Latin Extended Additional
    (0x1E00, 0x1EFF, "Latin"),
    // Greek Extended
    (0x1F00, 0x1FFF, "Greek"),
    // Inherited — Combining Diacritical Marks for Symbols
    (0x20D0, 0x20FF, "Inherited"),
    // Latin Extended-C
    (0x2C60, 0x2C7F, "Latin"),
    // Coptic
    (0x2C80, 0x2CFF, "Coptic"),
    // Georgian Supplement
    (0x2D00, 0x2D2F, "Georgian"),
    // Ethiopic Extended
    (0x2D80, 0x2DDF, "Ethiopic"),
    // Cyrillic Extended-A
    (0x2DE0, 0x2DFF, "Cyrillic"),
    // CJK Radicals Supplement
    (0x2E80, 0x2EFF, "Han"),
    // Kangxi Radicals
    (0x2F00, 0x2FDF, "Han"),
    // Hiragana
    (0x3040, 0x309F, "Hiragana"),
    // Katakana
    (0x30A0, 0x30FF, "Katakana"),
    // Hangul Compatibility Jamo
    (0x3130, 0x318F, "Hangul"),
    // Katakana Phonetic Extensions
    (0x31F0, 0x31FF, "Katakana"),
    // CJK Unified Ext A
    (0x3400, 0x4DBF, "Han"),
    // CJK Unified
    (0x4E00, 0x9FFF, "Han"),
    // Vai
    (0xA500, 0xA63F, "Vai"),
    // Cyrillic Extended-B
    (0xA640, 0xA69F, "Cyrillic"),
    // Latin Extended-D
    (0xA720, 0xA7FF, "Latin"),
    // Devanagari Extended
    (0xA8E0, 0xA8FF, "Devanagari"),
    // Hangul Jamo Extended-A
    (0xA960, 0xA97F, "Hangul"),
    // Javanese
    (0xA980, 0xA9DF, "Javanese"),
    // Myanmar Extended-A
    (0xAA60, 0xAA7F, "Myanmar"),
    // Ethiopic Extended-A
    (0xAB00, 0xAB2F, "Ethiopic"),
    // Latin Extended-E
    (0xAB30, 0xAB6F, "Latin"),
    // Cherokee Supplement
    (0xAB70, 0xABBF, "Cherokee"),
    // Hangul Syllables
    (0xAC00, 0xD7AF, "Hangul"),
    // Hangul Jamo Extended-B
    (0xD7B0, 0xD7FF, "Hangul"),
    // CJK Compatibility Ideographs
    (0xF900, 0xFAFF, "Han"),
    // Latin ligatures in Alphabetic PF
    (0xFB00, 0xFB06, "Latin"),
    // Armenian ligatures in Alphabetic PF
    (0xFB13, 0xFB17, "Armenian"),
    // Hebrew presentation forms
    (0xFB1D, 0xFB4F, "Hebrew"),
    // Arabic Presentation Forms-A
    (0xFB50, 0xFDFF, "Arabic"),
    // Inherited — Combining Half Marks
    (0xFE20, 0xFE2F, "Inherited"),
    // Arabic Presentation Forms-B
    (0xFE70, 0xFEFF, "Arabic"),
    // Halfwidth Katakana
    (0xFF65, 0xFF9F, "Katakana"),
    // CJK Unified Ext B
    (0x20000, 0x2A6DF, "Han"),
    // CJK Unified Ext C
    (0x2A700, 0x2B73F, "Han"),
    // CJK Unified Ext D
    (0x2B740, 0x2B81F, "Han"),
    // CJK Unified Ext E
    (0x2B820, 0x2CEAF, "Han"),
    // CJK Unified Ext F
    (0x2CEB0, 0x2EBEF, "Han"),
    // CJK Unified Ext G
    (0x30000, 0x3134F, "Han"),
];

/// Detect the Unicode script for a single character.
///
/// Uses binary search over sorted, non-overlapping Unicode Script ranges
/// (UAX #24).  O(log n) where n = number of ranges (~100), vs the previous
/// linear chain which was O(n) worst-case.
fn detect_char_script(ch: char) -> &'static str {
    let cp = ch as u32;

    // Fast path for ASCII (very common).
    if ch.is_ascii() {
        if (0x0041..=0x005A).contains(&cp) || (0x0061..=0x007A).contains(&cp) {
            return "Latin";
        }
        // Digits, punctuation, whitespace, and control chars are all Common.
        return "Common";
    }

    // Binary search: find the rightmost range whose start <= cp
    match SCRIPT_RANGES.binary_search_by(|&(start, _, _)| start.cmp(&cp)) {
        // Exact match on a range start
        Ok(idx) => SCRIPT_RANGES[idx].2,
        // cp would be inserted at `idx`; check if it falls within the range before it
        Err(0) => {
            // cp is below all ranges
            "Common"
        }
        Err(idx) => {
            let &(_, end, script) = &SCRIPT_RANGES[idx - 1];
            if cp <= end {
                script
            } else {
                "Common"
            }
        }
    }
}

/// Map a detected script name to a default ISO 639-1 language code.
///
/// For scripts that serve a single language (Thai, Georgian, etc.) the mapping
/// is unambiguous.  For multi-language scripts (Cyrillic → Russian, Han → Chinese)
/// a reasonable default is chosen.  Scripts with no useful language-specific
/// transliteration table (Latin, Runic, Ogham, …) return `None`.
fn script_to_lang(script: &str) -> Option<&'static str> {
    match script {
        "Thai" => Some("th"),
        "Lao" => Some("lo"),
        "Myanmar" => Some("my"),
        "Khmer" => Some("km"),
        "Georgian" => Some("ka"),
        "Armenian" => Some("hy"),
        "Tibetan" => Some("bo"),
        "Ethiopic" => Some("am"),
        "Bengali" => Some("bn"),
        "Tamil" => Some("ta"),
        "Telugu" => Some("te"),
        "Kannada" => Some("kn"),
        "Malayalam" => Some("ml"),
        "Gujarati" => Some("gu"),
        "Gurmukhi" => Some("pa"),
        "Oriya" => Some("or"),
        "Sinhala" => Some("si"),
        "Hangul" => Some("ko"),
        "Hebrew" => Some("he"),
        "Arabic" => Some("ar"),
        "Thaana" => Some("dv"),
        "Javanese" => Some("jv"),
        "Mongolian" => Some("mn"),
        "Devanagari" => Some("hi"),
        "Cyrillic" => Some("ru"),
        "Han" => Some("zh"),
        "Hiragana" | "Katakana" => Some("ja"),
        "Greek" => Some("el"),
        _ => None,
    }
}

/// True if the script is shared by multiple languages with different
/// transliteration profiles.  Only these scripts trigger discriminator
/// scanning — all other scripts have a 1:1 script→language mapping.
fn is_ambiguous_script(script: &str) -> bool {
    matches!(script, "Cyrillic" | "Arabic")
}

/// Look up whether a character is an exclusive discriminator for a
/// language within the given script.
///
/// Returns `Some(lang_code)` if the character appears exclusively in
/// one language's alphabet among the profiles we support for that
/// script.  Returns `None` for characters shared across languages.
///
/// **Fail-safe property:** only characters with zero ambiguity are
/// included.  False positives are impossible by construction — every
/// entry has been verified against all supported profiles for the
/// script.
fn lookup_discriminator(ch: char, script: &str) -> Option<&'static str> {
    match script {
        "Cyrillic" => match ch {
            // Ukrainian exclusive: ґ Ґ ї Ї є Є і І
            '\u{0491}' | '\u{0490}' | '\u{0457}' | '\u{0407}'
            | '\u{0454}' | '\u{0404}' | '\u{0456}' | '\u{0406}' => Some("uk"),
            // Serbian exclusive: ђ Ђ ћ Ћ љ Љ њ Њ џ Џ ј Ј
            '\u{0452}' | '\u{0402}' | '\u{045B}' | '\u{040B}'
            | '\u{0459}' | '\u{0409}' | '\u{045A}' | '\u{040A}'
            | '\u{045F}' | '\u{040F}' | '\u{0458}' | '\u{0408}' => Some("sr"),
            // Mongolian Cyrillic exclusive: ө Ө ү Ү
            '\u{04E9}' | '\u{04E8}' | '\u{04AF}' | '\u{04AE}' => Some("mn"),
            _ => None,
        },
        "Arabic" => match ch {
            // Persian exclusive: پ چ ژ گ
            '\u{067E}' | '\u{0686}' | '\u{0698}' | '\u{06AF}' => Some("fa"),
            _ => None,
        },
        _ => None,
    }
}

/// Look up whether a Latin-script character is an exclusive discriminator
/// for a language.
///
/// Separated from `lookup_discriminator` because Latin is handled via a
/// different code path (Latin text has no "primary script" in the
/// existing detection flow).
fn lookup_latin_discriminator(ch: char) -> Option<&'static str> {
    match ch {
        // Vietnamese exclusive: ơ Ơ ư Ư
        '\u{01A1}' | '\u{01A0}' | '\u{01B0}' | '\u{01AF}' => Some("vi"),
        // Turkish exclusive: İ (dotted capital I), ı (dotless small i)
        '\u{0130}' | '\u{0131}' => Some("tr"),
        // German exclusive: ß (eszett) and ẞ (capital eszett, rare but unambiguous)
        '\u{00DF}' | '\u{1E9E}' => Some("de"),
        _ => None,
    }
}

/// Scan text for discriminator characters exclusive to a particular language.
///
/// Returns `Some(lang)` only if **exactly one** language's discriminators
/// are found.  Returns `None` if:
/// - no discriminator characters appear (→ fall back to script default)
/// - discriminators for two different languages appear (→ conflict; fail-safe
///   fall back to script default)
///
/// This is the core fail-safe guarantee: the function never returns a wrong
/// answer.  In the worst case it returns `None` and the caller uses the
/// previous default behaviour.
fn discriminate_by_chars(text: &str, script: &str) -> Option<&'static str> {
    let mut candidate: Option<&'static str> = None;

    for ch in text.chars() {
        let hit = if script == "Latin" {
            lookup_latin_discriminator(ch)
        } else {
            lookup_discriminator(ch, script)
        };

        if let Some(lang) = hit {
            match candidate {
                None => candidate = Some(lang),
                Some(prev) if prev == lang => {} // same language — reinforce
                Some(_) => return None,          // conflict — bail out
            }
        }
    }

    candidate
}

/// Resolve `lang="auto"` by scanning text for the first non-Latin, non-Common script,
/// then refining with character-level discriminators for ambiguous scripts.
///
/// **Detection strategy (two-tier):**
///
/// 1. **Script detection:** find the primary non-Latin script (unchanged from before).
/// 2. **Discriminator refinement:** for ambiguous scripts (Cyrillic, Arabic), scan
///    for characters exclusive to one language.  If exactly one language's exclusive
///    characters appear, return that language.  If none or multiple appear, fall back
///    to the script default.
/// 3. **Latin fallback:** if the text contains only Latin characters, try Latin-script
///    discriminators (Vietnamese ơ/ư, Turkish İ/ı, German ß).
///
/// **Fail-safe guarantee:** discriminators can only *upgrade* the result (from a
/// generic script default to a specific language).  They never *downgrade* — if
/// anything is uncertain, the previous default behaviour is preserved.
///
/// Returns the default language code for that script, or `None` if the text
/// contains only Latin/Common/Inherited characters (or is empty) and no Latin
/// discriminators match.
///
/// **Note:** For mixed-script input (e.g. "Hello 北京 Привет"), the first
/// non-Latin script encountered wins. This is a deliberate simplification —
/// callers needing per-segment transliteration should split the text first.
pub fn resolve_auto_lang(text: &str) -> Option<String> {
    // Pass 1: Find primary non-Latin, non-Common script.
    let mut primary_script: Option<&str> = None;
    for ch in text.chars() {
        let script = detect_char_script(ch);
        if script != "Common" && script != "Inherited" && script != "Latin" {
            primary_script = Some(script);
            break;
        }
    }

    match primary_script {
        Some(script) if is_ambiguous_script(script) => {
            // Ambiguous script — try discriminators, fall back to script default
            let lang = discriminate_by_chars(text, script)
                .or_else(|| script_to_lang(script));
            lang.map(str::to_owned)
        }
        Some(script) => {
            // Unambiguous script — direct mapping (unchanged)
            script_to_lang(script).map(str::to_owned)
        }
        None => {
            // No non-Latin script — try Latin discriminators if text has
            // non-ASCII characters (accented Latin, special letters)
            if text.is_ascii() {
                None
            } else {
                discriminate_by_chars(text, "Latin").map(str::to_owned)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detect_latin() {
        let scripts = _detect_scripts("hello");
        assert_eq!(scripts, vec!["Latin" as &str]);
    }

    #[test]
    fn test_mixed_script() {
        assert!(_is_mixed_script("hello мир"));
    }

    #[test]
    fn test_single_script() {
        assert!(!_is_mixed_script("hello world"));
    }

    #[test]
    fn test_detect_bengali() {
        let scripts = _detect_scripts("বাংলা");
        assert_eq!(scripts, vec!["Bengali"]);
    }

    #[test]
    fn test_detect_tamil() {
        let scripts = _detect_scripts("தமிழ்");
        assert_eq!(scripts, vec!["Tamil"]);
    }

    #[test]
    fn test_detect_telugu() {
        let scripts = _detect_scripts("తెలుగు");
        assert_eq!(scripts, vec!["Telugu"]);
    }

    #[test]
    fn test_detect_kannada() {
        let scripts = _detect_scripts("ಕನ್ನಡ");
        assert_eq!(scripts, vec!["Kannada"]);
    }

    #[test]
    fn test_detect_malayalam() {
        let scripts = _detect_scripts("മലയാളം");
        assert_eq!(scripts, vec!["Malayalam"]);
    }

    #[test]
    fn test_detect_gujarati() {
        let scripts = _detect_scripts("ગુજરાતી");
        assert_eq!(scripts, vec!["Gujarati"]);
    }

    #[test]
    fn test_detect_gurmukhi() {
        let scripts = _detect_scripts("ਗੁਰਮੁਖੀ");
        assert_eq!(scripts, vec!["Gurmukhi"]);
    }

    #[test]
    fn test_detect_thai() {
        let scripts = _detect_scripts("ภาษาไทย");
        assert_eq!(scripts, vec!["Thai"]);
    }

    #[test]
    fn test_detect_lao() {
        let scripts = _detect_scripts("ພາສາລາວ");
        assert_eq!(scripts, vec!["Lao"]);
    }

    #[test]
    fn test_detect_myanmar() {
        let scripts = _detect_scripts("မြန်မာ");
        assert_eq!(scripts, vec!["Myanmar"]);
    }

    #[test]
    fn test_detect_tibetan() {
        let scripts = _detect_scripts("བོད་སྐད");
        assert_eq!(scripts, vec!["Tibetan"]);
    }

    #[test]
    fn test_detect_sinhala() {
        let scripts = _detect_scripts("සිංහල");
        assert_eq!(scripts, vec!["Sinhala"]);
    }

    #[test]
    fn test_detect_khmer() {
        let scripts = _detect_scripts("ភាសាខ្មែរ");
        assert_eq!(scripts, vec!["Khmer"]);
    }

    #[test]
    fn test_detect_georgian() {
        let scripts = _detect_scripts("ქართული");
        assert_eq!(scripts, vec!["Georgian"]);
    }

    #[test]
    fn test_detect_armenian() {
        let scripts = _detect_scripts("Հայերեն");
        assert_eq!(scripts, vec!["Armenian"]);
    }

    #[test]
    fn test_detect_ethiopic() {
        let scripts = _detect_scripts("አማርኛ");
        assert_eq!(scripts, vec!["Ethiopic"]);
    }

    #[test]
    fn test_detect_hangul() {
        let scripts = _detect_scripts("한국어");
        assert_eq!(scripts, vec!["Hangul"]);
    }

    #[test]
    fn test_detect_han() {
        let scripts = _detect_scripts("中文");
        assert_eq!(scripts, vec!["Han"]);
    }

    #[test]
    fn test_detect_arabic() {
        let scripts = _detect_scripts("العربية");
        assert_eq!(scripts, vec!["Arabic"]);
    }

    #[test]
    fn test_detect_hebrew() {
        let scripts = _detect_scripts("עברית");
        assert_eq!(scripts, vec!["Hebrew"]);
    }

    #[test]
    fn test_detect_oriya() {
        let scripts = _detect_scripts("ଓଡ଼ିଆ");
        assert_eq!(scripts, vec!["Oriya"]);
    }

    #[test]
    fn test_detect_coptic() {
        let scripts = _detect_scripts("Ⲙⲉⲧⲣⲉⲙⲛⲕⲏⲙⲉ");
        assert_eq!(scripts, vec!["Coptic"]);
    }

    #[test]
    fn test_inherited_combining_marks() {
        // Combining acute accent alone should be Inherited (filtered by detect_scripts)
        let scripts = _detect_scripts("\u{0301}");
        assert!(scripts.is_empty());
    }

    // ── Remaining scripts (ensure no enum member lacks detection) ──

    #[test]
    fn test_detect_syriac() {
        assert_eq!(detect_char_script('\u{0710}'), "Syriac");
        assert_eq!(detect_char_script('\u{074F}'), "Syriac");
    }

    #[test]
    fn test_detect_thaana() {
        assert_eq!(detect_char_script('\u{0780}'), "Thaana");
        assert_eq!(detect_char_script('\u{07BF}'), "Thaana");
    }

    #[test]
    fn test_detect_nko() {
        assert_eq!(detect_char_script('\u{07C1}'), "NKo");
        assert_eq!(detect_char_script('\u{07FF}'), "NKo");
    }

    #[test]
    fn test_detect_mongolian() {
        assert_eq!(detect_char_script('\u{1820}'), "Mongolian");
        assert_eq!(detect_char_script('\u{18AF}'), "Mongolian");
    }

    #[test]
    fn test_detect_cherokee() {
        assert_eq!(detect_char_script('\u{13A0}'), "Cherokee");
        assert_eq!(detect_char_script('\u{13FF}'), "Cherokee");
    }

    #[test]
    fn test_detect_canadian_aboriginal() {
        assert_eq!(detect_char_script('\u{1401}'), "CanadianAboriginal");
        assert_eq!(detect_char_script('\u{167F}'), "CanadianAboriginal");
    }

    #[test]
    fn test_detect_ogham() {
        assert_eq!(detect_char_script('\u{1681}'), "Ogham");
        assert_eq!(detect_char_script('\u{169F}'), "Ogham");
    }

    #[test]
    fn test_detect_runic() {
        assert_eq!(detect_char_script('\u{16A0}'), "Runic");
        assert_eq!(detect_char_script('\u{16FF}'), "Runic");
    }

    #[test]
    fn test_detect_tai_le() {
        assert_eq!(detect_char_script('\u{1950}'), "TaiLe");
        assert_eq!(detect_char_script('\u{197F}'), "TaiLe");
    }

    #[test]
    fn test_detect_new_tai_lue() {
        assert_eq!(detect_char_script('\u{1980}'), "NewTaiLue");
        assert_eq!(detect_char_script('\u{19DF}'), "NewTaiLue");
    }

    #[test]
    fn test_detect_balinese() {
        assert_eq!(detect_char_script('\u{1B05}'), "Balinese");
        assert_eq!(detect_char_script('\u{1B7F}'), "Balinese");
    }

    #[test]
    fn test_detect_javanese() {
        assert_eq!(detect_char_script('\u{A984}'), "Javanese");
        assert_eq!(detect_char_script('\u{A9DF}'), "Javanese");
    }

    #[test]
    fn test_detect_vai() {
        assert_eq!(detect_char_script('\u{A500}'), "Vai");
        assert_eq!(detect_char_script('\u{A63F}'), "Vai");
    }

    // ── Boundary codepoint tests ────────────────────────────────

    #[test]
    fn test_latin_block_boundaries() {
        // Basic Latin uppercase start
        assert_eq!(detect_char_script('A'), "Latin"); // U+0041
        assert_eq!(detect_char_script('Z'), "Latin"); // U+005A
                                                      // Basic Latin lowercase
        assert_eq!(detect_char_script('a'), "Latin"); // U+0061
        assert_eq!(detect_char_script('z'), "Latin"); // U+007A
                                                      // Latin-1 Supplement start
        assert_eq!(detect_char_script('\u{00C0}'), "Latin"); // À
                                                             // Latin Extended-B end
        assert_eq!(detect_char_script('\u{024F}'), "Latin");
        // IPA Extensions
        assert_eq!(detect_char_script('\u{0250}'), "Latin");
        assert_eq!(detect_char_script('\u{02AF}'), "Latin");
        // Latin Extended Additional
        assert_eq!(detect_char_script('\u{1E00}'), "Latin");
        assert_eq!(detect_char_script('\u{1EFF}'), "Latin");
    }

    #[test]
    fn test_greek_block_boundaries() {
        assert_eq!(detect_char_script('\u{0370}'), "Greek");
        assert_eq!(detect_char_script('\u{03FF}'), "Greek");
        // Greek Extended
        assert_eq!(detect_char_script('\u{1F00}'), "Greek");
        assert_eq!(detect_char_script('\u{1FFF}'), "Greek");
    }

    #[test]
    fn test_cyrillic_block_boundaries() {
        assert_eq!(detect_char_script('\u{0400}'), "Cyrillic");
        assert_eq!(detect_char_script('\u{04FF}'), "Cyrillic");
        // Cyrillic Supplement
        assert_eq!(detect_char_script('\u{0500}'), "Cyrillic");
        assert_eq!(detect_char_script('\u{052F}'), "Cyrillic");
        // Cyrillic Extended-A
        assert_eq!(detect_char_script('\u{2DE0}'), "Cyrillic");
        assert_eq!(detect_char_script('\u{2DFF}'), "Cyrillic");
        // Cyrillic Extended-B
        assert_eq!(detect_char_script('\u{A640}'), "Cyrillic");
        assert_eq!(detect_char_script('\u{A69F}'), "Cyrillic");
    }

    #[test]
    fn test_arabic_block_boundaries() {
        assert_eq!(detect_char_script('\u{0600}'), "Arabic");
        assert_eq!(detect_char_script('\u{06FF}'), "Arabic");
        // Arabic Supplement
        assert_eq!(detect_char_script('\u{0750}'), "Arabic");
        assert_eq!(detect_char_script('\u{077F}'), "Arabic");
        // Arabic Extended-A
        assert_eq!(detect_char_script('\u{08A0}'), "Arabic");
        assert_eq!(detect_char_script('\u{08FF}'), "Arabic");
        // Arabic Presentation Forms-A
        assert_eq!(detect_char_script('\u{FB50}'), "Arabic");
        // Arabic Presentation Forms-B
        assert_eq!(detect_char_script('\u{FE70}'), "Arabic");
        assert_eq!(detect_char_script('\u{FEFF}'), "Arabic");
    }

    #[test]
    fn test_han_supplementary_planes() {
        // CJK Unified Ideographs main block
        assert_eq!(detect_char_script('\u{4E00}'), "Han");
        assert_eq!(detect_char_script('\u{9FFF}'), "Han");
        // CJK Extension A
        assert_eq!(detect_char_script('\u{3400}'), "Han");
        assert_eq!(detect_char_script('\u{4DBF}'), "Han");
        // CJK Extension B (SMP)
        assert_eq!(detect_char_script('\u{20000}'), "Han");
        assert_eq!(detect_char_script('\u{2A6DF}'), "Han");
        // CJK Extension C
        assert_eq!(detect_char_script('\u{2A700}'), "Han");
        // CJK Extension G
        assert_eq!(detect_char_script('\u{30000}'), "Han");
    }

    #[test]
    fn test_hangul_block_boundaries() {
        // Jamo
        assert_eq!(detect_char_script('\u{1100}'), "Hangul");
        assert_eq!(detect_char_script('\u{11FF}'), "Hangul");
        // Compatibility Jamo
        assert_eq!(detect_char_script('\u{3130}'), "Hangul");
        assert_eq!(detect_char_script('\u{318F}'), "Hangul");
        // Syllables
        assert_eq!(detect_char_script('\u{AC00}'), "Hangul");
        assert_eq!(detect_char_script('\u{D7AF}'), "Hangul");
    }

    // ── detect_char_script for Common/Inherited ─────────────────

    #[test]
    fn test_common_detection() {
        assert_eq!(detect_char_script('0'), "Common");
        assert_eq!(detect_char_script(' '), "Common");
        assert_eq!(detect_char_script('!'), "Common");
    }

    #[test]
    fn test_inherited_combining_diacriticals() {
        assert_eq!(detect_char_script('\u{0300}'), "Inherited"); // Combining grave
        assert_eq!(detect_char_script('\u{036F}'), "Inherited"); // End of block
    }

    #[test]
    fn test_inherited_combining_extended() {
        assert_eq!(detect_char_script('\u{1AB0}'), "Inherited");
        assert_eq!(detect_char_script('\u{1AFF}'), "Inherited");
    }

    #[test]
    fn test_inherited_combining_supplement() {
        assert_eq!(detect_char_script('\u{1DC0}'), "Inherited");
        assert_eq!(detect_char_script('\u{1DFF}'), "Inherited");
    }

    #[test]
    fn test_inherited_combining_symbols() {
        assert_eq!(detect_char_script('\u{20D0}'), "Inherited");
        assert_eq!(detect_char_script('\u{20FF}'), "Inherited");
    }

    #[test]
    fn test_inherited_combining_half_marks() {
        assert_eq!(detect_char_script('\u{FE20}'), "Inherited");
        assert_eq!(detect_char_script('\u{FE2F}'), "Inherited");
    }

    // ── Mixed-script ordering ───────────────────────────────────

    #[test]
    fn test_script_order_preserved() {
        let scripts = _detect_scripts("hello Москва");
        assert_eq!(scripts, vec!["Latin", "Cyrillic"]);
    }

    #[test]
    fn test_three_scripts_detected() {
        let scripts = _detect_scripts("abc мир 日本");
        assert_eq!(scripts.len(), 3);
        assert_eq!(scripts[0], "Latin");
        assert_eq!(scripts[1], "Cyrillic");
        assert_eq!(scripts[2], "Han");
    }

    #[test]
    fn test_empty_string_no_scripts() {
        let scripts = _detect_scripts("");
        assert!(scripts.is_empty());
    }

    #[test]
    fn test_digits_only_no_scripts() {
        let scripts = _detect_scripts("12345");
        assert!(scripts.is_empty());
    }

    // ── Supplementary block edge cases ──────────────────────────

    #[test]
    fn test_syriac_supplement() {
        assert_eq!(detect_char_script('\u{0860}'), "Syriac");
        assert_eq!(detect_char_script('\u{086F}'), "Syriac");
    }

    #[test]
    fn test_latin_ligatures_in_alphabetic_pf() {
        // FB00–FB06 are LATIN ligatures, not Armenian.
        // They share the Alphabetic Presentation Forms block with Armenian
        // ligatures (FB13–FB17), which caused the original misclassification.
        assert_eq!(detect_char_script('\u{FB00}'), "Latin"); // ﬀ  LATIN SMALL LIGATURE FF
        assert_eq!(detect_char_script('\u{FB01}'), "Latin"); // ﬁ  LATIN SMALL LIGATURE FI
        assert_eq!(detect_char_script('\u{FB02}'), "Latin"); // ﬂ  LATIN SMALL LIGATURE FL
        assert_eq!(detect_char_script('\u{FB03}'), "Latin"); // ﬃ  LATIN SMALL LIGATURE FFI
        assert_eq!(detect_char_script('\u{FB04}'), "Latin"); // ﬄ  LATIN SMALL LIGATURE FFL
        assert_eq!(detect_char_script('\u{FB05}'), "Latin"); // ﬅ  LATIN SMALL LIGATURE LONG S T
        assert_eq!(detect_char_script('\u{FB06}'), "Latin"); // ﬆ  LATIN SMALL LIGATURE ST
    }

    #[test]
    fn test_armenian_ligatures_in_alphabetic_pf() {
        // FB13–FB17 are the actual Armenian ligatures in Alphabetic PF.
        assert_eq!(detect_char_script('\u{FB13}'), "Armenian"); // ﬓ  ARMENIAN SMALL LIGATURE MEN NOW
        assert_eq!(detect_char_script('\u{FB14}'), "Armenian"); // ﬔ  ARMENIAN SMALL LIGATURE MEN ECH
        assert_eq!(detect_char_script('\u{FB15}'), "Armenian"); // ﬕ  ARMENIAN SMALL LIGATURE MEN INI
        assert_eq!(detect_char_script('\u{FB16}'), "Armenian"); // ﬖ  ARMENIAN SMALL LIGATURE VEW NOW
        assert_eq!(detect_char_script('\u{FB17}'), "Armenian"); // ﬗ  ARMENIAN SMALL LIGATURE MEN XEH
    }

    #[test]
    fn test_latin_ligature_fi_detected_as_latin_in_text() {
        // Regression: detect_scripts("ﬁ") previously returned [Armenian]
        let scripts = _detect_scripts("ﬁ");
        assert_eq!(scripts, vec!["Latin" as &str]);
    }

    #[test]
    fn test_armenian_ligature_detected_in_text() {
        // Regression: detect_scripts("ﬓ") previously returned [] (Common)
        let scripts = _detect_scripts("ﬓ");
        assert_eq!(scripts, vec!["Armenian"]);
    }

    #[test]
    fn test_mixed_latin_and_armenian_ligatures() {
        // Text containing both Latin ligature ﬁ and Armenian ligature ﬓ
        let scripts = _detect_scripts("ﬁﬓ");
        assert_eq!(scripts, vec!["Latin", "Armenian"]);
    }

    #[test]
    fn test_devanagari_extended_range() {
        assert_eq!(detect_char_script('\u{A8E0}'), "Devanagari");
        assert_eq!(detect_char_script('\u{A8FF}'), "Devanagari");
    }

    #[test]
    fn test_ethiopic_extended() {
        assert_eq!(detect_char_script('\u{2D80}'), "Ethiopic");
        assert_eq!(detect_char_script('\u{2DDF}'), "Ethiopic");
    }

    #[test]
    fn test_ethiopic_extended_a() {
        assert_eq!(detect_char_script('\u{AB00}'), "Ethiopic");
        assert_eq!(detect_char_script('\u{AB2F}'), "Ethiopic");
    }

    #[test]
    fn test_cherokee_supplement_range() {
        assert_eq!(detect_char_script('\u{AB70}'), "Cherokee");
        assert_eq!(detect_char_script('\u{ABBF}'), "Cherokee");
    }

    #[test]
    fn test_canadian_aboriginal_extended() {
        assert_eq!(detect_char_script('\u{18B0}'), "CanadianAboriginal");
        assert_eq!(detect_char_script('\u{18FF}'), "CanadianAboriginal");
    }

    #[test]
    fn test_georgian_extended() {
        assert_eq!(detect_char_script('\u{1C90}'), "Georgian");
        assert_eq!(detect_char_script('\u{1CBF}'), "Georgian");
    }

    #[test]
    fn test_myanmar_extended_a_range() {
        assert_eq!(detect_char_script('\u{AA60}'), "Myanmar");
        assert_eq!(detect_char_script('\u{AA7F}'), "Myanmar");
    }

    #[test]
    fn test_khmer_symbols_range() {
        assert_eq!(detect_char_script('\u{19E0}'), "Khmer");
        assert_eq!(detect_char_script('\u{19FF}'), "Khmer");
    }

    // ── resolve_auto_lang tests ─────────────────────────────────

    #[test]
    fn test_resolve_auto_lang_thai() {
        assert_eq!(resolve_auto_lang("ภาษาไทย"), Some("th".to_owned()));
    }

    #[test]
    fn test_resolve_auto_lang_latin_only() {
        assert_eq!(resolve_auto_lang("hello"), None);
    }

    #[test]
    fn test_resolve_auto_lang_empty() {
        assert_eq!(resolve_auto_lang(""), None);
    }

    #[test]
    fn test_resolve_auto_lang_accented_latin() {
        assert_eq!(resolve_auto_lang("café"), None);
    }

    #[test]
    fn test_resolve_auto_lang_mixed_latin_cyrillic() {
        assert_eq!(resolve_auto_lang("Hello Москва"), Some("ru".to_owned()));
    }

    #[test]
    fn test_resolve_auto_lang_hiragana() {
        assert_eq!(resolve_auto_lang("こんにちは"), Some("ja".to_owned()));
    }

    #[test]
    fn test_resolve_auto_lang_han() {
        assert_eq!(resolve_auto_lang("中文"), Some("zh".to_owned()));
    }

    #[test]
    fn test_resolve_auto_lang_hangul() {
        assert_eq!(resolve_auto_lang("한국어"), Some("ko".to_owned()));
    }

    #[test]
    fn test_resolve_auto_lang_arabic() {
        assert_eq!(resolve_auto_lang("العربية"), Some("ar".to_owned()));
    }

    #[test]
    fn test_resolve_auto_lang_hebrew() {
        assert_eq!(resolve_auto_lang("עברית"), Some("he".to_owned()));
    }

    #[test]
    fn test_resolve_auto_lang_georgian() {
        assert_eq!(resolve_auto_lang("ქართული"), Some("ka".to_owned()));
    }

    #[test]
    fn test_resolve_auto_lang_armenian() {
        assert_eq!(resolve_auto_lang("Հայերեն"), Some("hy".to_owned()));
    }

    #[test]
    fn test_resolve_auto_lang_unmapped_script() {
        // Runic character — no language mapping
        assert_eq!(resolve_auto_lang("\u{16A0}"), None);
    }

    // ── Language discriminator tests ──────────────────────────────

    #[test]
    fn test_discriminate_ukrainian_by_exclusive_chars() {
        // ї is exclusively Ukrainian among our Cyrillic profiles
        assert_eq!(resolve_auto_lang("Київ — столиця України"), Some("uk".to_owned()));
    }

    #[test]
    fn test_discriminate_serbian_by_exclusive_chars() {
        // ћ and ђ are exclusively Serbian
        assert_eq!(resolve_auto_lang("Ђорђе и Ћирилица"), Some("sr".to_owned()));
    }

    #[test]
    fn test_discriminate_persian_by_exclusive_chars() {
        // پ چ ژ گ are exclusively Persian among our Arabic profiles
        assert_eq!(resolve_auto_lang("پارسی زبان"), Some("fa".to_owned()));
    }

    #[test]
    fn test_discriminate_vietnamese_by_exclusive_chars() {
        // ơ and ư are exclusively Vietnamese
        assert_eq!(resolve_auto_lang("Việt Nam có nhiều người"), Some("vi".to_owned()));
    }

    #[test]
    fn test_discriminate_turkish_by_exclusive_chars() {
        // İ and ı are exclusively Turkish
        assert_eq!(resolve_auto_lang("İstanbul güzel bir şehır"), Some("tr".to_owned()));
    }

    #[test]
    fn test_discriminate_german_by_exclusive_chars() {
        // ß is exclusively German
        assert_eq!(resolve_auto_lang("Straße nach Süden"), Some("de".to_owned()));
    }

    #[test]
    fn test_discriminate_fallback_on_conflict() {
        // Mix Ukrainian ї and Serbian ћ — should fall back to script default (ru)
        assert_eq!(resolve_auto_lang("їћ"), Some("ru".to_owned()));
    }

    #[test]
    fn test_discriminate_cyrillic_no_exclusive_chars() {
        // Plain Russian text with no exclusive chars — default to ru
        assert_eq!(resolve_auto_lang("Москва"), Some("ru".to_owned()));
    }

    #[test]
    fn test_discriminate_arabic_no_exclusive_chars() {
        // Plain Arabic text with no Persian chars — default to ar
        assert_eq!(resolve_auto_lang("العربية"), Some("ar".to_owned()));
    }

    #[test]
    fn test_discriminate_latin_no_exclusive_chars() {
        // Accented Latin with no exclusive chars — returns None (no lang)
        assert_eq!(resolve_auto_lang("café"), None);
    }

    #[test]
    fn test_discriminate_latin_ascii_only() {
        // Pure ASCII — returns None
        assert_eq!(resolve_auto_lang("hello"), None);
    }
}
