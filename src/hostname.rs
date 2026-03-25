use pyo3::prelude::*;
use unicode_normalization::UnicodeNormalization;

use crate::{confusables, scripts};

/// Check if a bracketed string is a valid IPv6 literal per RFC 3986 §3.2.2.
///
/// Requires: starts with '[', ends with ']', content contains ':',
/// only hex digits / colons / dots / '%' (zone ID), and no more than 7 colons.
fn is_ipv6_literal(normalized: &str) -> bool {
    if !(normalized.starts_with('[') && normalized.ends_with(']')) {
        return false;
    }
    let inner = &normalized[1..normalized.len() - 1];
    if inner.is_empty() || !inner.contains(':') {
        return false;
    }
    // Validate colon count on the address portion (before any zone ID).
    let addr_part = match inner.find('%') {
        Some(pos) => &inner[..pos],
        None => inner,
    };
    let colon_count = addr_part.chars().filter(|&c| c == ':').count();
    if colon_count > 7 {
        return false;
    }
    inner
        .as_bytes()
        .iter()
        .all(|&b| b.is_ascii_hexdigit() || b == b':' || b == b'.' || b == b'%')
}

/// Check if a hostname is safe from Unicode homoglyph attacks.
///
/// A hostname is considered unsafe if:
/// - It contains characters from multiple scripts (mixed-script)
///   AND at least one script pair is high-risk (Cyrillic+Latin, Greek+Latin)
/// - It contains confusable characters that map to different Latin characters
///
/// Returns a tuple of (is_safe, details) where details is a dict with:
/// - "safe": bool
/// - "scripts": list of detected scripts
/// - "mixed_script": bool
/// - "has_confusables": bool
/// - "canonical": the Latin-normalized form
///
/// This is a conservative check — it flags anything suspicious rather than
/// trying to determine benign intent.
#[pyfunction]
#[pyo3(signature = (hostname,))]
pub fn _is_safe_hostname(hostname: &str) -> PyResult<(bool, SafeHostnameDetails)> {
    // 1. NFKC normalize
    let normalized: String = hostname.nfkc().collect();

    // IPv6 literals (e.g. "[::1]", "[2001:db8::1]") are not IDN hostnames and
    // cannot be visually spoofed via homoglyph attacks. Return them as safe
    // without running the script/confusable analysis.
    if is_ipv6_literal(&normalized) {
        return Ok((
            true,
            SafeHostnameDetails {
                safe: true,
                scripts: Vec::new(),
                mixed_script: false,
                has_confusables: false,
                canonical: normalized,
            },
        ));
    }

    // 2. Split on dots to check each label
    let mut overall_safe = true;
    let mut all_scripts: Vec<&str> = Vec::new();
    let mut seen_scripts: std::collections::HashSet<&str> = std::collections::HashSet::new();
    let mut has_mixed = false;
    let mut has_confusables = false;

    for label in normalized.split('.') {
        // Empty labels arise from leading, trailing, or consecutive dots
        // (e.g. "a..b" or "example.com.").  These are structurally
        // malformed but not a homoglyph attack vector — skip them.
        if label.is_empty() {
            continue;
        }

        // Check scripts in this label
        let label_scripts = scripts::_detect_scripts(label);

        // Track all scripts seen (O(1) dedup via HashSet)
        for s in &label_scripts {
            if seen_scripts.insert(s) {
                all_scripts.push(s);
            }
        }

        // Mixed-script within a single label is suspicious
        if label_scripts.len() > 1 {
            has_mixed = true;

            // High-risk script combinations (visually confusable with Latin).
            const HIGH_RISK_PAIRS: &[(&str, &str)] = &[
                ("Cyrillic", "Latin"),
                ("Greek", "Latin"),
                ("Armenian", "Latin"),
            ];

            let script_set: std::collections::HashSet<&str> =
                label_scripts.iter().copied().collect();

            for &(a, b) in HIGH_RISK_PAIRS {
                if script_set.contains(a) && script_set.contains(b) {
                    overall_safe = false;
                }
            }
        }

        // Check confusables in this label
        if confusables::_is_confusable(label, "latin").unwrap_or(false) {
            has_confusables = true;
            overall_safe = false;
        }
    }

    // Generate canonical Latin form
    let canonical = confusables::_normalize_confusables(&normalized, "latin")
        .unwrap_or_else(|_| normalized.clone());

    Ok((
        overall_safe,
        SafeHostnameDetails {
            safe: overall_safe,
            scripts: all_scripts.into_iter().map(String::from).collect(),
            mixed_script: has_mixed,
            has_confusables,
            canonical,
        },
    ))
}

/// Details from hostname safety check.
#[pyclass]
#[pyo3(name = "SafeHostnameDetails")]
#[derive(Clone)]
pub struct SafeHostnameDetails {
    #[pyo3(get)]
    pub safe: bool,
    #[pyo3(get)]
    pub scripts: Vec<String>,
    #[pyo3(get)]
    pub mixed_script: bool,
    #[pyo3(get)]
    pub has_confusables: bool,
    #[pyo3(get)]
    pub canonical: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_safe_hostname() {
        let (safe, details) = _is_safe_hostname("paypal.com").unwrap();
        assert!(safe);
        assert!(!details.has_confusables);
        assert!(!details.mixed_script);
    }

    #[test]
    fn test_cyrillic_spoof() {
        // Cyrillic а and р mixed with Latin
        let (safe, details) = _is_safe_hostname("\u{0440}\u{0430}ypal.com").unwrap();
        assert!(!safe);
        assert!(details.has_confusables);
        assert!(details.mixed_script);
        assert_eq!(details.canonical, "paypal.com");
    }

    #[test]
    fn test_full_cyrillic_domain() {
        // Fully Cyrillic domain — not mixed script, might have confusables
        let (_, details) = _is_safe_hostname("яндекс.ру").unwrap();
        assert!(!details.mixed_script);
    }

    #[test]
    fn test_punycode_safe() {
        // Pure ASCII punycode is safe
        let (safe, _) = _is_safe_hostname("xn--n3h.com").unwrap();
        assert!(safe);
    }

    #[test]
    fn test_ipv6_loopback_safe() {
        let (safe, details) = _is_safe_hostname("[::1]").unwrap();
        assert!(safe);
        assert!(!details.mixed_script);
        assert!(!details.has_confusables);
    }

    #[test]
    fn test_ipv6_full_safe() {
        let (safe, details) = _is_safe_hostname("[2001:db8::1]").unwrap();
        assert!(safe);
        assert!(details.scripts.is_empty());
    }
}
