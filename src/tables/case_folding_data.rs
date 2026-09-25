//! Full Unicode case folding table (status C + F from CaseFolding.txt).
//!
//! Generated at build time as a PHF map from `case_folding.tsv`.
//! Provides O(1) lookup for all 1,557 case folding mappings.

include!(concat!(env!("OUT_DIR"), "/case_folding_phf.rs"));
// `CASE_FOLD_BMP`: the BMP keys of `CASE_FOLD`, one bit each (build.rs).
include!(concat!(env!("OUT_DIR"), "/case_folding_bmp.rs"));

/// Look up the full case fold for a character.
/// Returns `None` if the character maps to itself (i.e., is already folded).
///
/// Most characters a fold reads are already folded, and the bitmap says so with one bit
/// where the map would hash the character first; `tests::bitmap_is_the_map` holds the two
/// equal over the BMP.
#[inline]
pub fn lookup(ch: char) -> Option<&'static str> {
    let cp = u32::from(ch);
    if cp <= 0xFFFF && CASE_FOLD_BMP[(cp >> 6) as usize] >> (cp & 63) & 1 == 0 {
        return None;
    }
    CASE_FOLD.get(&ch).copied()
}

/// This module's generated `phf` tables, for [`crate::phf_integrity`].
#[cfg(test)]
pub(super) fn phf_tables() -> Vec<crate::phf_integrity::Table> {
    use crate::phf_integrity::Table as T;
    vec![T::CharStr("CASE_FOLD", &CASE_FOLD)]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bitmap_is_the_map() {
        for c in (0u32..0x1_0000).filter_map(char::from_u32) {
            assert_eq!(
                lookup(c),
                CASE_FOLD.get(&c).copied(),
                "U+{:04X}",
                u32::from(c)
            );
        }
        for (&key, &value) in CASE_FOLD.entries() {
            assert_eq!(lookup(key), Some(value), "{key:?}");
        }
    }
}
