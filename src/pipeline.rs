use std::borrow::Cow;

use pyo3::prelude::*;

use bitflags::bitflags;

use crate::{case_fold, confusables, emoji, normalize, transliterate, whitespace};

bitflags! {
    #[derive(Debug, Clone, Copy)]
    struct PipelineSteps: u16 {
        const NORMALIZE        = 0b0000_0001;
        const TRANSLITERATE    = 0b0000_0010;
        const CONFUSABLES      = 0b0000_0100;
        const STRIP_ACCENTS    = 0b0000_1000;
        const FOLD_CASE        = 0b0001_0000;
        const COLLAPSE_WS      = 0b0010_0000;
        const DEMOJIZE         = 0b0100_0000;
        const STRIP_CONTROL    = 0b1000_0000;
        const STRIP_ZERO_WIDTH = 0b1_0000_0000;
    }
}

/// Composable, pre-compiled text cleaning pipeline.
#[pyclass]
#[pyo3(name = "_TextPipeline")]
pub struct _TextPipeline {
    steps: PipelineSteps,
    normalize_form: Option<String>,
    lang: Option<String>,
    strict_iso9: bool,
    gost7034: bool,
}

#[pymethods]
impl _TextPipeline {
    #[new]
    #[pyo3(signature = (
        *,
        normalize=None,
        transliterate=false,
        lang=None,
        strict_iso9=false,
        gost7034=false,
        confusables=false,
        strip_accents=false,
        fold_case=false,
        collapse_whitespace=false,
        strip_control=None,
        strip_zero_width=None,
        demojize=false,
    ))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        normalize: Option<&str>,
        transliterate: bool,
        lang: Option<&str>,
        strict_iso9: bool,
        gost7034: bool,
        confusables: bool,
        strip_accents: bool,
        fold_case: bool,
        collapse_whitespace: bool,
        strip_control: Option<bool>,
        strip_zero_width: Option<bool>,
        demojize: bool,
    ) -> PyResult<Self> {
        let mut steps = PipelineSteps::empty();

        if let Some(form) = normalize {
            // Validate the form
            if !matches!(form, "NFC" | "NFD" | "NFKC" | "NFKD") {
                return Err(crate::TranslitError::new_err(format!(
                    "normalize must be 'NFC', 'NFD', 'NFKC', or 'NFKD', got '{form}'"
                )));
            }
            steps |= PipelineSteps::NORMALIZE;
        }
        if transliterate {
            steps |= PipelineSteps::TRANSLITERATE;
        }
        if confusables {
            steps |= PipelineSteps::CONFUSABLES;
        }
        if strip_accents {
            steps |= PipelineSteps::STRIP_ACCENTS;
        }
        if fold_case {
            steps |= PipelineSteps::FOLD_CASE;
        }
        if collapse_whitespace {
            steps |= PipelineSteps::COLLAPSE_WS;
        }
        if demojize {
            steps |= PipelineSteps::DEMOJIZE;
        }

        // strip_control: defaults to True when collapse_whitespace is True,
        // False otherwise. Can be independently set to True for standalone use.
        let sc = strip_control.unwrap_or(collapse_whitespace);
        if sc {
            steps |= PipelineSteps::STRIP_CONTROL;
        }

        // strip_zero_width: same logic as strip_control.
        let szw = strip_zero_width.unwrap_or(collapse_whitespace);
        if szw {
            steps |= PipelineSteps::STRIP_ZERO_WIDTH;
        }

        if strict_iso9 && gost7034 {
            return Err(crate::TranslitError::new_err(
                "strict_iso9 and gost7034 are mutually exclusive",
            ));
        }

        let pipeline = Self {
            steps,
            normalize_form: normalize.map(std::borrow::ToOwned::to_owned),
            lang: lang.map(std::borrow::ToOwned::to_owned),
            strict_iso9,
            gost7034,
        };

        // Invariant: NORMALIZE step requires a normalize_form, and vice versa.
        debug_assert_eq!(
            pipeline.steps.contains(PipelineSteps::NORMALIZE),
            pipeline.normalize_form.is_some(),
            "NORMALIZE step and normalize_form must be set together"
        );

        Ok(pipeline)
    }

    /// Return the ordered list of active pipeline steps and their parameters.
    ///
    /// Order matches `process()`: normalize → demojize → strip_accents →
    /// transliterate → confusables → fold_case → strip_control →
    /// strip_zero_width → collapse_whitespace.
    ///
    /// Transliterate runs BEFORE confusables so that non-Latin scripts are
    /// fully romanized before confusable normalization. Running confusables
    /// first on Cyrillic/Greek text creates mixed-script gibberish because
    /// only some characters have Latin confusables.
    fn steps(&self) -> Vec<(String, Option<String>)> {
        // Execution order — add new steps here AND in process().
        const STEP_ORDER: &[(PipelineSteps, &str)] = &[
            (PipelineSteps::NORMALIZE, "normalize"),
            (PipelineSteps::DEMOJIZE, "demojize"),
            (PipelineSteps::STRIP_ACCENTS, "strip_accents"),
            (PipelineSteps::TRANSLITERATE, "transliterate"),
            (PipelineSteps::CONFUSABLES, "confusables"),
            (PipelineSteps::FOLD_CASE, "fold_case"),
            (PipelineSteps::STRIP_CONTROL, "strip_control"),
            (PipelineSteps::STRIP_ZERO_WIDTH, "strip_zero_width"),
            (PipelineSteps::COLLAPSE_WS, "collapse_whitespace"),
        ];

        STEP_ORDER
            .iter()
            .filter(|(flag, _)| self.steps.contains(*flag))
            .map(|(flag, name)| {
                let param = if flag.contains(PipelineSteps::NORMALIZE) {
                    self.normalize_form.clone()
                } else if flag.contains(PipelineSteps::CONFUSABLES) {
                    Some("latin".to_owned())
                } else if flag.contains(PipelineSteps::TRANSLITERATE) {
                    self.lang.clone()
                } else {
                    None
                };
                ((*name).to_owned(), param)
            })
            .collect()
    }

    fn __repr__(&self) -> String {
        let parts: Vec<String> = self
            .steps()
            .iter()
            .map(|(name, param)| match param {
                Some(p) => format!("{name}={p:?}"),
                None => name.clone(),
            })
            .collect();
        format!("TextPipeline({})", parts.join(" -> "))
    }

    /// Process text through the pipeline.
    ///
    /// Uses `Cow<str>` to avoid cloning the input when no steps modify it
    /// (e.g. empty pipeline, or input that passes through unchanged).
    fn process(&self, text: &str) -> PyResult<String> {
        let mut buf: Cow<'_, str> = Cow::Borrowed(text);

        // Fixed optimal order regardless of construction order:
        // 1. Normalize (canonical form first)
        if self.steps.contains(PipelineSteps::NORMALIZE) {
            if let Some(ref form) = self.normalize_form {
                buf = Cow::Owned(normalize::_normalize(&buf, form)?);
            }
        }

        // 2. Demojize (after normalization, before transliteration)
        if self.steps.contains(PipelineSteps::DEMOJIZE) {
            buf = Cow::Owned(emoji::demojize_rust(&buf, false));
        }

        // 3. Strip accents (NFD decompose + strip combining marks)
        if self.steps.contains(PipelineSteps::STRIP_ACCENTS) {
            buf = Cow::Owned(transliterate::_strip_accents(&buf));
        }

        // 4. Transliterate (Unicode → ASCII)
        if self.steps.contains(PipelineSteps::TRANSLITERATE) {
            buf = Cow::Owned(
                transliterate::transliterate_impl(
                    &buf,
                    self.lang.as_deref(),
                    crate::ErrorMode::Ignore,
                    "",
                    self.strict_iso9,
                    self.gost7034,
                    false,
                )
                .into_owned(),
            );
        }

        // 5. Confusables (after transliteration — non-Latin text is now ASCII,
        //    so confusable normalization operates on Latin-only text)
        if self.steps.contains(PipelineSteps::CONFUSABLES) {
            buf = Cow::Owned(confusables::_normalize_confusables(&buf, "latin")?);
        }

        // 6. Fold case (after transliteration)
        if self.steps.contains(PipelineSteps::FOLD_CASE) {
            buf = Cow::Owned(case_fold::fold_case_impl(&buf));
        }

        // 7. Strip control + strip zero-width + collapse whitespace (final cleanup)
        //    When collapse_whitespace is active, use the combined single-pass function.
        //    Otherwise, apply strip_control and strip_zero_width independently.
        let has_collapse = self.steps.contains(PipelineSteps::COLLAPSE_WS);
        let has_strip_ctrl = self.steps.contains(PipelineSteps::STRIP_CONTROL);
        let has_strip_zw = self.steps.contains(PipelineSteps::STRIP_ZERO_WIDTH);

        if has_collapse {
            // Combined single-pass: collapse whitespace + optional stripping
            buf = Cow::Owned(whitespace::_collapse_whitespace(
                &buf,
                has_strip_ctrl,
                has_strip_zw,
            ));
        } else {
            // Standalone stripping without whitespace collapsing
            if has_strip_ctrl {
                buf = Cow::Owned(whitespace::strip_control_chars(&buf));
            }
            if has_strip_zw {
                buf = Cow::Owned(whitespace::strip_zero_width_chars(&buf));
            }
        }

        Ok(buf.into_owned())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── Helper to build a pipeline from bitflags ────────────────────
    fn pipeline(steps: PipelineSteps, normalize_form: Option<&str>) -> _TextPipeline {
        _TextPipeline {
            steps,
            normalize_form: normalize_form.map(ToOwned::to_owned),
            lang: None,
            strict_iso9: false,
            gost7034: false,
        }
    }

    // ── Unit tests: individual steps ─────────────────────────────────

    #[test]
    fn test_pipeline_empty_passthrough() {
        let p = pipeline(PipelineSteps::empty(), None);
        assert_eq!(p.process("hello world").unwrap(), "hello world");
        assert_eq!(p.process("").unwrap(), "");
        assert_eq!(p.process("café ☕").unwrap(), "café ☕");
        // Empty pipeline preserves control chars and zero-width
        assert_eq!(p.process("a\x00b").unwrap(), "a\x00b");
        assert_eq!(p.process("a\u{200B}b").unwrap(), "a\u{200B}b");
    }

    #[test]
    fn test_pipeline_normalize_only() {
        let p = pipeline(PipelineSteps::NORMALIZE, Some("NFC"));
        // NFD e + combining accent → NFC é
        let result = p.process("caf\u{0065}\u{0301}").unwrap();
        assert_eq!(result, "caf\u{00e9}");
    }

    #[test]
    fn test_pipeline_transliterate_only() {
        let p = pipeline(PipelineSteps::TRANSLITERATE, None);
        let result = p.process("café").unwrap();
        assert!(result.is_ascii(), "expected ASCII, got: {result:?}");
    }

    #[test]
    fn test_pipeline_fold_case_only() {
        let p = pipeline(PipelineSteps::FOLD_CASE, None);
        assert_eq!(p.process("HELLO").unwrap(), "hello");
        assert_eq!(p.process("Straße").unwrap(), "strasse");
    }

    #[test]
    fn test_pipeline_strip_accents_only() {
        let p = pipeline(PipelineSteps::STRIP_ACCENTS, None);
        assert_eq!(p.process("café").unwrap(), "cafe");
        assert_eq!(p.process("naïve").unwrap(), "naive");
    }

    #[test]
    fn test_pipeline_collapse_ws_only() {
        // collapse_whitespace without strip_control/strip_zero_width
        let p = pipeline(PipelineSteps::COLLAPSE_WS, None);
        assert_eq!(p.process("  hello   world  ").unwrap(), "hello world");
    }

    #[test]
    fn test_pipeline_collapse_ws_with_strip_control() {
        let p = pipeline(
            PipelineSteps::COLLAPSE_WS | PipelineSteps::STRIP_CONTROL,
            None,
        );
        assert_eq!(p.process("hello\x00world").unwrap(), "helloworld");
    }

    #[test]
    fn test_pipeline_collapse_ws_with_strip_zero_width() {
        let p = pipeline(
            PipelineSteps::COLLAPSE_WS | PipelineSteps::STRIP_ZERO_WIDTH,
            None,
        );
        assert_eq!(p.process("hello\u{200B}world").unwrap(), "helloworld");
    }

    #[test]
    fn test_pipeline_strip_control_standalone() {
        // strip_control without collapse_whitespace — independent operation
        let p = pipeline(PipelineSteps::STRIP_CONTROL, None);
        assert_eq!(p.process("hello\x00world").unwrap(), "helloworld");
        // Whitespace is NOT collapsed
        assert_eq!(p.process("hello   world").unwrap(), "hello   world");
        // Newline and tab are preserved
        assert_eq!(p.process("hello\nworld").unwrap(), "hello\nworld");
        assert_eq!(p.process("hello\tworld").unwrap(), "hello\tworld");
    }

    #[test]
    fn test_pipeline_strip_zero_width_standalone() {
        // strip_zero_width without collapse_whitespace — independent operation
        let p = pipeline(PipelineSteps::STRIP_ZERO_WIDTH, None);
        assert_eq!(p.process("hello\u{200B}world").unwrap(), "helloworld");
        // Whitespace is NOT collapsed
        assert_eq!(p.process("hello   world").unwrap(), "hello   world");
    }

    #[test]
    fn test_pipeline_confusables_only() {
        let p = pipeline(PipelineSteps::CONFUSABLES, None);
        // Cyrillic а (U+0430) → Latin a
        let result = p.process("\u{0430}bc").unwrap();
        assert_eq!(result, "abc");
    }

    #[test]
    fn test_pipeline_demojize_only() {
        let p = pipeline(PipelineSteps::DEMOJIZE, None);
        let result = p.process("Hello 😀").unwrap();
        assert!(
            result.contains("grinning face"),
            "expected emoji name, got: {result:?}"
        );
    }

    // ── Step ordering verification ───────────────────────────────────

    #[test]
    fn test_pipeline_all_steps_ordering() {
        let p = pipeline(PipelineSteps::all(), Some("NFKC"));
        // ﬁ (Latin ligature fi) → NFKC → fi → ... → fi
        let result = p.process("\u{FB01}").unwrap();
        assert_eq!(result, "fi");
    }

    #[test]
    fn test_pipeline_steps_list_matches_execution_order() {
        let p = pipeline(PipelineSteps::all(), Some("NFC"));
        let step_names: Vec<String> = p.steps().iter().map(|(name, _)| name.clone()).collect();
        assert_eq!(
            step_names,
            vec![
                "normalize",
                "confusables",
                "demojize",
                "strip_accents",
                "transliterate",
                "fold_case",
                "strip_control",
                "strip_zero_width",
                "collapse_whitespace",
            ]
        );
    }

    #[test]
    fn test_pipeline_steps_without_strip() {
        // When collapse_whitespace is set but strip_control/strip_zero_width are not
        let p = pipeline(PipelineSteps::FOLD_CASE | PipelineSteps::COLLAPSE_WS, None);
        let step_names: Vec<String> = p.steps().iter().map(|(name, _)| name.clone()).collect();
        assert_eq!(step_names, vec!["fold_case", "collapse_whitespace"]);
    }

    #[test]
    fn test_pipeline_repr_format() {
        let p = pipeline(
            PipelineSteps::NORMALIZE | PipelineSteps::FOLD_CASE,
            Some("NFC"),
        );
        let repr = p.__repr__();
        assert!(repr.starts_with("TextPipeline("), "repr: {repr:?}");
        assert!(repr.contains("normalize"), "repr: {repr:?}");
        assert!(repr.contains("fold_case"), "repr: {repr:?}");
    }

    // ── Constructor tests (via PyO3 signature semantics) ─────────────

    #[test]
    fn test_constructor_collapse_ws_implies_strip() {
        // collapse_whitespace=True with default strip_control/strip_zero_width (None)
        // should auto-enable both strip flags
        let p = _TextPipeline::new(
            None, false, None, false, false, false, false, false, true, // collapse_whitespace
            None, // strip_control (defaults to collapse_whitespace=true)
            None, // strip_zero_width (defaults to collapse_whitespace=true)
            false,
        )
        .unwrap();
        assert!(p.steps.contains(PipelineSteps::COLLAPSE_WS));
        assert!(p.steps.contains(PipelineSteps::STRIP_CONTROL));
        assert!(p.steps.contains(PipelineSteps::STRIP_ZERO_WIDTH));
    }

    #[test]
    fn test_constructor_collapse_ws_with_explicit_false() {
        // collapse_whitespace=True but strip_control=False explicitly
        let p = _TextPipeline::new(
            None,
            false,
            None,
            false,
            false,
            false,
            false,
            false,
            true,        // collapse_whitespace
            Some(false), // strip_control=False
            Some(false), // strip_zero_width=False
            false,
        )
        .unwrap();
        assert!(p.steps.contains(PipelineSteps::COLLAPSE_WS));
        assert!(!p.steps.contains(PipelineSteps::STRIP_CONTROL));
        assert!(!p.steps.contains(PipelineSteps::STRIP_ZERO_WIDTH));
    }

    #[test]
    fn test_constructor_standalone_strip_control() {
        // strip_control=True without collapse_whitespace
        let p = _TextPipeline::new(
            None,
            false,
            None,
            false,
            false,
            false,
            false,
            false,
            false,      // collapse_whitespace
            Some(true), // strip_control
            None,       // strip_zero_width (defaults to collapse_whitespace=false)
            false,
        )
        .unwrap();
        assert!(!p.steps.contains(PipelineSteps::COLLAPSE_WS));
        assert!(p.steps.contains(PipelineSteps::STRIP_CONTROL));
        assert!(!p.steps.contains(PipelineSteps::STRIP_ZERO_WIDTH));
    }

    #[test]
    fn test_constructor_empty() {
        // Default constructor — no steps
        let p = _TextPipeline::new(
            None, false, None, false, false, false, false, false, false, None, None, false,
        )
        .unwrap();
        assert!(p.steps.is_empty());
    }

    // ── Edge cases ───────────────────────────────────────────────────

    #[test]
    fn test_pipeline_all_steps_empty_input() {
        let p = pipeline(PipelineSteps::all(), Some("NFC"));
        assert_eq!(p.process("").unwrap(), "");
    }

    #[test]
    fn test_pipeline_all_steps_ascii_input() {
        let p = pipeline(PipelineSteps::all(), Some("NFC"));
        assert_eq!(p.process("hello").unwrap(), "hello");
    }

    // ── Property-based tests ─────────────────────────────────────────

    mod proptest_properties {
        use super::*;
        use proptest::prelude::*;

        fn all_steps_pipeline() -> _TextPipeline {
            pipeline(PipelineSteps::all(), Some("NFKC"))
        }

        /// Pipeline without confusables — used for idempotency testing.
        /// Confusables intentionally remaps ASCII characters that
        /// transliteration produced (e.g. `|` → `l`), so the combined
        /// pipeline stabilises in one pass but is not idempotent in the
        /// mathematical sense.  All other steps are individually
        /// idempotent and their composition must be too.
        fn idempotent_steps_pipeline() -> _TextPipeline {
            pipeline(
                PipelineSteps::all() & !PipelineSteps::CONFUSABLES,
                Some("NFKC"),
            )
        }

        proptest! {
            #![proptest_config(ProptestConfig::with_cases(1000))]

            /// The full pipeline must never panic on any valid Unicode string.
            #[test]
            fn pipeline_all_steps_never_panics(s in "\\PC*") {
                let p = all_steps_pipeline();
                let result = p.process(&s);
                prop_assert!(result.is_ok(), "pipeline panicked on: {:?}", s);
            }

            /// Output of all-steps pipeline is always valid ASCII (since
            /// transliterate with Ignore mode is included, which drops non-ASCII).
            #[test]
            fn pipeline_all_steps_produces_ascii(s in "\\PC*") {
                let p = all_steps_pipeline();
                let result = p.process(&s).unwrap();
                prop_assert!(
                    result.is_ascii(),
                    "non-ASCII in all-steps pipeline output: {:?} → {:?}",
                    s, result
                );
            }

            /// Pipeline (without confusables) is idempotent: processing
            /// already-processed text gives the same result.
            #[test]
            fn pipeline_all_steps_idempotent(s in "\\PC*") {
                let p = idempotent_steps_pipeline();
                let once = p.process(&s).unwrap();
                let twice = p.process(&once).unwrap();
                prop_assert_eq!(&once, &twice,
                    "pipeline is not idempotent on: {:?}", s);
            }

            /// Full pipeline (including confusables) stabilises in two
            /// passes: confusables runs before transliterate, so
            /// transliteration output only passes through confusables on
            /// the second application.
            #[test]
            fn pipeline_all_steps_stabilises(s in "\\PC*") {
                let p = all_steps_pipeline();
                let once = p.process(&s).unwrap();
                let twice = p.process(&once).unwrap();
                let thrice = p.process(&twice).unwrap();
                prop_assert_eq!(&twice, &thrice,
                    "pipeline does not stabilise on: {:?}", s);
            }

            /// Empty pipeline is a no-op — output equals input.
            #[test]
            fn pipeline_empty_is_identity(s in "\\PC*") {
                let p = pipeline(PipelineSteps::empty(), None);
                let result = p.process(&s).unwrap();
                prop_assert_eq!(&result, &s);
            }

            /// strip_control standalone is idempotent.
            #[test]
            fn strip_control_standalone_idempotent(s in "\\PC*") {
                let p = pipeline(PipelineSteps::STRIP_CONTROL, None);
                let once = p.process(&s).unwrap();
                let twice = p.process(&once).unwrap();
                prop_assert_eq!(&once, &twice);
            }

            /// strip_zero_width standalone is idempotent.
            #[test]
            fn strip_zero_width_standalone_idempotent(s in "\\PC*") {
                let p = pipeline(PipelineSteps::STRIP_ZERO_WIDTH, None);
                let once = p.process(&s).unwrap();
                let twice = p.process(&once).unwrap();
                prop_assert_eq!(&once, &twice);
            }
        }
    }
}
