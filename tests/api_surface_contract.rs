//! Surface-contract guards for the Layer-2 public API (`crate::api`).
//!
//! Two resilience invariants, enforced as tests so a future change that breaks
//! them fails CI rather than silently shipping a hard-to-evolve surface:
//!
//! 1. **Struct returns, not anonymous tuples.** Every public function returns a
//!    named (and `#[non_exhaustive]`) struct instead of a bare tuple, so a field
//!    can be added later without breaking callers. A source-level scan catches
//!    any new `-> (…)` / `-> Wrapper<(…)>` return type.
//! 2. **Uniform `as_str` / `Display` / `FromStr` on every token enum.** Each
//!    string-backed enum round-trips through all three, and an unknown token is a
//!    classified [`ErrorKind::InvalidArgument`].

use disarm::api;
use disarm::ErrorKind;

// ── 1. Named-struct returns ───────────────────────────────────────────────────

#[test]
fn detect_encoding_returns_named_struct() {
    let d: api::EncodingDetection = api::detect_encoding(b"hello world");
    // Field access pins the named-struct shape (`label: String`, `confidence: f64`).
    assert!(!d.label.is_empty());
    assert!((0.0..=1.0).contains(&d.confidence));
}

#[test]
fn decode_to_utf8_returns_named_struct() {
    let d: api::DecodedText = api::decode_to_utf8(b"hello", None, 0.0, false).unwrap();
    // Field access pins the named-struct shape (`text: String`, `had_errors: bool`).
    assert_eq!(d.text, "hello");
    assert!(!d.had_errors);
}

#[test]
fn is_suspicious_hostname_returns_analysis_struct() {
    // Returns the analysis directly; the verdict is the `suspicious` field (the
    // former tuple's redundant bool is gone).
    let a: api::HostnameAnalysis = api::is_suspicious_hostname("p\u{0430}ypal.com");
    assert!(a.suspicious);
    assert!(!a.scripts.is_empty());
    let safe = api::is_suspicious_hostname("example.com");
    assert!(!safe.suspicious);
}

#[test]
fn no_public_tuple_returns_in_api() {
    // Scan every src/api/*.rs for a `pub fn` (public surface only — private
    // helpers may use tuples) whose return type is a tuple: bare (`-> (A, B)`) or
    // wrapped (`Result<(A, B), _>`, `Option<(A, B)>`). The unit `()` is excluded.
    // The contract is "named structs only", so a new tuple return fails here.
    let dir = concat!(env!("CARGO_MANIFEST_DIR"), "/src/api");
    let mut offenders = Vec::new();
    for entry in std::fs::read_dir(dir).expect("read src/api") {
        let path = entry.expect("dir entry").path();
        if path.extension().and_then(|e| e.to_str()) != Some("rs") {
            continue;
        }
        let src = std::fs::read_to_string(&path).expect("read api file");
        let lines: Vec<&str> = src.lines().collect();
        let mut i = 0;
        while i < lines.len() {
            // Only `pub fn` — not `pub(crate) fn`, not private `fn`.
            if !lines[i].trim_start().starts_with("pub fn ") {
                i += 1;
                continue;
            }
            // Accumulate the signature up to the body's opening brace (handles
            // multi-line signatures whose `->` sits on the closing line).
            let start = i;
            let mut sig = String::new();
            while i < lines.len() {
                sig.push_str(lines[i]);
                sig.push(' ');
                if lines[i].contains('{') {
                    break;
                }
                i += 1;
            }
            if let Some(arrow) = sig.find("->") {
                let ret = sig[arrow + 2..].trim_start();
                let bare_tuple = ret.starts_with('(') && !ret.starts_with("()");
                let wrapped_tuple = ret.contains("<(") && !ret.contains("<()");
                if bare_tuple || wrapped_tuple {
                    offenders.push(format!(
                        "{}:{}: {}",
                        path.display(),
                        start + 1,
                        lines[start].trim()
                    ));
                }
            }
            i += 1;
        }
    }
    assert!(
        offenders.is_empty(),
        "public API must return named structs, not tuples:\n{}",
        offenders.join("\n")
    );
}

// ── 2. Uniform token-enum conversions ─────────────────────────────────────────

/// For each variant: `Display` prints `as_str`, and `FromStr` of `as_str` returns
/// the same variant. Then an unknown token must be an `InvalidArgument` error.
macro_rules! assert_token_enum {
    ($ty:ty, [$($variant:expr),+ $(,)?]) => {{
        $(
            let v: $ty = $variant;
            assert_eq!(v.to_string(), v.as_str(), "Display must equal as_str for {v:?}");
            let parsed: $ty = v.as_str().parse().expect("as_str must parse back via FromStr");
            assert_eq!(parsed, v, "FromStr(as_str) must round-trip for {v:?}");
        )+
        let err = "not-a-valid-token-xyz".parse::<$ty>().unwrap_err();
        assert_eq!(
            err.kind(),
            ErrorKind::InvalidArgument,
            "an unknown token must be ErrorKind::InvalidArgument",
        );
    }};
}

#[test]
fn all_token_enums_roundtrip_as_str_display_fromstr() {
    use api::{NormalizationForm, Platform, ReverseLang, Scheme, TargetScript, UrlComponent};
    assert_token_enum!(TargetScript, [TargetScript::Latin, TargetScript::Cyrillic]);
    assert_token_enum!(
        Scheme,
        [Scheme::Default, Scheme::StrictIso9, Scheme::GostR7034]
    );
    assert_token_enum!(
        NormalizationForm,
        [
            NormalizationForm::Nfc,
            NormalizationForm::Nfd,
            NormalizationForm::Nfkc,
            NormalizationForm::Nfkd,
        ]
    );
    assert_token_enum!(
        UrlComponent,
        [
            UrlComponent::Path,
            UrlComponent::Segment,
            UrlComponent::Query,
            UrlComponent::Form,
        ]
    );
    assert_token_enum!(
        Platform,
        [Platform::Universal, Platform::Windows, Platform::Posix]
    );
    assert_token_enum!(
        ReverseLang,
        [
            ReverseLang::Greek,
            ReverseLang::Russian,
            ReverseLang::Ukrainian
        ]
    );
}
