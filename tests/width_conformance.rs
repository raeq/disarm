//! Tier-3 conformance test for terminal width (#224).
//!
//! Gated with `#[ignore]` — an exhaustive sweep, run before a release:
//!   cargo test --no-default-features --test width_conformance -- --ignored
//!
//! The rigorous *differential* against the UCD East Asian Width source lives in
//! the Python tier (`tests/test_width.py`, `@pytest.mark.formal`), which has
//! `unicodedata` as a blend-free oracle. (The `unicode-width` crate blends an
//! emoji-width policy into its base width, so it is not a clean EAW oracle for
//! translit's A6 "only Emoji_Presentation widens" rule.)

use _translit::width::grapheme_width;

/// Exhaustive bounds + no-panic over every Unicode scalar (I_w2 base case, A7).
#[test]
#[ignore = "tier 3: exhaustive over all scalars — run before release"]
fn width_bounds_no_panic_all_scalars() {
    for cp in 0u32..0x0011_0000 {
        let Some(c) = char::from_u32(cp) else {
            continue;
        };
        let mut buf = [0u8; 4];
        let w = grapheme_width(c.encode_utf8(&mut buf));
        assert!(w <= 2, "U+{cp:04X}: width {w} exceeds 2");
    }
}
