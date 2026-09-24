//! `replace_emoji` and `demojize`.
//!
//! Properties (`formal/lean/Emoji`, and the #1011 / #1015 fixes):
//!
//! - `replace_emoji(s, r)` is idempotent for `r` in `" "`, `"#"` and `""`
//!   (`replace_space_idem`, `replace_hash_idem`; for `""`, #1011 closed the seam through
//!   which a removal manufactured a keycap, finding F1). Idempotence also says no emoji
//!   is left behind for a second pass to replace.
//! - `replace_emoji` never touches ASCII-only text, and neither does `demojize` ("pure-ASCII
//!   input is returned unchanged").
//! - Text is never removed (`replace_keeps_text`, over `x . space U+0301 €`). Checked as:
//!   the input's ASCII letters are a subsequence of the output's. Letters, not digits: a
//!   digit is the base of a keycap emoji (`1 U+FE0F U+20E3`), which is replaced whole.
//!
//! Not asserted: `demojize` idempotence, which fails by design on the 38 CLDR names that
//! contain curly quotes (Emoji finding F6: `woman\u{2019}s hat` names its apostrophe on a second
//! pass).
#![no_main]

use disarm::api::{demojize, replace_emoji};
use disarm_fuzz::{is_subsequence, text_and};
use libfuzzer_sys::fuzz_target;

fn letters(s: &str) -> String {
    s.chars().filter(char::is_ascii_alphabetic).collect()
}

fuzz_target!(|data: &[u8]| {
    let Some((s, (strip_modifiers, custom))) = text_and::<(bool, String)>(data) else {
        return;
    };
    for r in [" ", "#", ""] {
        let once = replace_emoji(&s, r);
        assert_eq!(
            replace_emoji(&once, r),
            once,
            "replace_emoji({r:?}) not idempotent on {s:?}"
        );
        assert!(
            is_subsequence(&letters(&s), &letters(&once)),
            "replace_emoji({r:?}) lost text from {s:?}: {once:?}"
        );
    }
    let _ = replace_emoji(&s, &custom);
    let named = demojize(&s, strip_modifiers);
    if s.is_ascii() {
        assert_eq!(named, s);
        assert_eq!(replace_emoji(&s, &custom), s);
    }
});
