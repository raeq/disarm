//! `decode_to_utf8` and `detect_encoding` over arbitrary bytes: the most parser-shaped
//! surface in the library, and the one that takes untrusted bytes directly.
//!
//! Input layout: the first byte selects the options, the rest is the payload.
//!
//! - bits 0-4: the label — `None` (auto-detect) for 0, else an index into [`LABELS`]
//! - bit 5: `strict`
//! - bits 6-7: `min_confidence` — 0.0, 0.5, 1.0, or out of range
//!
//! Properties (docstrings of `decode_to_utf8` / `detect_encoding` in
//! `src/api/safety.rs`, and the #710 and #1026 fixes):
//!
//! 1. `min_confidence` outside `0.0..=1.0` is always an error.
//! 2. `detect_encoding`'s confidence is in `0.0..=1.0`.
//! 3. Strict mode errors instead of substituting: a strict decode succeeds exactly when
//!    the lenient decode of the same bytes reports no errors, and then yields the same
//!    text with `had_errors == false`.
//! 4. Auto-detection agrees with decoding under the label it detected (#710: the two
//!    agree by construction, BOM included). Checked at `min_confidence = 0.0`, where
//!    auto-detection cannot refuse.
//! 5. An explicit `utf-8` label decodes valid UTF-8 to itself (less its own BOM), and
//!    reports errors on anything else — a UTF-16 BOM included (#1026, finding 14).
//! 6. An unknown label is an error, never a silent fallback.
#![no_main]

use disarm::api::{decode_to_utf8, detect_encoding};
use libfuzzer_sys::fuzz_target;

/// Labels worth reaching in one byte: every UTF-16 spelling (the BOM rules differ per
/// label), the single-byte and multi-byte encodings chardetng can report, WHATWG aliases,
/// the `replacement` encoding, and two labels that do not exist.
const LABELS: &[&str] = &[
    "utf-8",
    "UTF-8",
    "utf8",
    "utf-16",
    "utf-16le",
    "utf-16be",
    "unicode",
    "ucs-2",
    "windows-1252",
    "iso-8859-1",
    "latin1",
    "ascii",
    "windows-1251",
    "koi8-r",
    "koi8-u",
    "iso-8859-7",
    "windows-1255",
    "windows-1256",
    "shift_jis",
    "euc-jp",
    "iso-2022-jp",
    "gbk",
    "gb18030",
    "big5",
    "euc-kr",
    "x-user-defined",
    "replacement",
    "iso-2022-kr",
    "not-an-encoding",
    "",
    "utf-7",
];

fn confidence(bits: u8) -> f64 {
    match bits {
        0 => 0.0,
        1 => 0.5,
        2 => 1.0,
        _ => f64::NAN,
    }
}

fuzz_target!(|data: &[u8]| {
    let Some((&mode, bytes)) = data.split_first() else {
        return;
    };
    let label_index = usize::from(mode & 0x1F);
    let label = label_index.checked_sub(1).map(|i| LABELS[i % LABELS.len()]);
    let strict = mode & 0x20 != 0;
    let min_confidence = confidence(mode >> 6);

    // 1. An out-of-range threshold is refused whatever else is passed.
    for bad in [-0.1, 1.5, f64::NAN, f64::INFINITY] {
        assert!(decode_to_utf8(bytes, label, bad, strict).is_err());
    }

    // 2.
    let detected = detect_encoding(bytes);
    assert!(
        (0.0..=1.0).contains(&detected.confidence),
        "confidence {} out of range",
        detected.confidence
    );

    // The call the input asked for: no panic, and a valid result when it succeeds.
    let asked = decode_to_utf8(bytes, label, min_confidence, strict);
    if min_confidence.is_nan() {
        assert!(asked.is_err());
    }
    if let Ok(d) = &asked {
        if strict {
            assert!(
                !d.had_errors,
                "strict decode reported errors instead of failing"
            );
        }
    }

    // 3. Strict against lenient, same label, a threshold that cannot refuse.
    let lenient = decode_to_utf8(bytes, label, 0.0, false);
    let strict_res = decode_to_utf8(bytes, label, 0.0, true);
    match (&lenient, &strict_res) {
        (Ok(l), Ok(s)) => {
            assert!(!l.had_errors, "strict succeeded where lenient substituted");
            assert_eq!(l.text, s.text);
            assert!(!s.had_errors);
        }
        (Ok(l), Err(_)) => assert!(l.had_errors, "strict failed on a clean decode"),
        (Err(_), Ok(_)) => panic!("lenient failed where strict succeeded"),
        (Err(_), Err(_)) => {}
    }

    // 4. Auto-detection == decoding under the detected label.
    let auto = decode_to_utf8(bytes, None, 0.0, false).expect("auto-detect at 0.0 cannot refuse");
    let relabelled = decode_to_utf8(bytes, Some(&detected.label), 0.0, false)
        .expect("the detected label is a known label");
    assert_eq!(
        (&auto.text, auto.had_errors),
        (&relabelled.text, relabelled.had_errors),
        "auto-detect ({}) and the explicit detected label disagree",
        detected.label
    );

    // 5. Explicit UTF-8 is exactly UTF-8.
    let utf8 = decode_to_utf8(bytes, Some("utf-8"), 0.0, false).expect("utf-8 is a known label");
    match std::str::from_utf8(bytes) {
        Ok(s) => {
            assert!(!utf8.had_errors);
            assert_eq!(utf8.text, s.strip_prefix('\u{FEFF}').unwrap_or(s));
        }
        Err(_) => assert!(utf8.had_errors, "invalid UTF-8 decoded without errors"),
    }

    // 6. Unknown labels are errors.
    for unknown in ["not-an-encoding", "", "utf-7"] {
        assert!(decode_to_utf8(bytes, Some(unknown), 0.0, false).is_err());
    }
});
