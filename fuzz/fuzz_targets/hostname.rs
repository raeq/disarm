//! `is_suspicious_hostname` / `analyze_hostname_with`.
//!
//! Properties (the `HostnameAnalysis` field docs in `src/api/safety.rs`, and H1 of
//! `formal/lean/Sanitizers`):
//!
//! - **H1** `canonical` carries no bidi control and no invisible character of any class
//!   the `has_invisible` doc lists: they are stripped per label before anything else.
//! - Every field the docs say is "folded into `suspicious`" implies it: `mixed_script`,
//!   `has_confusables`, `bidi_conflict`, `bidi_control`, `has_invisible`, `compat_fold`.
//! - The per-label vectors are parallel.
//! - `contractions = false` is `is_suspicious_hostname`.
#![no_main]

use disarm::api::{analyze_hostname_with, has_bidi_control, is_suspicious_hostname};
use disarm_fuzz::text_and;
use libfuzzer_sys::fuzz_target;

/// The `has_invisible` classes, transcribed from its field doc.
fn is_documented_invisible(c: char) -> bool {
    let cp = c as u32;
    matches!(cp,
        0x200B..=0x200D | 0x2060..=0x2064 | 0xFEFF | 0x180E      // zero-width
        | 0xE0000..=0xE007F                                      // tags
        | 0xFE00..=0xFE0F | 0xE0100..=0xE01EF                    // variation selectors
        | 0xFDD0..=0xFDEF                                        // noncharacters
        | 0xE000..=0xF8FF | 0xF0000..=0x10FFFF                   // private use (planes 15-16)
        | 0x00AD | 0x034F | 0x115F..=0x1160 | 0x17B4..=0x17B5    // other default-ignorables
        | 0x180B..=0x180F | 0x206A..=0x206F | 0x3164 | 0xFFA0
        | 0x1BCA0..=0x1BCA3 | 0x1D173..=0x1D17A | 0xFFF0..=0xFFF8 | 0xE0080..=0xE0FFF)
        || (cp & 0xFFFE) == 0xFFFE // the last two of every plane
}

fuzz_target!(|data: &[u8]| {
    let Some((s, contractions)) = text_and::<bool>(data) else {
        return;
    };
    let a = analyze_hostname_with(&s, contractions);

    // H1.
    assert!(
        !has_bidi_control(&a.canonical),
        "bidi control in canonical {:?}",
        a.canonical
    );
    if let Some(c) = a.canonical.chars().find(|&c| is_documented_invisible(c)) {
        panic!(
            "invisible U+{:04X} in canonical {:?} of {s:?}",
            c as u32, a.canonical
        );
    }

    // Folded-in fields imply the verdict.
    let folded = a.mixed_script
        || a.has_confusables
        || a.bidi_conflict
        || a.bidi_control
        || a.has_invisible
        || a.compat_fold;
    assert!(
        !folded || a.suspicious,
        "a folded-in field is set but not suspicious: {a:?}"
    );

    // Parallel per-label vectors.
    assert_eq!(a.label_scripts.len(), a.label_whole_script_confusable.len());
    assert_eq!(
        a.whole_script_confusable,
        a.label_whole_script_confusable.iter().any(|&b| b)
    );

    // The default entry point is `contractions = false`.
    if !contractions {
        assert_eq!(is_suspicious_hostname(&s), a);
    }
});
