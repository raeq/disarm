//! Layer 2: the idiomatic, pyo3-free Rust API — the crates.io surface (#38).
//!
//! These wrap the Layer-1 algorithm modules with typed parameters and infallible
//! signatures where the type system already rules out the error. The PyO3 shims
//! (`src/py/`) and the planned C-ABI consume the same Layer-1 core, so this is
//! the one place the public Rust behaviour is defined.
//!
//! The surface is split into cohesive submodules ([`safety`](self), text,
//! transliterate, presets) whose items are all re-exported here, so every public
//! item stays addressable as `crate::api::*`. The [`DisarmStr`] extension trait,
//! which spans all of them, lives here.

use std::borrow::Cow;

use crate::Error;

mod presets;
mod safety;
mod text;
mod transliterate;

pub use presets::*;
pub use safety::*;
pub use text::*;
pub use transliterate::*;

// ── Extension trait (#352) ────────────────────────────────────────────────────

/// Method-call syntax over the [`crate::api`] free functions, for any
/// string-like type (`&str`, `String`, `Cow`, …). `use disarm::DisarmStr;` then
/// call e.g. `"раypal".normalize_confusables(TargetScript::Latin)`.
///
/// Every method is a thin shim over the matching `api::` function — those are the
/// single implementation. Both ship: the free functions are easier to find in
/// docs; the methods read better at call sites.
///
/// ```
/// use disarm::DisarmStr;
/// use disarm::api::TargetScript;
/// assert_eq!("раypal".normalize_confusables(TargetScript::Latin), "paypal");
/// assert_eq!("café".strip_accents(), "cafe");
/// assert!("p\u{0430}ypal.com".is_suspicious_hostname().0);
/// ```
pub trait DisarmStr: AsRef<str> {
    /// See [`normalize_confusables`].
    #[must_use]
    fn normalize_confusables(&self, target: TargetScript) -> Cow<'_, str> {
        normalize_confusables(self.as_ref(), target)
    }
    /// See [`is_confusable`].
    #[must_use]
    fn is_confusable(&self, target: TargetScript) -> bool {
        is_confusable(self.as_ref(), target)
    }
    /// See [`fold_case`].
    #[must_use]
    fn fold_case(&self) -> Cow<'_, str> {
        fold_case(self.as_ref())
    }
    /// See [`strip_accents`].
    #[must_use]
    fn strip_accents(&self) -> Cow<'_, str> {
        strip_accents(self.as_ref())
    }
    /// See [`transliterate`].
    #[must_use]
    fn transliterate(&self) -> Cow<'_, str> {
        transliterate(self.as_ref())
    }
    /// See [`demojize`].
    #[must_use]
    fn demojize(&self, strip_modifiers: bool) -> String {
        demojize(self.as_ref(), strip_modifiers)
    }
    /// See [`normalize`].
    #[must_use]
    fn normalize(&self, form: NormalizationForm) -> String {
        normalize(self.as_ref(), form)
    }
    /// See [`is_normalized`].
    #[must_use]
    fn is_normalized(&self, form: NormalizationForm) -> bool {
        is_normalized(self.as_ref(), form)
    }
    /// See [`escape_html`].
    #[must_use]
    fn escape_html(&self) -> Cow<'_, str> {
        escape_html(self.as_ref())
    }
    /// See [`strip_zalgo`].
    #[must_use]
    fn strip_zalgo(&self, max_marks: usize) -> String {
        strip_zalgo(self.as_ref(), max_marks)
    }
    /// See [`is_zalgo`].
    #[must_use]
    fn is_zalgo(&self, threshold: usize) -> bool {
        is_zalgo(self.as_ref(), threshold)
    }
    /// See [`detect_scripts`].
    #[must_use]
    fn detect_scripts(&self) -> Vec<&'static str> {
        detect_scripts(self.as_ref())
    }
    /// See [`is_mixed_script`].
    #[must_use]
    fn is_mixed_script(&self) -> bool {
        is_mixed_script(self.as_ref())
    }
    /// See [`is_suspicious_hostname`].
    #[must_use]
    fn is_suspicious_hostname(&self) -> (bool, HostnameAnalysis) {
        is_suspicious_hostname(self.as_ref())
    }
    /// See [`grapheme_len`].
    #[must_use]
    fn grapheme_len(&self) -> usize {
        grapheme_len(self.as_ref())
    }
    /// See [`slugify`].
    #[must_use]
    fn slugify(&self, config: &SlugConfig) -> String {
        slugify(self.as_ref(), config)
    }
    /// See [`display_clean`].
    #[must_use]
    fn display_clean(&self) -> String {
        display_clean(self.as_ref())
    }
    /// See [`security_clean`].
    ///
    /// # Errors
    /// Propagates [`security_clean`]'s error.
    fn security_clean(&self) -> Result<String, Error> {
        security_clean(self.as_ref())
    }
    /// See [`strip_obfuscation`].
    ///
    /// # Errors
    /// Propagates [`strip_obfuscation`]'s error.
    fn strip_obfuscation(&self) -> Result<String, Error> {
        strip_obfuscation(self.as_ref())
    }
    /// See [`normalize_user_input`].
    ///
    /// # Errors
    /// Propagates [`normalize_user_input`]'s error.
    fn normalize_user_input(&self) -> Result<String, Error> {
        normalize_user_input(self.as_ref())
    }
}

impl<T: AsRef<str> + ?Sized> DisarmStr for T {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalize_folds_cyrillic_to_latin() {
        // Cyrillic 'а' (U+0430) → Latin 'a'.
        assert_eq!(
            normalize_confusables("\u{0430}pple", TargetScript::Latin),
            "apple"
        );
        assert_eq!(normalize_confusables("hello", TargetScript::Latin), "hello");
        assert_eq!(normalize_confusables("", TargetScript::Latin), "");
    }

    #[test]
    fn is_confusable_detects_homoglyph() {
        assert!(is_confusable("p\u{0430}ypal", TargetScript::Latin)); // Cyrillic 'а'
        assert!(!is_confusable("paypal", TargetScript::Latin));
    }

    #[test]
    fn target_script_tokens() {
        assert_eq!(TargetScript::Latin.as_str(), "latin");
        assert_eq!(TargetScript::Cyrillic.as_str(), "cyrillic");
    }

    #[test]
    fn terminal_width_sums_clusters() {
        assert_eq!(terminal_width("hello", false), 5);
        assert_eq!(terminal_width("世界", false), 4); // wide CJK
        assert_eq!(terminal_width("", false), 0);
    }

    #[test]
    fn grapheme_width_single_cluster() {
        assert_eq!(grapheme_width("a", false), 1);
        assert_eq!(grapheme_width("世", false), 2);
        assert_eq!(grapheme_width("👨\u{200D}👩\u{200D}👧\u{200D}👦", false), 2);
        // ZWJ family
    }

    #[test]
    fn ambiguous_wide_policy() {
        // U+00A1 INVERTED EXCLAMATION MARK is East Asian Ambiguous.
        assert_eq!(terminal_width("\u{00A1}", false), 1);
        assert_eq!(terminal_width("\u{00A1}", true), 2);
        assert_eq!(grapheme_width("\u{00A1}", true), 2);
    }

    #[test]
    fn sanitize_filename_happy_path() {
        // Transliterates to ASCII and strips illegal characters.
        let out = sanitize_filename("héllo/wörld.txt", "_", 255, Platform::Universal, None, true)
            .unwrap();
        assert_eq!(out, "hello_world.txt");
        // POSIX keeps ':' (only '/' and NUL are illegal there).
        let out = sanitize_filename("a:b", "_", 255, Platform::Posix, None, true).unwrap();
        assert_eq!(out, "a:b");
    }

    #[test]
    fn sanitize_filename_bad_lang_is_invalid_argument() {
        // The one fallible argument: an unknown language code surfaces the opaque
        // Error, classified as InvalidArgument (the first fallible Layer-2 path).
        let err =
            sanitize_filename("x", "_", 255, Platform::Universal, Some("zzz"), true).unwrap_err();
        assert_eq!(err.kind(), crate::ErrorKind::InvalidArgument);
        // Opaque: no inner source leaks.
        assert!(std::error::Error::source(&err).is_none());
    }

    #[test]
    fn decode_to_utf8_explicit_and_error() {
        // Explicit encoding round-trips; "café" in ISO-8859-1 is 0x63 61 66 E9.
        let (text, had_errors) =
            decode_to_utf8(&[0x63, 0x61, 0x66, 0xE9], Some("ISO-8859-1"), 0.0, false).unwrap();
        assert_eq!(text, "café");
        assert!(!had_errors);
        // An unknown label surfaces the opaque Error (InvalidArgument).
        let err = decode_to_utf8(b"hi", Some("FAKE-999"), 0.0, false).unwrap_err();
        assert_eq!(err.kind(), crate::ErrorKind::InvalidArgument);
        // detect_encoding is infallible.
        let (label, conf) = detect_encoding(b"hello world");
        assert!(!label.is_empty() && conf > 0.0);
    }

    #[test]
    fn strip_log_injection_and_bad_replacement() {
        // CR/LF/NUL are neutralized; a clean line borrows.
        assert_eq!(
            strip_log_injection("a\r\nb\0c", "\u{FFFD}", false).unwrap(),
            "a\u{FFFD}\u{FFFD}b\u{FFFD}c"
        );
        assert!(matches!(
            strip_log_injection("plain line", "\u{FFFD}", false).unwrap(),
            std::borrow::Cow::Borrowed(_)
        ));
        // A replacement that itself contains a neutralized char (CR) is rejected.
        let err = strip_log_injection("x", "\r", false).unwrap_err();
        assert_eq!(err.kind(), crate::ErrorKind::InvalidArgument);
        assert_eq!(err.code(), "invalid_log_replacement");
    }

    #[test]
    fn slugify_with_config() {
        assert_eq!(
            slugify("Héllo Wörld", &SlugConfig::default()),
            "hello-world"
        );
        let bounded = SlugConfig {
            max_length: 5,
            word_boundary: true,
            ..SlugConfig::default()
        };
        assert_eq!(slugify("hello world", &bounded), "hello");
    }

    #[test]
    fn transliterate_surface() {
        // ASCII passes through unchanged (Cow::Borrowed fast path).
        assert_eq!(transliterate("hello"), "hello");
        // Cyrillic auto-transliterates to ASCII via the builder.
        let out = Transliterate::new()
            .on_unknown(OnUnknown::Replace("?".into()))
            .run("Москва");
        assert!(out.is_ascii() && !out.is_empty(), "got {out:?}");
        // strip_accents / is_ascii / list_langs.
        assert_eq!(strip_accents("café"), "cafe");
        assert!(is_ascii("hi") && !is_ascii("café"));
        assert!(list_langs().iter().any(|l| l == "ru"));
        // ASCII has nothing untranslatable.
        assert!(Transliterate::new().find_untranslatable("hello").is_empty());
    }

    #[test]
    fn preset_pipelines_surface() {
        // security_clean folds Cyrillic homoglyphs (р а → p a) and strips bidi.
        assert_eq!(security_clean("\u{0440}\u{0430}ypal").unwrap(), "paypal");
        // Key presets are case/accent/script insensitive.
        assert_eq!(search_key("CAFÉ", None).unwrap(), "cafe");
        assert_eq!(sort_key("Москва", None).unwrap(), "moskva");
        assert_eq!(catalog_key("Café", None, false).unwrap(), "cafe");
        // ml_normalize lowercases, strips accents.
        assert_eq!(ml_normalize("Café", None, "cldr").unwrap(), "cafe");
        // Infallible presets.
        assert_eq!(display_clean("hello   world"), "hello world");
        assert_eq!(strip_bidi("pass\u{00AD}word"), "password");
        // normalize_user_input preserves script/accents; strip_obfuscation runs.
        assert_eq!(normalize_user_input("café").unwrap(), "café");
        assert!(!strip_obfuscation("p\u{0430}ypal").unwrap().is_empty());
        // Bad lang / emoji_style surface InvalidArgument.
        assert_eq!(
            search_key("x", Some("zzz")).unwrap_err().kind(),
            crate::ErrorKind::InvalidArgument
        );
        assert_eq!(
            ml_normalize("x", None, "bogus").unwrap_err().kind(),
            crate::ErrorKind::InvalidArgument
        );
    }

    #[test]
    fn list_profiles_surface() {
        let profiles = list_profiles();
        // Known profiles are present, and the list is sorted (stable contract).
        assert!(profiles.iter().any(|p| p == "llm_guardrail"));
        assert!(profiles.iter().any(|p| p == "search_index"));
        let mut sorted = profiles.clone();
        sorted.sort();
        assert_eq!(profiles, sorted);
    }

    #[test]
    fn is_suspicious_hostname_surface() {
        // Plain ASCII hostname: not suspicious, single-script, canonical == input.
        let (susp, a) = is_suspicious_hostname("example.com");
        assert!(!susp && !a.suspicious && !a.mixed_script);
        assert_eq!(a.canonical, "example.com");
        // A label mixing Cyrillic 'а' (U+0430) into Latin "paypal" is a homoglyph
        // spoof — flagged, with the mixed-script / confusable findings set.
        let (susp2, a2) = is_suspicious_hostname("p\u{0430}ypal.com");
        assert!(susp2);
        assert!(a2.mixed_script || a2.has_confusables);
    }
}
