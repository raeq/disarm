//! Layer 1 (pure-Rust core): Unicode script detection + auto-language
//! inspection. No pyo3. Shims in `src/py/scripts.rs`; crates.io surface is
//! `crate::api::{detect_scripts, is_mixed_script, inspect_auto_lang}`.

/// Detect Unicode scripts present in text, in order of first appearance.
///
/// Returns `&'static str` script names, avoiding per-character String
/// allocation.  The `HashSet` and output `Vec` use borrowed static strings.
pub(crate) fn detect_scripts(text: &str) -> Vec<&'static str> {
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
pub(crate) fn is_mixed_script(text: &str) -> bool {
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
    // Tagalog, Hanunoo, Buhid, Tagbanwa
    (0x1700, 0x171F, "Tagalog"),
    (0x1720, 0x173F, "Hanunoo"),
    (0x1740, 0x175F, "Buhid"),
    (0x1760, 0x177F, "Tagbanwa"),
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
    // Buginese (Lontara)
    (0x1A00, 0x1A1F, "Buginese"),
    // Tai Tham (Lanna)
    (0x1A20, 0x1AAF, "TaiTham"),
    // Inherited — Combining Diacritical Marks Extended
    (0x1AB0, 0x1AFF, "Inherited"),
    // Balinese
    (0x1B00, 0x1B7F, "Balinese"),
    // Sundanese
    (0x1B80, 0x1BBF, "Sundanese"),
    // Batak
    (0x1BC0, 0x1BFF, "Batak"),
    // Ol Chiki
    (0x1C50, 0x1C7F, "OlChiki"),
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
    // Tifinagh
    (0x2D30, 0x2D7F, "Tifinagh"),
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
    // Lisu (Fraser)
    (0xA4D0, 0xA4FF, "Lisu"),
    // Vai
    (0xA500, 0xA63F, "Vai"),
    // Cyrillic Extended-B
    (0xA640, 0xA69F, "Cyrillic"),
    // Bamum
    (0xA6A0, 0xA6FF, "Bamum"),
    // Latin Extended-D
    (0xA720, 0xA7FF, "Latin"),
    // Devanagari Extended
    (0xA8E0, 0xA8FF, "Devanagari"),
    // Hangul Jamo Extended-A
    (0xA960, 0xA97F, "Hangul"),
    // Javanese
    (0xA980, 0xA9DF, "Javanese"),
    // Cham
    (0xAA00, 0xAA5F, "Cham"),
    // Myanmar Extended-A
    (0xAA60, 0xAA7F, "Myanmar"),
    // Meetei Mayek Extensions
    (0xAAE0, 0xAAFF, "MeeteiMayek"),
    // Ethiopic Extended-A
    (0xAB00, 0xAB2F, "Ethiopic"),
    // Latin Extended-E
    (0xAB30, 0xAB6F, "Latin"),
    // Cherokee Supplement
    (0xAB70, 0xABBF, "Cherokee"),
    // Meetei Mayek
    (0xABC0, 0xABFF, "MeeteiMayek"),
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
    // Linear B Syllabary
    (0x10000, 0x1007F, "LinearB"),
    // Linear B Ideograms
    (0x10080, 0x100FF, "LinearB"),
    // Gothic
    (0x10330, 0x1034F, "Gothic"),
    // Old Persian
    (0x103A0, 0x103DF, "OldPersian"),
    // Cuneiform
    (0x12000, 0x123FF, "Cuneiform"),
    (0x12400, 0x1247F, "Cuneiform"), // Cuneiform Numbers and Punctuation
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
pub(crate) fn detect_char_script(ch: char) -> &'static str {
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

/// The scripts whose letters are strong **right-to-left** under the Unicode
/// Bidirectional Algorithm (UAX #9): Hebrew/Syriac/Thaana/N'Ko are class `R`,
/// Arabic is `AL`. For detecting a *direction conflict* the distinction between
/// `R` and `AL` does not matter — both reorder against left-to-right text — so
/// they are folded into a single `Rtl`.
const RTL_SCRIPTS: &[&str] = &["Hebrew", "Arabic", "Syriac", "Thaana", "NKo"];

/// Strong bidirectional direction of a character, for direction-conflict
/// detection.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(crate) enum StrongDir {
    /// Strong left-to-right (UAX #9 `L`): letters of Latin, Cyrillic, Greek,
    /// CJK, Indic, … — every named script that is not strong-RTL.
    Ltr,
    /// Strong right-to-left (UAX #9 `R`/`AL`): letters of [`RTL_SCRIPTS`].
    Rtl,
}

/// Resolve a character's strong bidi direction, or `None` for a bidi-neutral
/// character (digits and numerics — UAX #9 `EN`/`AN` — plus all `Common` and
/// `Inherited` punctuation, whitespace and combining marks).
///
/// This is derived from disarm's own [`detect_char_script`] ranges — it is
/// *script-level*, a deliberate, conservative approximation of the per-codepoint
/// UAX #9 class and needs no external bidi table. Numerics are excluded first so
/// that, e.g., Arabic-Indic digits (which live in the Arabic block but are bidi
/// class `AN`) do not by themselves create a conflict.
pub(crate) fn strong_dir(ch: char) -> Option<StrongDir> {
    if ch.is_numeric() {
        return None;
    }
    match detect_char_script(ch) {
        "Common" | "Inherited" => None,
        s if RTL_SCRIPTS.contains(&s) => Some(StrongDir::Rtl),
        _ => Some(StrongDir::Ltr),
    }
}

/// True iff `text` contains at least one strong-left-to-right character **and**
/// at least one strong-right-to-left character — the precondition for Unicode
/// Bidi display-reordering (UAX #9).
///
/// This is the structural signal behind "BiDi Swap"-style spoofs, where an LTR
/// brand label sits beside an RTL domain (e.g. `varonis.com.ו.קום`): the
/// reordering happens in the *real letters*, with **no** U+202x override
/// involved, so [`crate::whitespace`]-style override stripping is a no-op on it.
/// A `false` result is not a safety guarantee — it only means no strong-LTR and
/// strong-RTL letters coexist in this string.
pub(crate) fn has_bidi_conflict(text: &str) -> bool {
    let mut ltr = false;
    let mut rtl = false;
    for ch in text.chars() {
        match strong_dir(ch) {
            Some(StrongDir::Ltr) => ltr = true,
            Some(StrongDir::Rtl) => rtl = true,
            None => continue,
        }
        if ltr && rtl {
            return true;
        }
    }
    false
}

/// Map a detected script name to a default language code (ISO 639-1 where one
/// exists, otherwise ISO 639-3 — e.g. `chr`, `cop`, `vai`, `tzm`).
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
        // Scripts added in v0.3.0+
        "Balinese" => Some("ban"),
        "Bamum" => Some("bax"),
        "Buginese" => Some("bug"),
        "Cherokee" => Some("chr"),
        "Cham" => Some("cjm"),
        "Coptic" => Some("cop"),
        "Lisu" => Some("lis"),
        "MeeteiMayek" => Some("mni"),
        "NKo" => Some("nqo"),
        "NewTaiLue" => Some("khb"),
        "OlChiki" => Some("sat"),
        "Sundanese" => Some("su"),
        "Syriac" => Some("syr"),
        "TaiLe" => Some("tdd"),
        "TaiTham" => Some("nod"),
        "Tagalog" => Some("tl"),
        "Tifinagh" => Some("tzm"),
        "Vai" => Some("vai"),
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
            '\u{0491}' | '\u{0490}' | '\u{0457}' | '\u{0407}' | '\u{0454}' | '\u{0404}'
            | '\u{0456}' | '\u{0406}' => Some("uk"),
            // Serbian exclusive: ђ Ђ ћ Ћ љ Љ њ Њ џ Џ ј Ј
            '\u{0452}' | '\u{0402}' | '\u{045B}' | '\u{040B}' | '\u{0459}' | '\u{0409}'
            | '\u{045A}' | '\u{040A}' | '\u{045F}' | '\u{040F}' | '\u{0458}' | '\u{0408}' => {
                Some("sr")
            }
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
/// Returns the language of the **first** discriminator character found in scan
/// order (#253), or `None` if no discriminator appears (→ fall back to the
/// script default). The scan stops at the first hit; it does not look ahead for
/// a competing discriminator, so on the rare input mixing two languages'
/// discriminators the first one in the text wins (a documented heuristic, not a
/// conflict-resolution guarantee — see `test_discriminate_first_hit_wins`).
///
/// Because every discriminator is *exclusive* to its language within the script,
/// a hit can only **upgrade** the result from the script default to a more
/// specific profile of the same script — it never selects a wrong-script answer.
fn discriminate_by_chars(text: &str, script: &str) -> Option<&'static str> {
    discriminate_by_chars_detailed(text, script).map(|(lang, _ch)| lang)
}

/// Like `discriminate_by_chars` but also returns the discriminator character
/// that triggered the match.  Used by `inspect_auto_lang` to provide
/// audit-level detail.
fn discriminate_by_chars_detailed(text: &str, script: &str) -> Option<(&'static str, char)> {
    // Cap the scan at `SCAN_LIMIT` characters (centralized in `crate::limits`,
    // #256).  If a discriminator character exists in the text it will almost
    // certainly appear in the opening portion — scanning further is pure
    // overhead for long documents.
    for ch in text.chars().take(crate::limits::SCAN_LIMIT) {
        let hit = if script == "Latin" {
            lookup_latin_discriminator(ch)
        } else {
            lookup_discriminator(ch, script)
        };

        if let Some(lang) = hit {
            return Some((lang, ch));
        }
    }

    None
}

/// Resolve `lang="auto"` by scanning text for the first non-Latin, non-Common script,
/// then refining with character-level discriminators for ambiguous scripts.
///
/// **Detection strategy (two-tier):**
///
/// 1. **Script detection:** find the primary non-Latin script (unchanged from before).
/// 2. **Discriminator refinement:** for ambiguous scripts (Cyrillic, Arabic), scan
///    for characters exclusive to one language and return the language of the
///    **first** such character (#253). If none appears, fall back to the script
///    default. (The scan does not arbitrate between competing discriminators — on
///    rare two-language input the first one in scan order wins.)
/// 3. **Latin fallback:** if the text contains only Latin characters, try Latin-script
///    discriminators (Vietnamese ơ/ư, Turkish İ/ı, German ß).
///
/// **Fail-safe guarantee:** discriminators can only *upgrade* the result (from a
/// generic script default to a more specific language of the same script).  They
/// never select a wrong-script answer; absent any discriminator, the script
/// default is preserved.
///
/// Returns the default language code for that script, or `None` if the text
/// contains only Latin/Common/Inherited characters (or is empty) and no Latin
/// discriminators match.
///
/// **Note:** For mixed-script input (e.g. "Hello 北京 Привет"), the first
/// non-Latin script encountered wins. This is a deliberate simplification —
/// callers needing per-segment transliteration should split the text first.
pub(crate) fn resolve_auto_lang(text: &str) -> Option<String> {
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
            let lang = discriminate_by_chars(text, script).or_else(|| script_to_lang(script));
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

/// Inspect how `lang="auto"` would resolve for the given text.
///
/// Returns the tuple `(script, chosen_lang, reason, discriminators_hit)`:
///   - `script`: primary non-Latin script name, or `None`
///   - `chosen_lang`: resolved language code, or `None`
///   - `reason`: one of `"unambiguous_script"`, `"discriminator"`,
///     `"script_default"`, `"latin_discriminator"`, `"no_detection"`
///   - `discriminators_hit`: the discriminator characters found
///
/// The Layer-2 [`crate::api::inspect_auto_lang`] wraps this in a typed
/// `AutoLangInspection`; the `src/py/scripts.rs` shim marshals it to a Python dict.
pub(crate) fn inspect_auto_lang(
    text: &str,
) -> (
    Option<&'static str>,
    Option<String>,
    &'static str,
    Vec<String>,
) {
    // Pass 1: Find primary non-Latin, non-Common script.
    let mut primary_script: Option<&'static str> = None;
    for ch in text.chars() {
        let script = detect_char_script(ch);
        if script != "Common" && script != "Inherited" && script != "Latin" {
            primary_script = Some(script);
            break;
        }
    }

    match primary_script {
        Some(script) if is_ambiguous_script(script) => {
            match discriminate_by_chars_detailed(text, script) {
                Some((lang, ch)) => (
                    Some(script),
                    Some(lang.to_owned()),
                    "discriminator",
                    vec![ch.to_string()],
                ),
                None => (
                    Some(script),
                    script_to_lang(script).map(str::to_owned),
                    "script_default",
                    vec![],
                ),
            }
        }
        Some(script) => (
            Some(script),
            script_to_lang(script).map(str::to_owned),
            "unambiguous_script",
            vec![],
        ),
        None => {
            if text.is_ascii() {
                (None, None, "no_detection", vec![])
            } else {
                match discriminate_by_chars_detailed(text, "Latin") {
                    Some((lang, ch)) => (
                        None,
                        Some(lang.to_owned()),
                        "latin_discriminator",
                        vec![ch.to_string()],
                    ),
                    None => (None, None, "no_detection", vec![]),
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_script_ranges_sorted() {
        for i in 1..SCRIPT_RANGES.len() {
            let (prev_start, prev_end, prev_script) = SCRIPT_RANGES[i - 1];
            let (curr_start, _, _) = SCRIPT_RANGES[i];
            assert!(
                curr_start > prev_end,
                "SCRIPT_RANGES not sorted or overlapping at index {i}: \
                 ({prev_start:#X}..{prev_end:#X}, {prev_script:?}) vs ({curr_start:#X}..)"
            );
        }
    }

    #[test]
    fn test_detect_latin() {
        let scripts = detect_scripts("hello");
        assert_eq!(scripts, vec!["Latin" as &str]);
    }

    #[test]
    fn test_mixed_script() {
        assert!(is_mixed_script("hello мир"));
    }

    #[test]
    fn test_single_script() {
        assert!(!is_mixed_script("hello world"));
    }

    #[test]
    fn test_detect_bengali() {
        let scripts = detect_scripts("বাংলা");
        assert_eq!(scripts, vec!["Bengali"]);
    }

    #[test]
    fn test_detect_tamil() {
        let scripts = detect_scripts("தமிழ்");
        assert_eq!(scripts, vec!["Tamil"]);
    }

    #[test]
    fn test_detect_telugu() {
        let scripts = detect_scripts("తెలుగు");
        assert_eq!(scripts, vec!["Telugu"]);
    }

    #[test]
    fn test_detect_kannada() {
        let scripts = detect_scripts("ಕನ್ನಡ");
        assert_eq!(scripts, vec!["Kannada"]);
    }

    #[test]
    fn test_detect_malayalam() {
        let scripts = detect_scripts("മലയാളം");
        assert_eq!(scripts, vec!["Malayalam"]);
    }

    #[test]
    fn test_detect_gujarati() {
        let scripts = detect_scripts("ગુજરાતી");
        assert_eq!(scripts, vec!["Gujarati"]);
    }

    #[test]
    fn test_detect_gurmukhi() {
        let scripts = detect_scripts("ਗੁਰਮੁਖੀ");
        assert_eq!(scripts, vec!["Gurmukhi"]);
    }

    #[test]
    fn test_detect_thai() {
        let scripts = detect_scripts("ภาษาไทย");
        assert_eq!(scripts, vec!["Thai"]);
    }

    #[test]
    fn test_detect_lao() {
        let scripts = detect_scripts("ພາສາລາວ");
        assert_eq!(scripts, vec!["Lao"]);
    }

    #[test]
    fn test_detect_myanmar() {
        let scripts = detect_scripts("မြန်မာ");
        assert_eq!(scripts, vec!["Myanmar"]);
    }

    #[test]
    fn test_detect_tibetan() {
        let scripts = detect_scripts("བོད་སྐད");
        assert_eq!(scripts, vec!["Tibetan"]);
    }

    #[test]
    fn test_detect_sinhala() {
        let scripts = detect_scripts("සිංහල");
        assert_eq!(scripts, vec!["Sinhala"]);
    }

    #[test]
    fn test_detect_khmer() {
        let scripts = detect_scripts("ភាសាខ្មែរ");
        assert_eq!(scripts, vec!["Khmer"]);
    }

    #[test]
    fn test_detect_georgian() {
        let scripts = detect_scripts("ქართული");
        assert_eq!(scripts, vec!["Georgian"]);
    }

    #[test]
    fn test_detect_armenian() {
        let scripts = detect_scripts("Հայերեն");
        assert_eq!(scripts, vec!["Armenian"]);
    }

    #[test]
    fn test_detect_ethiopic() {
        let scripts = detect_scripts("አማርኛ");
        assert_eq!(scripts, vec!["Ethiopic"]);
    }

    #[test]
    fn test_detect_hangul() {
        let scripts = detect_scripts("한국어");
        assert_eq!(scripts, vec!["Hangul"]);
    }

    #[test]
    fn test_detect_han() {
        let scripts = detect_scripts("中文");
        assert_eq!(scripts, vec!["Han"]);
    }

    #[test]
    fn test_detect_arabic() {
        let scripts = detect_scripts("العربية");
        assert_eq!(scripts, vec!["Arabic"]);
    }

    #[test]
    fn test_detect_hebrew() {
        let scripts = detect_scripts("עברית");
        assert_eq!(scripts, vec!["Hebrew"]);
    }

    #[test]
    fn test_detect_oriya() {
        let scripts = detect_scripts("ଓଡ଼ିଆ");
        assert_eq!(scripts, vec!["Oriya"]);
    }

    #[test]
    fn test_detect_coptic() {
        let scripts = detect_scripts("Ⲙⲉⲧⲣⲉⲙⲛⲕⲏⲙⲉ");
        assert_eq!(scripts, vec!["Coptic"]);
    }

    #[test]
    fn test_inherited_combining_marks() {
        // Combining acute accent alone should be Inherited (filtered by detect_scripts)
        let scripts = detect_scripts("\u{0301}");
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
        let scripts = detect_scripts("hello Москва");
        assert_eq!(scripts, vec!["Latin", "Cyrillic"]);
    }

    #[test]
    fn test_three_scripts_detected() {
        let scripts = detect_scripts("abc мир 日本");
        assert_eq!(scripts.len(), 3);
        assert_eq!(scripts[0], "Latin");
        assert_eq!(scripts[1], "Cyrillic");
        assert_eq!(scripts[2], "Han");
    }

    #[test]
    fn test_empty_string_no_scripts() {
        let scripts = detect_scripts("");
        assert!(scripts.is_empty());
    }

    #[test]
    fn test_digits_only_no_scripts() {
        let scripts = detect_scripts("12345");
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
        let scripts = detect_scripts("ﬁ");
        assert_eq!(scripts, vec!["Latin" as &str]);
    }

    #[test]
    fn test_armenian_ligature_detected_in_text() {
        // Regression: detect_scripts("ﬓ") previously returned [] (Common)
        let scripts = detect_scripts("ﬓ");
        assert_eq!(scripts, vec!["Armenian"]);
    }

    #[test]
    fn test_mixed_latin_and_armenian_ligatures() {
        // Text containing both Latin ligature ﬁ and Armenian ligature ﬓ
        let scripts = detect_scripts("ﬁﬓ");
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
    fn test_resolve_auto_lang_new_scripts() {
        // One representative LETTER per script added in v0.3.0+, asserting the
        // SCRIPT_RANGES entry and script_to_lang() arm agree end to end. Without
        // this, a typo in either table for a new script would go undetected.
        let cases: &[(char, &str)] = &[
            ('\u{0710}', "syr"), // Syriac letter alaph
            ('\u{07CA}', "nqo"), // NKo letter a
            ('\u{13A0}', "chr"), // Cherokee letter a
            ('\u{1700}', "tl"),  // Tagalog letter a
            ('\u{1950}', "tdd"), // Tai Le letter ka
            ('\u{1980}', "khb"), // New Tai Lue letter high qa
            ('\u{1A00}', "bug"), // Buginese letter ka
            ('\u{1A20}', "nod"), // Tai Tham letter high ka
            ('\u{1B05}', "ban"), // Balinese letter akara
            ('\u{1B83}', "su"),  // Sundanese letter a
            ('\u{1C5A}', "sat"), // Ol Chiki letter la
            ('\u{2C80}', "cop"), // Coptic capital letter alfa
            ('\u{2D30}', "tzm"), // Tifinagh letter ya
            ('\u{A4D0}', "lis"), // Lisu letter ba
            ('\u{A500}', "vai"), // Vai syllable ee
            ('\u{A6A0}', "bax"), // Bamum letter a
            ('\u{AA00}', "cjm"), // Cham letter a
            ('\u{AAE0}', "mni"), // Meetei Mayek letter e
        ];
        for &(ch, lang) in cases {
            assert_eq!(
                resolve_auto_lang(&ch.to_string()),
                Some(lang.to_owned()),
                "U+{:04X} should resolve to {lang}",
                ch as u32
            );
        }
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
        assert_eq!(
            resolve_auto_lang("Київ — столиця України"),
            Some("uk".to_owned())
        );
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
        assert_eq!(
            resolve_auto_lang("Việt Nam có nhiều người"),
            Some("vi".to_owned())
        );
    }

    #[test]
    fn test_discriminate_turkish_by_exclusive_chars() {
        // İ and ı are exclusively Turkish
        assert_eq!(
            resolve_auto_lang("İstanbul güzel bir şehır"),
            Some("tr".to_owned())
        );
    }

    #[test]
    fn test_discriminate_german_by_exclusive_chars() {
        // ß is exclusively German
        assert_eq!(
            resolve_auto_lang("Straße nach Süden"),
            Some("de".to_owned())
        );
    }

    #[test]
    fn test_discriminate_first_hit_wins() {
        // Mix Ukrainian ї and Serbian ћ — first discriminator (ї → uk) wins
        assert_eq!(resolve_auto_lang("їћ"), Some("uk".to_owned()));
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

    #[test]
    fn strong_dir_classifies_ltr_rtl_and_neutral() {
        // Strong LTR: Latin, Cyrillic, Greek, CJK letters.
        for ch in ['a', 'Z', 'д', 'Ω', '中', '한'] {
            assert_eq!(strong_dir(ch), Some(StrongDir::Ltr), "{ch:?}");
        }
        // Strong RTL: Hebrew, Arabic, Syriac, Thaana, N'Ko letters.
        for ch in ['\u{05D5}', '\u{0627}', '\u{0710}', '\u{0780}', '\u{07CA}'] {
            assert_eq!(strong_dir(ch), Some(StrongDir::Rtl), "{ch:?}");
        }
        // Neutral: ASCII digits, Arabic-Indic digits (AN), punctuation, space, mark.
        for ch in ['0', '\u{0664}', '.', '-', ' ', '\u{0301}'] {
            assert_eq!(strong_dir(ch), None, "{ch:?}");
        }
    }

    #[test]
    fn has_bidi_conflict_only_on_ltr_plus_rtl() {
        // LTR + RTL letters => conflict.
        assert!(has_bidi_conflict("varonis\u{05D5}")); // Latin + Hebrew vav
        assert!(has_bidi_conflict("\u{05D5}.\u{05E7}\u{05D5}\u{05DD}com")); // Hebrew + Latin
        assert!(has_bidi_conflict("\u{0430}\u{05D5}")); // Cyrillic + Hebrew (no Latin)
                                                        // Single-direction strings => no conflict.
        assert!(!has_bidi_conflict("varonis.com")); // all LTR
        assert!(!has_bidi_conflict("\u{05D0}\u{05EA}\u{05E8}")); // all Hebrew (RTL)
        assert!(!has_bidi_conflict("google\u{0440}\u{0444}")); // Latin + Cyrillic, both LTR
                                                               // Digits never create a conflict on their own.
        assert!(!has_bidi_conflict("\u{05D5}443")); // Hebrew + ASCII digits
        assert!(!has_bidi_conflict("\u{05D5}\u{0664}")); // Hebrew + Arabic-Indic digit (AN)
    }
}
