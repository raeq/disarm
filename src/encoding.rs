use pyo3::prelude::*;
use pyo3::types::PyBytes;

/// Pure Rust encoding detection — no Python dependency.
///
/// Returns (encoding_name, confidence).
pub fn detect_encoding_impl(bytes: &[u8]) -> (String, f64) {
    let mut detector = chardetng::EncodingDetector::new();
    detector.feed(bytes, true);
    let (encoding, confident) = detector.guess_assess(None, true);

    let confidence = if confident { 0.95 } else { 0.5 };

    (encoding.name().to_owned(), confidence)
}

/// Pure Rust byte-to-UTF-8 decoding — no Python dependency.
///
/// Returns `Ok((decoded_text, had_errors))` or `Err(message)`.
pub fn decode_to_utf8_impl(bytes: &[u8], encoding: Option<&str>) -> Result<(String, bool), String> {
    let enc = match encoding {
        Some(name) => encoding_rs::Encoding::for_label(name.as_bytes())
            .ok_or_else(|| format!("Unknown encoding: '{name}'"))?,
        None => {
            let mut detector = chardetng::EncodingDetector::new();
            detector.feed(bytes, true);
            let (detected, _) = detector.guess_assess(None, true);
            detected
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
/// if any characters were replaced during decoding (lossy conversion).
///
/// If encoding is None, uses detect_encoding to guess the encoding.
///
/// Supported encodings: all WHATWG encodings (UTF-8, windows-1252,
/// ISO-8859-1, Shift_JIS, EUC-JP, EUC-KR, Big5, GB18030, etc.).
#[pyfunction]
#[pyo3(signature = (data, encoding=None))]
pub fn _decode_to_utf8(
    data: &Bound<'_, PyBytes>,
    encoding: Option<&str>,
) -> PyResult<(String, bool)> {
    decode_to_utf8_impl(data.as_bytes(), encoding).map_err(|e| crate::TranslitError::new_err(e))
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
        let (decoded, had_errors) = decode_to_utf8_impl("café".as_bytes(), Some("UTF-8")).unwrap();
        assert_eq!(decoded, "café");
        assert!(!had_errors);
    }

    #[test]
    fn test_decode_latin1() {
        // "café" in ISO-8859-1: 63 61 66 E9
        let (decoded, had_errors) =
            decode_to_utf8_impl(&[0x63, 0x61, 0x66, 0xE9], Some("ISO-8859-1")).unwrap();
        assert_eq!(decoded, "café");
        assert!(!had_errors);
    }

    #[test]
    fn test_decode_unknown_encoding_errors() {
        let result = decode_to_utf8_impl(b"hello", Some("FAKE-999"));
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
        let (decoded, had_errors) = decode_to_utf8_impl(b"hello world", None).unwrap();
        assert_eq!(decoded, "hello world");
        assert!(!had_errors);
    }
}
