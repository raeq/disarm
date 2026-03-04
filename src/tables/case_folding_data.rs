//! Full Unicode case folding table (status C + F from CaseFolding.txt).
//!
//! Generated at build time as a PHF map from `case_folding.tsv`.
//! Provides O(1) lookup for all 1,557 case folding mappings.

include!(concat!(env!("OUT_DIR"), "/case_folding_phf.rs"));

/// Look up the full case fold for a character.
/// Returns `None` if the character maps to itself (i.e., is already folded).
#[inline]
pub fn lookup(ch: char) -> Option<&'static str> {
    CASE_FOLD.get(&ch).copied()
}
