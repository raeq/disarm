//! Layer 1 (pure-Rust core): encoding detection + decoding. No pyo3.
//!
//! Shims in `src/py/encoding.rs`; crates.io surface is
//! `crate::api::{detect_encoding, decode_to_utf8}`.

/// Confidence score reported for a successful chardetng detection.
///
/// chardetng's confidence assessment (the old 0.1 `guess_assess` flag) was
/// always `true` for every input — verified against its source and by a
/// differential parity test — so detection always reports this fixed level.
/// The value is chosen to align with chardet/cChardet output ranges so that
/// callers using `min_confidence` thresholds (e.g. 0.7) get intuitive results.
const CONFIDENCE_HIGH: f64 = 0.95;

/// BOM-less UTF-16 over ASCII-range text (#710 §3).
///
/// In UTF-16 every ASCII character is one NUL byte plus the ASCII byte, and which of the
/// two positions holds the NUL is the endianness: `41 00 42 00` is little-endian, `00 41
/// 00 42` big-endian. That is a deterministic pattern, not a frequency guess, and
/// chardetng never produces a UTF-16 label at all, so nothing else in the pipeline can
/// see it. BOM-less UTF-16 is what Windows tooling and several DB exports emit, and the
/// consequence was not a wrong label but a wrong *decode*:
/// `decode_to_utf8("héllo".encode("utf-16-le"))` returned `'h\0é\0l\0l\0o\0'` with
/// `had_errors = false`, and `strict = true` did not catch it.
///
/// Deliberately conservative, because a false positive turns working text into garbage:
///
/// - Even length and at least two code units. An odd length is not UTF-16 at all.
/// - One position must be at least `MIN_NUL_FRACTION` NUL and the other **exactly zero**.
///   Text in a single-byte encoding contains no NUL anywhere — it is a C0 control — so any
///   split at all is evidence; requiring the clean side to be empty is what keeps a binary
///   blob from being read as text. The fraction is the weaker half of the rule and is
///   named rather than spelled out in prose, so it cannot drift out of step with the
///   constant (it did: the comment said 90% after the constant moved to 0.5).
///
/// `MIN_NUL_FRACTION` is what limits this to the ASCII range, and that limit is real: in
/// UTF-16LE Cyrillic the high byte is `04`, not `00`, so `"Привет"` without a BOM carries
/// no NUL and stays undetected. Documented on both surfaces rather than papered over —
/// widening it would mean guessing from script frequency, which is the ambiguous-bytes
/// case `THREAT_MODEL.md` scopes out.
fn sniff_bomless_utf16(bytes: &[u8]) -> Option<&'static encoding_rs::Encoding> {
    const MIN_NUL_FRACTION: f64 = 0.5;
    if bytes.len() < 4 || bytes.len() % 2 != 0 {
        return None;
    }
    let (mut even_nuls, mut odd_nuls) = (0usize, 0usize);
    for (i, b) in bytes.iter().enumerate() {
        if *b == 0 {
            if i % 2 == 0 {
                even_nuls += 1;
            } else {
                odd_nuls += 1;
            }
        }
    }
    let units = bytes.len() / 2;
    #[allow(clippy::cast_precision_loss)] // counts are bounded by the input length
    let floor = MIN_NUL_FRACTION * units as f64;
    #[allow(clippy::cast_precision_loss)]
    match (even_nuls == 0, odd_nuls == 0) {
        // NUL in the high position of each unit: big-endian.
        (false, true) if even_nuls as f64 >= floor => Some(encoding_rs::UTF_16BE),
        // NUL in the low position: little-endian.
        (true, false) if odd_nuls as f64 >= floor => Some(encoding_rs::UTF_16LE),
        _ => None,
    }
}

/// Pure Rust encoding detection — no Python dependency.
///
/// Returns (encoding_name, confidence).
pub(crate) fn detect_encoding_impl(bytes: &[u8]) -> (String, f64) {
    use chardetng::{EncodingDetector, Iso2022JpDetection, Utf8Detection};

    // #710 §1: a BOM is not a probabilistic signal, and chardetng does not guess UTF-16
    // at all — so `detect_encoding` could not return a UTF-16 label for any input, and
    // reported `KOI8-U` at confidence 0.95 for UTF-16LE-with-BOM while `decode_to_utf8`
    // returned the correct text from the same bytes. The two disagreed silently, and a
    // caller following this function's own advice — "prefer explicit encoding metadata
    // over detection" — carried the wrong label to another decoder and got mojibake.
    //
    // `Encoding::for_bom` is the WHATWG sniff `Encoding::decode` already performs
    // internally, so using it here makes the two functions agree by construction rather
    // than by a second implementation that could drift.
    if let Some((encoding, _bom_len)) = encoding_rs::Encoding::for_bom(bytes) {
        return (encoding.name().to_owned(), CONFIDENCE_HIGH);
    }
    if let Some(encoding) = sniff_bomless_utf16(bytes) {
        return (encoding.name().to_owned(), CONFIDENCE_HIGH);
    }

    // chardetng 1.0 split `guess_assess` into `guess` (encoding only). We pass
    // the permissive options that match the old `guess_assess(None, true)`
    // behaviour: this is a general-purpose text library (not a script-running
    // web browser), so UTF-8 and ISO-2022-JP are both allowed as guesses.
    let mut detector = EncodingDetector::new(Iso2022JpDetection::Allow);
    detector.feed(bytes, true);
    let encoding = detector.guess(None, Utf8Detection::Allow);

    // The old `guess_assess` returned a binary confident flag. We verified
    // against chardetng 0.1's source that this flag was `max >= 0` where `max`
    // is initialised to 0 and only ever increases — so the general path was
    // ALWAYS confident — plus two unconditional-true shortcuts (UTF-8 and
    // ISO-2022-JP). A differential parity test against the 0.1.x detector confirmed
    // the flag is `true` for every input. We therefore report CONFIDENCE_HIGH
    // unconditionally, reproducing 0.1.x output exactly, and avoid depending on
    // 1.0's `find_score` API (gated behind an explicitly unstable feature).
    (encoding.name().to_owned(), CONFIDENCE_HIGH)
}

/// Common encoding labels offered as "did you mean …?" hints for an unrecognised
/// label (#186). Not exhaustive — encoding_rs accepts ~220 labels — just the
/// canonical names a typo is most likely aimed at.
const COMMON_ENCODING_LABELS: &[&str] = &[
    "utf-8",
    "utf-16le",
    "utf-16be",
    "windows-1250",
    "windows-1251",
    "windows-1252",
    "windows-1254",
    "iso-8859-1",
    "iso-8859-2",
    "iso-8859-15",
    "koi8-r",
    "koi8-u",
    "shift_jis",
    "euc-jp",
    "iso-2022-jp",
    "euc-kr",
    "big5",
    "gbk",
    "gb18030",
    "macintosh",
];

/// Pure Rust byte-to-UTF-8 decoding — no Python dependency.
///
/// Returns `Ok((decoded_text, had_errors))` or a [`crate::ErrorRepr`].
///
/// `had_errors` reflects encoding_rs's WHATWG-defined error flag: it is
/// `true` only when a U+FFFD REPLACEMENT CHARACTER was inserted because a
/// byte sequence could not be decoded.  It is **not** a general fidelity
/// guarantee — some encodings (e.g. Windows-1252) remap every byte to a
/// valid Unicode codepoint without inserting U+FFFD, so `had_errors` will
/// be `false` even if the result differs from what another encoding would
/// produce.  Callers that require lossless round-trip guarantees should
/// compare the re-encoded output against the original bytes rather than
/// relying solely on this flag.
///
/// When `encoding` is `None` the encoding is auto-detected. If the
/// detection confidence is below `min_confidence` an error is returned
/// so the caller can require a minimum quality threshold.
///
/// In `strict` mode (#189) a lossy decode — malformed bytes replaced with U+FFFD
/// — is a hard error rather than a silent `had_errors = true` the caller might
/// ignore.
pub(crate) fn decode_to_utf8_impl(
    bytes: &[u8],
    encoding: Option<&str>,
    min_confidence: f64,
    strict: bool,
) -> Result<(String, bool), crate::ErrorRepr> {
    // Validate the [0.0, 1.0] contract here in the core, not only in the
    // `_api.py` wrapper: the raw `_decode_to_utf8` PyO3 function is importable
    // and callable directly, bypassing that wrapper, so a wrapper-only check
    // would leave it unguarded. The core is the single place every caller
    // crosses. The check is unconditional — an out-of-range threshold is a
    // caller mistake even when an explicit `encoding` means it is never used as
    // a detection threshold. NaN is rejected too: `(0.0..=1.0).contains(&NaN)`
    // is false, so the negation below is true.
    if !(0.0..=1.0).contains(&min_confidence) {
        return Err(crate::ErrorRepr::MinConfidenceOutOfRange { min_confidence });
    }
    let enc = if let Some(name) = encoding {
        encoding_rs::Encoding::for_label(name.as_bytes()).ok_or_else(|| {
            // "did you mean …?" against the common labels (#186); encoding_rs
            // does not enumerate its ~220 accepted labels, so we hint from the
            // popular subset a typo most likely targets.
            let suggestion =
                crate::utils::closest_match(name, COMMON_ENCODING_LABELS.iter().copied())
                    .map(|s| format!(" (did you mean '{s}'?)"))
                    .unwrap_or_default();
            crate::ErrorRepr::UnknownEncoding {
                got: name.to_owned(),
                suggestion,
            }
        })?
    } else {
        let (name, confidence) = detect_encoding_impl(bytes);
        if confidence < min_confidence {
            return Err(crate::ErrorRepr::EncodingConfidenceTooLow {
                confidence,
                min_confidence,
                guess: name,
            });
        }
        encoding_rs::Encoding::for_label(name.as_bytes())
            .ok_or(crate::ErrorRepr::UnsupportedAutoEncoding { got: name })?
    };

    let (decoded, actual_encoding, had_errors) = enc.decode(bytes);
    // #189: in strict mode a lossy decode (malformed sequences replaced with
    // U+FFFD) is a hard error, not a silent success the caller might ignore.
    if strict && had_errors {
        return Err(crate::ErrorRepr::LossyDecode {
            encoding: actual_encoding.name().to_owned(),
        });
    }
    Ok((decoded.into_owned(), had_errors))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detect_utf8() {
        let (encoding, confidence) = detect_encoding_impl(b"hello world");
        assert!(encoding == "windows-1252" || encoding == "UTF-8");
        assert!(confidence > 0.0);
    }

    #[test]
    fn test_detect_utf8_with_bom() {
        let (encoding, _) = detect_encoding_impl(b"\xef\xbb\xbfhello");
        assert_eq!(encoding, "UTF-8");
    }

    /// #710: chardetng never produces a UTF-16 label, so a BOM has to be read first.
    /// `detect_encoding` reported `KOI8-U` at confidence 0.95 for the first row while
    /// `decode_to_utf8` read the same bytes correctly.
    #[test]
    fn test_detect_utf16_bom() {
        // "hi" in each, with the BOM.
        let le: &[u8] = &[0xFF, 0xFE, b'h', 0, b'i', 0];
        let be: &[u8] = &[0xFE, 0xFF, 0, b'h', 0, b'i'];
        assert_eq!(detect_encoding_impl(le).0, "UTF-16LE");
        assert_eq!(detect_encoding_impl(be).0, "UTF-16BE");
    }

    /// #710 §3: BOM-less UTF-16 over ASCII-range text, where the NUL position is the
    /// endianness. The harm was not the label but the decode — `decode_to_utf8` returned
    /// a NUL after every character with `had_errors = false`, and `strict` did not catch
    /// it.
    #[test]
    fn test_detect_bomless_utf16_over_ascii() {
        assert_eq!(detect_encoding_impl(b"h\0e\0l\0l\0o\0").0, "UTF-16LE");
        assert_eq!(detect_encoding_impl(b"\0h\0e\0l\0l\0o").0, "UTF-16BE");
    }

    /// The clean side must be EXACTLY zero, which is what keeps real text out: a
    /// single-byte encoding never emits a NUL, so any split at all is evidence.
    #[test]
    fn test_bomless_sniff_rejects_the_ambiguous_cases() {
        // NULs at both parities: not a UTF-16 text pattern.
        assert!(sniff_bomless_utf16(b"\0\0\0\0\0\0").is_none());
        // Odd length cannot be UTF-16 at all.
        assert!(sniff_bomless_utf16(b"h\0e\0l").is_none());
        // Under two code units there is no pattern to read.
        assert!(sniff_bomless_utf16(b"h\0").is_none());
        // Ordinary text carries no NUL, so neither side can win.
        assert!(sniff_bomless_utf16(b"hello world").is_none());
        // Below the half-NUL floor: one ASCII character in four units.
        assert!(sniff_bomless_utf16(b"h\0\x04\x1f\x04@\x048").is_none());
    }

    /// Regression pins for the chardetng 0.1 -> 1.0 migration (#164). These
    /// expectations were captured from a differential parity test that compared
    /// the new `guess`/`CONFIDENCE_HIGH` mechanism against the old
    /// `guess_assess(None, true)` across a broad differential corpus (zero divergences).
    /// Confidence is always CONFIDENCE_HIGH (0.95) because chardetng's
    /// confidence flag is always true.
    #[test]
    fn test_detect_regression_pins() {
        let cases: &[(&[u8], &str)] = &[
            // UTF-8 multibyte sequence: "日本語" — hits the UTF-8 shortcut.
            (
                &[0xE6, 0x97, 0xA5, 0xE6, 0x9C, 0xAC, 0xE8, 0xAA, 0x9E],
                "UTF-8",
            ),
            // ISO-2022-JP with ESC sequences: ESC$B 日本 ESC(B.
            (
                &[0x1B, 0x24, 0x42, 0x46, 0x7C, 0x4B, 0x5C, 0x1B, 0x28, 0x42],
                "ISO-2022-JP",
            ),
            // Shift_JIS: "こんにちは世界".
            (
                &[
                    0x82, 0xB1, 0x82, 0xF1, 0x82, 0xC9, 0x82, 0xBF, 0x82, 0xCD, 0x90, 0xA2, 0x8A,
                    0x45,
                ],
                "Shift_JIS",
            ),
        ];
        for (bytes, expected) in cases {
            let (encoding, confidence) = detect_encoding_impl(bytes);
            assert_eq!(&encoding, expected, "encoding mismatch for {bytes:02x?}");
            assert!(
                (confidence - super::CONFIDENCE_HIGH).abs() < 1e-9,
                "confidence should always be CONFIDENCE_HIGH, got {confidence}"
            );
        }
    }

    #[test]
    fn test_decode_utf8() {
        let (decoded, had_errors) =
            decode_to_utf8_impl("café".as_bytes(), Some("UTF-8"), 0.0, false).unwrap();
        assert_eq!(decoded, "café");
        assert!(!had_errors);
    }

    #[test]
    fn test_decode_latin1() {
        // "café" in ISO-8859-1: 63 61 66 E9
        let (decoded, had_errors) =
            decode_to_utf8_impl(&[0x63, 0x61, 0x66, 0xE9], Some("ISO-8859-1"), 0.0, false).unwrap();
        assert_eq!(decoded, "café");
        assert!(!had_errors);
    }

    #[test]
    fn test_decode_unknown_encoding_errors() {
        let result = decode_to_utf8_impl(b"hello", Some("FAKE-999"), 0.0, false);
        assert!(result.is_err());
    }

    #[test]
    fn test_detect_empty_input() {
        let (encoding, confidence) = detect_encoding_impl(b"");
        assert!(!encoding.is_empty());
        assert!(confidence > 0.0);
    }

    #[test]
    fn test_decode_auto_detect() {
        let (decoded, had_errors) = decode_to_utf8_impl(b"hello world", None, 0.0, false).unwrap();
        assert_eq!(decoded, "hello world");
        assert!(!had_errors);
    }

    #[test]
    fn test_decode_min_confidence_rejected() {
        // detect_encoding_impl always returns 0.95 (CONFIDENCE_HIGH).
        // A threshold of 1.0 always rejects auto-detection.
        let result = decode_to_utf8_impl(b"hi", None, 1.0, false);
        assert!(result.is_err());
        let msg = result.unwrap_err().to_string();
        assert!(
            msg.contains("below the required minimum"),
            "unexpected: {msg}"
        );
    }

    #[test]
    fn test_decode_min_confidence_accepted() {
        // Explicit encoding ignores min_confidence entirely.
        let result = decode_to_utf8_impl(b"hi", Some("UTF-8"), 1.0, false);
        assert!(result.is_ok());
    }

    #[test]
    fn test_decode_min_confidence_out_of_range_rejected() {
        // The range contract is enforced in decode_to_utf8_impl itself, so it
        // holds for the raw `_decode_to_utf8` PyO3 entrypoint too — not just the
        // `_api.py` wrapper. Rejected below 0, above 1, for NaN, and even when an
        // explicit encoding means the value is never used as a detection
        // threshold — an out-of-range threshold is a caller mistake either way.
        for bad in [-0.5_f64, 1.5, f64::NAN, -0.000_001, 1.000_001] {
            let auto = decode_to_utf8_impl(b"hi", None, bad, false);
            let explicit = decode_to_utf8_impl(b"hi", Some("UTF-8"), bad, false);
            for r in [auto, explicit] {
                assert!(
                    matches!(r, Err(crate::ErrorRepr::MinConfidenceOutOfRange { .. })),
                    "min_confidence {bad} should be rejected by the core"
                );
            }
        }
        // The valid boundaries remain accepted.
        assert!(decode_to_utf8_impl(b"hi", Some("UTF-8"), 0.0, false).is_ok());
        assert!(decode_to_utf8_impl(b"hi", Some("UTF-8"), 1.0, false).is_ok());
    }
}
