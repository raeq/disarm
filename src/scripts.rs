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

/// Detect the Unicode script for a single character.
/// Uses Unicode Script property ranges (UAX #24).
fn detect_char_script(ch: char) -> &'static str {
    let cp = ch as u32;

    // ── Latin ────────────────────────────────────────────
    if (0x0041..=0x005A).contains(&cp)
        || (0x0061..=0x007A).contains(&cp)
        || (0x00C0..=0x024F).contains(&cp)
        || (0x0250..=0x02AF).contains(&cp)   // IPA Extensions
        || (0x1D00..=0x1D7F).contains(&cp)   // Phonetic Extensions
        || (0x1D80..=0x1DBF).contains(&cp)   // Phonetic Extensions Supplement
        || (0x1E00..=0x1EFF).contains(&cp)   // Latin Extended Additional
        || (0x2C60..=0x2C7F).contains(&cp)   // Latin Extended-C
        || (0xA720..=0xA7FF).contains(&cp)   // Latin Extended-D
        || (0xAB30..=0xAB6F).contains(&cp)   // Latin Extended-E
        || (0xFB00..=0xFB06).contains(&cp)
    // Latin ligatures in Alphabetic PF (ﬀ ﬁ ﬂ ﬃ ﬄ ﬅ ﬆ)
    {
        return "Latin";
    }

    // ── Greek ────────────────────────────────────────────
    if (0x0370..=0x03FF).contains(&cp) || (0x1F00..=0x1FFF).contains(&cp)
    // Greek Extended
    {
        return "Greek";
    }

    // ── Cyrillic ─────────────────────────────────────────
    if (0x0400..=0x04FF).contains(&cp)
        || (0x0500..=0x052F).contains(&cp)   // Cyrillic Supplement
        || (0x2DE0..=0x2DFF).contains(&cp)   // Cyrillic Extended-A
        || (0xA640..=0xA69F).contains(&cp)
    // Cyrillic Extended-B
    {
        return "Cyrillic";
    }

    // ── Armenian ─────────────────────────────────────────
    if (0x0530..=0x058F).contains(&cp) || (0xFB13..=0xFB17).contains(&cp)
    // Armenian ligatures in Alphabetic PF (ﬓ ﬔ ﬕ ﬖ ﬗ)
    {
        return "Armenian";
    }

    // ── Hebrew ───────────────────────────────────────────
    if (0x0590..=0x05FF).contains(&cp) || (0xFB1D..=0xFB4F).contains(&cp)
    // Hebrew presentation forms
    {
        return "Hebrew";
    }

    // ── Arabic ───────────────────────────────────────────
    if (0x0600..=0x06FF).contains(&cp)
        || (0x0750..=0x077F).contains(&cp)   // Arabic Supplement
        || (0x08A0..=0x08FF).contains(&cp)   // Arabic Extended-A
        || (0xFB50..=0xFDFF).contains(&cp)   // Arabic Presentation Forms-A
        || (0xFE70..=0xFEFF).contains(&cp)
    // Arabic Presentation Forms-B
    {
        return "Arabic";
    }

    // ── Syriac ───────────────────────────────────────────
    if (0x0700..=0x074F).contains(&cp) || (0x0860..=0x086F).contains(&cp)
    // Syriac Supplement
    {
        return "Syriac";
    }

    // ── Thaana (Maldivian/Dhivehi) ──────────────────────
    if (0x0780..=0x07BF).contains(&cp) {
        return "Thaana";
    }

    // ── N'Ko ─────────────────────────────────────────────
    if (0x07C0..=0x07FF).contains(&cp) {
        return "NKo";
    }

    // ── Devanagari ───────────────────────────────────────
    if (0x0900..=0x097F).contains(&cp) || (0xA8E0..=0xA8FF).contains(&cp)
    // Devanagari Extended
    {
        return "Devanagari";
    }

    // ── Bengali ──────────────────────────────────────────
    if (0x0980..=0x09FF).contains(&cp) {
        return "Bengali";
    }

    // ── Gurmukhi (Punjabi) ───────────────────────────────
    if (0x0A00..=0x0A7F).contains(&cp) {
        return "Gurmukhi";
    }

    // ── Gujarati ─────────────────────────────────────────
    if (0x0A80..=0x0AFF).contains(&cp) {
        return "Gujarati";
    }

    // ── Oriya / Odia ─────────────────────────────────────
    if (0x0B00..=0x0B7F).contains(&cp) {
        return "Oriya";
    }

    // ── Tamil ────────────────────────────────────────────
    if (0x0B80..=0x0BFF).contains(&cp) {
        return "Tamil";
    }

    // ── Telugu ───────────────────────────────────────────
    if (0x0C00..=0x0C7F).contains(&cp) {
        return "Telugu";
    }

    // ── Kannada ──────────────────────────────────────────
    if (0x0C80..=0x0CFF).contains(&cp) {
        return "Kannada";
    }

    // ── Malayalam ────────────────────────────────────────
    if (0x0D00..=0x0D7F).contains(&cp) {
        return "Malayalam";
    }

    // ── Sinhala ──────────────────────────────────────────
    if (0x0D80..=0x0DFF).contains(&cp) {
        return "Sinhala";
    }

    // ── Thai ─────────────────────────────────────────────
    if (0x0E00..=0x0E7F).contains(&cp) {
        return "Thai";
    }

    // ── Lao ──────────────────────────────────────────────
    if (0x0E80..=0x0EFF).contains(&cp) {
        return "Lao";
    }

    // ── Tibetan ──────────────────────────────────────────
    if (0x0F00..=0x0FFF).contains(&cp) {
        return "Tibetan";
    }

    // ── Myanmar (Burmese) ────────────────────────────────
    if (0x1000..=0x109F).contains(&cp) || (0xAA60..=0xAA7F).contains(&cp)
    // Myanmar Extended-A
    {
        return "Myanmar";
    }

    // ── Georgian ─────────────────────────────────────────
    if (0x10A0..=0x10FF).contains(&cp)
        || (0x2D00..=0x2D2F).contains(&cp)   // Georgian Supplement
        || (0x1C90..=0x1CBF).contains(&cp)
    // Georgian Extended
    {
        return "Georgian";
    }

    // ── Hangul ───────────────────────────────────────────
    if (0x1100..=0x11FF).contains(&cp)        // Jamo
        || (0x3130..=0x318F).contains(&cp)    // Compatibility Jamo
        || (0xA960..=0xA97F).contains(&cp)    // Jamo Extended-A
        || (0xAC00..=0xD7AF).contains(&cp)    // Syllables
        || (0xD7B0..=0xD7FF).contains(&cp)
    // Jamo Extended-B
    {
        return "Hangul";
    }

    // ── Ethiopic ─────────────────────────────────────────
    if (0x1200..=0x137F).contains(&cp)
        || (0x1380..=0x139F).contains(&cp)    // Ethiopic Supplement
        || (0x2D80..=0x2DDF).contains(&cp)    // Ethiopic Extended
        || (0xAB00..=0xAB2F).contains(&cp)
    // Ethiopic Extended-A
    {
        return "Ethiopic";
    }

    // ── Cherokee ─────────────────────────────────────────
    if (0x13A0..=0x13FF).contains(&cp) || (0xAB70..=0xABBF).contains(&cp)
    // Cherokee Supplement
    {
        return "Cherokee";
    }

    // ── Canadian Aboriginal Syllabics ────────────────────
    if (0x1400..=0x167F).contains(&cp) || (0x18B0..=0x18FF).contains(&cp)
    // Unified Canadian Aboriginal Syllabics Extended
    {
        return "CanadianAboriginal";
    }

    // ── Ogham ────────────────────────────────────────────
    if (0x1680..=0x169F).contains(&cp) {
        return "Ogham";
    }

    // ── Runic ────────────────────────────────────────────
    if (0x16A0..=0x16FF).contains(&cp) {
        return "Runic";
    }

    // ── Khmer (Cambodian) ────────────────────────────────
    if (0x1780..=0x17FF).contains(&cp) || (0x19E0..=0x19FF).contains(&cp)
    // Khmer Symbols
    {
        return "Khmer";
    }

    // ── Mongolian ────────────────────────────────────────
    if (0x1800..=0x18AF).contains(&cp) {
        return "Mongolian";
    }

    // ── Tai Le ───────────────────────────────────────────
    if (0x1950..=0x197F).contains(&cp) {
        return "TaiLe";
    }

    // ── New Tai Lue ──────────────────────────────────────
    if (0x1980..=0x19DF).contains(&cp) {
        return "NewTaiLue";
    }

    // ── Balinese ─────────────────────────────────────────
    if (0x1B00..=0x1B7F).contains(&cp) {
        return "Balinese";
    }

    // ── Coptic ───────────────────────────────────────────
    if (0x2C80..=0x2CFF).contains(&cp) {
        return "Coptic";
    }

    // ── Hiragana ─────────────────────────────────────────
    if (0x3040..=0x309F).contains(&cp) {
        return "Hiragana";
    }

    // ── Katakana ─────────────────────────────────────────
    if (0x30A0..=0x30FF).contains(&cp)
        || (0x31F0..=0x31FF).contains(&cp)    // Katakana Phonetic Extensions
        || (0xFF65..=0xFF9F).contains(&cp)
    // Halfwidth Katakana
    {
        return "Katakana";
    }

    // ── CJK Unified Ideographs (Han) ────────────────────
    if (0x2E80..=0x2EFF).contains(&cp)        // CJK Radicals Supplement
        || (0x2F00..=0x2FDF).contains(&cp)    // Kangxi Radicals
        || (0x3400..=0x4DBF).contains(&cp)    // CJK Unified Ext A
        || (0x4E00..=0x9FFF).contains(&cp)    // CJK Unified
        || (0xF900..=0xFAFF).contains(&cp)    // CJK Compatibility
        || (0x20000..=0x2A6DF).contains(&cp)  // CJK Unified Ext B
        || (0x2A700..=0x2B73F).contains(&cp)  // CJK Unified Ext C
        || (0x2B740..=0x2B81F).contains(&cp)  // CJK Unified Ext D
        || (0x2B820..=0x2CEAF).contains(&cp)  // CJK Unified Ext E
        || (0x2CEB0..=0x2EBEF).contains(&cp)  // CJK Unified Ext F
        || (0x30000..=0x3134F).contains(&cp)
    // CJK Unified Ext G
    {
        return "Han";
    }

    // ── Vai ──────────────────────────────────────────────
    if (0xA500..=0xA63F).contains(&cp) {
        return "Vai";
    }

    // ── Javanese ─────────────────────────────────────────
    if (0xA980..=0xA9DF).contains(&cp) {
        return "Javanese";
    }

    // ── Common: digits, punctuation, whitespace ──────────
    if ch.is_ascii_digit() || ch.is_ascii_punctuation() || ch.is_whitespace() {
        return "Common";
    }

    // Combining marks in the general range are Inherited
    if (0x0300..=0x036F).contains(&cp)        // Combining Diacritical Marks
        || (0x1AB0..=0x1AFF).contains(&cp)    // Combining Diacritical Marks Extended
        || (0x1DC0..=0x1DFF).contains(&cp)    // Combining Diacritical Marks Supplement
        || (0x20D0..=0x20FF).contains(&cp)    // Combining Diacritical Marks for Symbols
        || (0xFE20..=0xFE2F).contains(&cp)
    // Combining Half Marks
    {
        return "Inherited";
    }

    "Common"
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
}
