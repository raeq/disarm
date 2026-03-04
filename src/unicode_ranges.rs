//! Named constants for Unicode codepoint ranges used throughout the library.
//!
//! Centralising these ranges prevents magic numbers from being duplicated
//! across modules and makes future Unicode version updates easier to apply.

// ── CJK ──────────────────────────────────────────────────────────────────────

/// CJK Unified Ideographs (U+4E00–U+9FFF)
pub const CJK_UNIFIED: std::ops::RangeInclusive<u32> = 0x4E00..=0x9FFF;

/// CJK Extension A (U+3400–U+4DBF)
pub const CJK_EXT_A: std::ops::RangeInclusive<u32> = 0x3400..=0x4DBF;

/// CJK Extension A + Unified combined range used for capacity estimation
/// (U+3000–U+9FFF, covers CJK Symbols, kana, and Unified Ideographs)
pub const CJK_CAPACITY_RANGE: std::ops::RangeInclusive<u32> = 0x3000..=0x9FFF;

/// CJK Compatibility Ideographs (U+F900–U+FAFF)
pub const CJK_COMPAT: std::ops::RangeInclusive<u32> = 0xF900..=0xFAFF;

// ── Hangul ────────────────────────────────────────────────────────────────────

/// Hangul Syllables (U+AC00–U+D7AF)
pub const HANGUL_SYLLABLES: std::ops::RangeInclusive<u32> = 0xAC00..=0xD7AF;

/// Hangul Compatibility Jamo (U+3131–U+3163)
pub const HANGUL_COMPAT_JAMO: std::ops::RangeInclusive<u32> = 0x3131..=0x3163;

// ── Kana ──────────────────────────────────────────────────────────────────────

/// Hiragana block (U+3040–U+309F)
pub const HIRAGANA: std::ops::RangeInclusive<u32> = 0x3040..=0x309F;

/// Katakana block (U+30A0–U+30FF)
pub const KATAKANA: std::ops::RangeInclusive<u32> = 0x30A0..=0x30FF;

/// Half-width Katakana (U+FF65–U+FF9F)
pub const KATAKANA_HALFWIDTH: std::ops::RangeInclusive<u32> = 0xFF65..=0xFF9F;
