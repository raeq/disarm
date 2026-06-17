use unicode_normalization::UnicodeNormalization;

use crate::{confusables, scripts};

/// Check if a bracketed string is a valid IPv6 literal per RFC 3986 §3.2.2.
///
/// Requires: starts with `[`, ends with `]`, content contains `:`,
/// only hex digits / colons / dots / `%` (zone ID), and no more than 7 colons.
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
    // A valid literal has at most one zone-ID delimiter (`%`); more than one is
    // malformed. Bounding it keeps a crafted `[::1%a%b...]` from being waved
    // through as an IP and thereby skipping homoglyph analysis. (C5)
    if inner.bytes().filter(|&b| b == b'%').count() > 1 {
        return false;
    }
    inner
        .as_bytes()
        .iter()
        .all(|&b| b.is_ascii_hexdigit() || b == b':' || b == b'.' || b == b'%')
}

/// Findings from a hostname homoglyph analysis.
///
/// Reports factual findings; it claims nothing about absolute safety. A
/// `suspicious == false` result is not a safety certificate (see
/// [`is_suspicious_hostname`]).
#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct HostnameAnalysis {
    /// Whether the hostname is flagged suspicious overall.
    pub(crate) suspicious: bool,
    /// Scripts detected across all labels, in order of first appearance.
    pub(crate) scripts: Vec<String>,
    /// Whether any single label mixes characters from more than one script.
    pub(crate) mixed_script: bool,
    /// Whether any label contains a confusable mapping to a Latin character.
    pub(crate) has_confusables: bool,
    /// Whether the decoded hostname mixes strong LTR and strong RTL characters
    /// (Bidi-reorder / "BiDi Swap" precondition). Folded into `suspicious`.
    pub(crate) bidi_conflict: bool,
    /// Whether the labels span more than one distinct script (Common/Inherited
    /// excluded). Broader than `bidi_conflict`; NOT folded into `suspicious`.
    pub(crate) cross_label_script: bool,
    /// Per-label resolved scripts, left to right (Common/Inherited excluded).
    pub(crate) label_scripts: Vec<Vec<String>>,
    /// The Latin-normalized (canonical) form of the hostname.
    pub(crate) canonical: String,
}

/// Detect whether a hostname is *suspicious* for Unicode homoglyph spoofing.
///
/// `xn--` (ACE) labels are decoded to their Unicode form via UTS#46 before
/// analysis, so the on-the-wire IDN homograph attack is examined rather than
/// passed through as inert ASCII (#63). A malformed ACE label is treated as
/// suspicious (fail closed).
///
/// A hostname is flagged **suspicious** if:
/// - Any single label contains characters from more than one script
///   (mixed-script), excluding Common/Inherited (digits, punctuation,
///   combining marks). This is conservative and fails closed (#254): it flags
///   benign combinations (e.g. Latin + CJK) as well as spoofing ones — a caller
///   wanting a more permissive policy can inspect the `mixed_script`/`scripts`
///   fields.
/// - It contains confusable characters that map to different Latin characters
/// - The decoded hostname mixes strong left-to-right and strong right-to-left
///   characters (`bidi_conflict`, #412) — the "BiDi Swap" reorder precondition,
///   which `mixed_script` misses because the mixing is *across* labels. The
///   broader `cross_label_script` fact is exposed but deliberately NOT folded in
///   (it fires on benign IDN ccTLDs like `google.рф`).
/// - An ACE label fails to decode, or a confusable check errors (fail closed)
///
/// Returns a tuple of (is_suspicious, analysis).
///
/// **A `false` (not-suspicious) result is NOT a safety guarantee.** It means
/// only that no mixed-script label and no confusable *from the bundled TR39
/// table* was found. Per the THREAT_MODEL *Out of scope* section, whole-script
/// spoofs that use no bundled-table confusable, and any confusable outside the
/// bundled table, are not detected and will report not-suspicious. Base allow/
/// deny decisions on the granular `scripts` / `mixed_script` / `has_confusables`
/// fields plus your own policy — a detector can attest the *presence* of a
/// problem, never the *absence* of all problems.
pub(crate) fn is_suspicious_hostname(hostname: &str) -> (bool, HostnameAnalysis) {
    // 1. NFKC normalize
    let normalized: String = hostname.nfkc().collect();

    // IPv6 literals (e.g. "[::1]", "[2001:db8::1]") are not IDN hostnames and
    // cannot be visually spoofed via homoglyph attacks. Report them as
    // not-suspicious without running the script/confusable analysis.
    if is_ipv6_literal(&normalized) {
        return (
            false,
            HostnameAnalysis {
                suspicious: false,
                scripts: Vec::new(),
                mixed_script: false,
                has_confusables: false,
                bidi_conflict: false,
                cross_label_script: false,
                label_scripts: Vec::new(),
                canonical: normalized,
            },
        );
    }

    // 2. Split on dots to check each label
    let mut suspicious = false;
    let mut all_scripts: Vec<&str> = Vec::new();
    let mut seen_scripts: std::collections::HashSet<&str> = std::collections::HashSet::new();
    let mut has_mixed = false;
    let mut has_confusables = false;
    let mut decoded_labels: Vec<String> = Vec::new();
    let mut per_label_scripts: Vec<Vec<String>> = Vec::new();

    for raw_label in normalized.split('.') {
        // Empty labels arise from leading, trailing, or consecutive dots
        // (e.g. "a..b" or "example.com.").  These are structurally
        // malformed but not a homoglyph attack vector — skip them (but keep a
        // placeholder so the canonical form preserves dot structure).
        if raw_label.is_empty() {
            decoded_labels.push(String::new());
            per_label_scripts.push(Vec::new());
            continue;
        }

        // Decode `xn--` ACE labels to their Unicode form (UTS#46, #63) so the
        // on-the-wire IDN homograph attack is analysed instead of passing as
        // inert ASCII. A malformed ACE label cannot be verified → fail closed.
        // `raw_label` here is *not yet known* to be ACE — it may be a non-ASCII
        // Unicode label — so a byte slice `raw_label[..4]` could fall mid-codepoint
        // and panic; the byte-prefix compare never can, and real ACE labels are
        // pure ASCII so it matches exactly. `>= 4` (not `> 4`) keeps a bare,
        // malformed `"xn--"` recognised as ACE and routed through the fail-closed
        // decode below rather than slipping past as an inert ASCII label.
        let is_ace =
            raw_label.len() >= 4 && raw_label.as_bytes()[..4].eq_ignore_ascii_case(b"xn--");
        let label: String = if is_ace {
            let (unicode, result) = idna::domain_to_unicode(raw_label);
            if result.is_err() {
                suspicious = true;
            }
            unicode.nfkc().collect()
        } else {
            raw_label.to_string()
        };
        decoded_labels.push(label.clone());

        // Check scripts in this (decoded) label
        let label_scripts = scripts::detect_scripts(&label);
        per_label_scripts.push(label_scripts.iter().map(|s| (*s).to_string()).collect());

        // Track all scripts seen (O(1) dedup via HashSet)
        for s in &label_scripts {
            if seen_scripts.insert(s) {
                all_scripts.push(s);
            }
        }

        // Mixed-script within a single label is suspicious. Conservative policy
        // (#254): any label drawing on two or more scripts is flagged. The
        // former rule only flagged the four Latin-paired high-risk combinations
        // (Cyrillic/Greek/Armenian/Cherokee + Latin), so a label mixing *two
        // non-Latin* scripts with no Latin confusable mapping — e.g. Greek +
        // Cyrillic — set `mixed_script = true` yet was reported not-suspicious.
        // That contradicted this function's documented "flag anything
        // suspicious" contract and failed open on a real spoofing vector.
        // Callers needing a more permissive policy (e.g. allowing Latin + CJK)
        // can read the `mixed_script` and `scripts` fields and decide for
        // themselves; the boolean here fails closed.
        if label_scripts.len() > 1 {
            has_mixed = true;
            suspicious = true;
        }

        // Check confusables in this label. Fail CLOSED (#67.1): if the check
        // errors we cannot prove the label clean, so flag it as suspicious
        // rather than silently degrading to "not confusable". The target
        // ("latin") is a fixed, always-supported script, so the underlying
        // Result is in practice always `Ok`; the `Err` arm is defensive.
        match confusables::is_confusable(&label, "latin") {
            Ok(true) => {
                has_confusables = true;
                suspicious = true;
            }
            Ok(false) => {}
            Err(_) => {
                suspicious = true;
            }
        }
    }

    // Generate canonical Latin form from the decoded labels.
    let decoded_hostname = decoded_labels.join(".");

    // Direction conflict (#412): the decoded hostname mixes strong-LTR and
    // strong-RTL characters — the "BiDi Swap" precondition. Computed on the same
    // decoded codepoints, with no U+202x override involved. Fold it into the
    // verdict (it is precise and rare in legitimate hostnames). `cross_label_script`
    // (more than one script across labels) is the broader, noisier fact — it
    // fires on benign IDN ccTLDs (`google.рф`), so it is exposed but NOT folded.
    let bidi_conflict = scripts::has_bidi_conflict(&decoded_hostname);
    let cross_label_script = all_scripts.len() > 1;
    if bidi_conflict {
        suspicious = true;
    }

    let canonical =
        confusables::normalize_confusables(&decoded_hostname, "latin").unwrap_or(decoded_hostname);

    (
        suspicious,
        HostnameAnalysis {
            suspicious,
            scripts: all_scripts.into_iter().map(String::from).collect(),
            mixed_script: has_mixed,
            has_confusables,
            bidi_conflict,
            cross_label_script,
            label_scripts: per_label_scripts,
            canonical,
        },
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_clean_hostname_not_suspicious() {
        let (suspicious, details) = is_suspicious_hostname("paypal.com");
        assert!(!suspicious);
        assert!(!details.has_confusables);
        assert!(!details.mixed_script);
    }

    #[test]
    fn test_cyrillic_spoof() {
        // Cyrillic а and р mixed with Latin
        let (suspicious, details) = is_suspicious_hostname("\u{0440}\u{0430}ypal.com");
        assert!(suspicious);
        assert!(details.has_confusables);
        assert!(details.mixed_script);
        assert_eq!(details.canonical, "paypal.com");
    }

    #[test]
    fn test_full_cyrillic_domain() {
        // Fully Cyrillic domain — not mixed script, might have confusables
        let (_, details) = is_suspicious_hostname("яндекс.ру");
        assert!(!details.mixed_script);
    }

    #[test]
    fn test_mixed_non_latin_scripts_suspicious() {
        // #254: a label mixing two *non-Latin* scripts (Cyrillic я + Greek ψ)
        // with no Latin confusable mapping used to set mixed_script=true yet
        // report not-suspicious, because the old rule only flagged Latin-paired
        // high-risk combinations. The conservative policy now flags any
        // mixed-script label as suspicious.
        let (suspicious, details) = is_suspicious_hostname("\u{044F}\u{03C8}.com");
        assert!(suspicious, "mixed Cyrillic+Greek label must be suspicious");
        assert!(details.mixed_script);
        // The mixed-script rule — not the confusable check — is what catches
        // this: neither character maps to a Latin confusable.
        assert!(
            !details.has_confusables,
            "neither я nor ψ is a Latin confusable; the mixed-script rule must \
             be what flags this label"
        );
        assert!(details.scripts.iter().any(|s| s == "Cyrillic"));
        assert!(details.scripts.iter().any(|s| s == "Greek"));
    }

    #[test]
    fn test_punycode_non_homograph_not_suspicious() {
        // xn--n3h.com decodes to ☃.com (a snowman) — a single-script non-Latin
        // label, not a homoglyph spoof, so it is correctly reported
        // not-suspicious. The point of #63 is that the label is now *decoded and
        // analysed*, not that every xn-- label is flagged.
        let (suspicious, _) = is_suspicious_hostname("xn--n3h.com");
        assert!(!suspicious);
    }

    #[test]
    fn test_punycode_homograph_suspicious() {
        // #63: the on-the-wire ACE form of a Cyrillic homograph must be decoded
        // and flagged. Build the xn-- form of a Cyrillic "apple" spoof, then
        // assert is_suspicious_hostname flags it (it used to pass as safe ASCII).
        let spoof = "\u{0430}\u{0440}\u{0440}\u{04CF}\u{0435}"; // аррӏе (Cyrillic)
        let ace = idna::domain_to_ascii(spoof).expect("encode Cyrillic spoof to ACE");
        assert!(
            ace.starts_with("xn--"),
            "expected an xn-- label, got {ace:?}"
        );
        let hostname = format!("{ace}.com");
        let (suspicious, details) = is_suspicious_hostname(&hostname);
        assert!(
            suspicious,
            "Cyrillic homograph in ACE form {hostname:?} must be suspicious"
        );
        assert!(details.has_confusables);
    }

    #[test]
    fn test_ipv6_loopback_not_suspicious() {
        let (suspicious, details) = is_suspicious_hostname("[::1]");
        assert!(!suspicious);
        assert!(!details.mixed_script);
        assert!(!details.has_confusables);
    }

    #[test]
    fn test_ipv6_full_not_suspicious() {
        let (suspicious, details) = is_suspicious_hostname("[2001:db8::1]");
        assert!(!suspicious);
        assert!(details.scripts.is_empty());
    }

    // ── #412: bidi-direction conflict ────────────────────────────────────────

    #[test]
    fn test_bidi_swap_hostname_flags_direction_conflict() {
        // "varonis.com.ו.קום": Latin subdomain stacked on a Hebrew (RTL) domain —
        // the BiDi-Swap shape. mixed_script stays false (each label is single
        // script), but bidi_conflict fires and drives suspicious=true.
        let (suspicious, d) =
            is_suspicious_hostname("varonis.com.\u{05D5}.\u{05E7}\u{05D5}\u{05DD}");
        assert!(suspicious);
        assert!(
            d.bidi_conflict,
            "LTR+RTL across labels must set bidi_conflict"
        );
        assert!(d.cross_label_script);
        assert!(!d.mixed_script, "no single label is mixed-script");
        assert_eq!(d.label_scripts.len(), 4);
        assert_eq!(d.label_scripts[0], vec!["Latin".to_string()]);
        assert_eq!(d.label_scripts[3], vec!["Hebrew".to_string()]);
    }

    #[test]
    fn test_bidi_conflict_intra_label() {
        // The intra-label case: "varonisו.com" — one label mixes Latin + Hebrew.
        let (suspicious, d) = is_suspicious_hostname("varonis\u{05D5}.com");
        assert!(suspicious);
        assert!(d.bidi_conflict);
    }

    #[test]
    fn test_benign_idn_cctld_no_direction_conflict() {
        // "google.рф": Latin label under a Cyrillic ccTLD. Both scripts are LTR,
        // so there is NO direction conflict (cross_label_script is true but does
        // not flip suspicious on its own).
        let (_, d) = is_suspicious_hostname("google.\u{0440}\u{0444}");
        assert!(!d.bidi_conflict);
        assert!(d.cross_label_script);
    }

    #[test]
    fn test_all_rtl_hostname_no_direction_conflict() {
        // "אתר.קום": a legitimately all-Hebrew domain — single direction (RTL),
        // so bidi_conflict is false and cross_label_script is false.
        let (_, d) = is_suspicious_hostname("\u{05D0}\u{05EA}\u{05E8}.\u{05E7}\u{05D5}\u{05DD}");
        assert!(!d.bidi_conflict);
        assert!(!d.cross_label_script);
    }

    #[test]
    fn test_ascii_hostname_no_new_signals() {
        let (suspicious, d) = is_suspicious_hostname("example.com");
        assert!(!suspicious);
        assert!(!d.bidi_conflict);
        assert!(!d.cross_label_script);
        assert_eq!(
            d.label_scripts,
            vec![vec!["Latin".to_string()], vec!["Latin".to_string()]]
        );
    }

    #[test]
    fn test_bidi_conflict_on_decoded_punycode() {
        // xn--9db.xn--9dbq2a decodes to Hebrew ו.קום — all-RTL after decode, so
        // bidi_conflict is false, exactly as for the literal Hebrew form.
        let (_, d) = is_suspicious_hostname("xn--9db.xn--9dbq2a");
        assert!(!d.bidi_conflict);
    }
}
