use pyo3::prelude::*;
use pyo3::types::PyBytes;

/// Confidence score reported for a successful chardetng detection.
///
/// chardetng's confidence assessment (the old 0.1 `guess_assess` flag) was
/// always `true` for every input — verified against its source and by a
/// differential parity test — so detection always reports this fixed level.
/// The value is chosen to align with chardet/cChardet output ranges so that
/// callers using `min_confidence` thresholds (e.g. 0.7) get intuitive results.
const CONFIDENCE_HIGH: f64 = 0.95;

/// Pure Rust encoding detection — no Python dependency.
///
/// Returns (encoding_name, confidence).
pub fn detect_encoding_impl(bytes: &[u8]) -> (String, f64) {
    use chardetng::{EncodingDetector, Iso2022JpDetection, Utf8Detection};

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
pub fn decode_to_utf8_impl(
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

/// Detect the encoding of a byte sequence.
///
/// Returns a tuple of (encoding_name, confidence) where confidence is
/// a float between 0.0 and 1.0. The encoding name follows WHATWG encoding
/// labels (e.g., "UTF-8", "windows-1252", "Shift_JIS", "EUC-KR").
///
/// Uses the chardetng algorithm (Firefox's encoding detector).
///
/// Important: automatic encoding detection is inherently probabilistic.
/// A high confidence score does NOT guarantee correctness. For critical
/// pipelines, always prefer explicit encoding metadata over detection.
#[pyfunction]
#[pyo3(signature = (data,))]
pub fn _detect_encoding(data: &Bound<'_, PyBytes>) -> (String, f64) {
    detect_encoding_impl(data.as_bytes())
}

/// Decode a byte sequence to UTF-8 using the specified encoding.
///
/// Returns a tuple of (decoded_text, had_errors) where had_errors is True
/// if U+FFFD REPLACEMENT CHARACTERs were inserted during decoding.
///
/// Important: had_errors=False does NOT guarantee lossless conversion.
/// Encodings such as Windows-1252 map every byte to a valid codepoint
/// without inserting U+FFFD, so had_errors will be False even if the
/// decoded text differs from what another encoding would produce.
/// For strict fidelity checks, re-encode the result and compare against
/// the original bytes.
///
/// If encoding is None, uses detect_encoding to guess the encoding.
/// min_confidence (0.0–1.0) sets the minimum acceptable detection confidence
/// when auto-detecting; raises DisarmError if the threshold is not met.
///
/// Supported encodings: all WHATWG encodings (UTF-8, windows-1252,
/// ISO-8859-1, Shift_JIS, EUC-JP, EUC-KR, Big5, GB18030, etc.).
// Default min_confidence requires HIGH confidence (#103): detection always
// reports CONFIDENCE_HIGH (0.95) — chardetng's confidence flag is always true —
// so the 0.95 default accepts every successful auto-detection while still
// letting callers reject auto-detection entirely by passing min_confidence > 0.95
// (e.g. 1.0). Pass min_confidence=0.0 to be explicit about accepting any guess.
#[pyfunction]
#[pyo3(signature = (data, encoding=None, min_confidence=0.95, strict=false))]
pub fn _decode_to_utf8(
    data: &Bound<'_, PyBytes>,
    encoding: Option<&str>,
    min_confidence: f64,
    strict: bool,
) -> PyResult<(String, bool)> {
    decode_to_utf8_impl(data.as_bytes(), encoding, min_confidence, strict)
        .map_err(pyo3::PyErr::from)
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
