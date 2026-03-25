use pyo3::prelude::*;
use pyo3::types::PyBytes;

/// Confidence score returned when chardetng reports high statistical confidence.
const CONFIDENCE_HIGH: f64 = 0.95;
/// Confidence score returned when chardetng reports ambiguous byte distribution.
const CONFIDENCE_LOW: f64 = 0.50;

/// Pure Rust encoding detection — no Python dependency.
///
/// Returns (encoding_name, confidence).
pub fn detect_encoding_impl(bytes: &[u8]) -> (String, f64) {
    let mut detector = chardetng::EncodingDetector::new();
    detector.feed(bytes, true);
    let (encoding, confident) = detector.guess_assess(None, true);

    // chardetng returns a binary confident/not-confident flag, not a
    // continuous score.  We map it to two fixed levels chosen to align
    // with chardet/cChardet output ranges so that callers using
    // min_confidence thresholds (e.g. 0.7) get intuitive results.
    let confidence = if confident { CONFIDENCE_HIGH } else { CONFIDENCE_LOW };

    (encoding.name().to_owned(), confidence)
}

/// Pure Rust byte-to-UTF-8 decoding — no Python dependency.
///
/// Returns `Ok((decoded_text, had_errors))` or `Err(message)`.
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
pub fn decode_to_utf8_impl(
    bytes: &[u8],
    encoding: Option<&str>,
    min_confidence: f64,
) -> Result<(String, bool), String> {
    let enc = match encoding {
        Some(name) => encoding_rs::Encoding::for_label(name.as_bytes())
            .ok_or_else(|| format!("Unknown encoding: '{name}'"))?,
        None => {
            let (name, confidence) = detect_encoding_impl(bytes);
            if confidence < min_confidence {
                return Err(format!(
                    "Encoding detection confidence {confidence:.2} is below the required \
                     minimum {min_confidence:.2} (best guess: '{name}'). \
                     Provide an explicit encoding instead."
                ));
            }
            encoding_rs::Encoding::for_label(name.as_bytes())
                .ok_or_else(|| format!("Auto-detected encoding '{name}' is not supported"))?
        }
    };

    let (decoded, _actual_encoding, had_errors) = enc.decode(bytes);
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
/// when auto-detecting; raises TranslitError if the threshold is not met.
///
/// Supported encodings: all WHATWG encodings (UTF-8, windows-1252,
/// ISO-8859-1, Shift_JIS, EUC-JP, EUC-KR, Big5, GB18030, etc.).
#[pyfunction]
#[pyo3(signature = (data, encoding=None, min_confidence=0.0))]
pub fn _decode_to_utf8(
    data: &Bound<'_, PyBytes>,
    encoding: Option<&str>,
    min_confidence: f64,
) -> PyResult<(String, bool)> {
    decode_to_utf8_impl(data.as_bytes(), encoding, min_confidence)
        .map_err(|e| crate::TranslitError::new_err(e))
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

    #[test]
    fn test_decode_utf8() {
        let (decoded, had_errors) = decode_to_utf8_impl("café".as_bytes(), Some("UTF-8"), 0.0).unwrap();
        assert_eq!(decoded, "café");
        assert!(!had_errors);
    }

    #[test]
    fn test_decode_latin1() {
        // "café" in ISO-8859-1: 63 61 66 E9
        let (decoded, had_errors) =
            decode_to_utf8_impl(&[0x63, 0x61, 0x66, 0xE9], Some("ISO-8859-1"), 0.0).unwrap();
        assert_eq!(decoded, "café");
        assert!(!had_errors);
    }

    #[test]
    fn test_decode_unknown_encoding_errors() {
        let result = decode_to_utf8_impl(b"hello", Some("FAKE-999"), 0.0);
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
        let (decoded, had_errors) = decode_to_utf8_impl(b"hello world", None, 0.0).unwrap();
        assert_eq!(decoded, "hello world");
        assert!(!had_errors);
    }

    #[test]
    fn test_decode_min_confidence_rejected() {
        // detect_encoding_impl returns at most 0.95 (confident) or 0.5 (not).
        // A threshold of 1.0 always rejects auto-detection.
        let result = decode_to_utf8_impl(b"hi", None, 1.0);
        assert!(result.is_err());
        let msg = result.unwrap_err();
        assert!(msg.contains("below the required minimum"), "unexpected: {msg}");
    }

    #[test]
    fn test_decode_min_confidence_accepted() {
        // Explicit encoding ignores min_confidence entirely.
        let result = decode_to_utf8_impl(b"hi", Some("UTF-8"), 1.0);
        assert!(result.is_ok());
    }
}
