use pyo3::prelude::*;

use bitflags::bitflags;

use crate::{case_fold, confusables, emoji, normalize, transliterate, whitespace};

bitflags! {
    #[derive(Debug, Clone, Copy)]
    struct PipelineSteps: u16 {
        const NORMALIZE       = 0b0000_0001;
        const TRANSLITERATE   = 0b0000_0010;
        const CONFUSABLES     = 0b0000_0100;
        const STRIP_ACCENTS   = 0b0000_1000;
        const FOLD_CASE       = 0b0001_0000;
        const COLLAPSE_WS     = 0b0010_0000;
        const DEMOJIZE        = 0b0100_0000;
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
    strip_control: bool,
    strip_zero_width: bool,
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
        confusables=false,
        strip_accents=false,
        fold_case=false,
        collapse_whitespace=false,
        strip_control=true,
        strip_zero_width=true,
        demojize=false,
    ))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        normalize: Option<&str>,
        transliterate: bool,
        lang: Option<&str>,
        strict_iso9: bool,
        confusables: bool,
        strip_accents: bool,
        fold_case: bool,
        collapse_whitespace: bool,
        strip_control: bool,
        strip_zero_width: bool,
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

        Ok(Self {
            steps,
            normalize_form: normalize.map(|s| s.to_owned()),
            lang: lang.map(|s| s.to_owned()),
            strict_iso9,
            strip_control,
            strip_zero_width,
        })
    }

    /// Process text through the pipeline.
    fn process(&self, text: &str) -> PyResult<String> {
        let mut buf = text.to_owned();

        // Fixed optimal order regardless of construction order:
        // 1. Normalize (canonical form first)
        if self.steps.contains(PipelineSteps::NORMALIZE) {
            if let Some(ref form) = self.normalize_form {
                buf = normalize::_normalize(&buf, form)?;
            }
        }

        // 2. Confusables (before transliteration — operates on Unicode)
        if self.steps.contains(PipelineSteps::CONFUSABLES) {
            buf = confusables::_normalize_confusables(&buf, "latin")?;
        }

        // 3. Demojize (after normalization, before transliteration)
        if self.steps.contains(PipelineSteps::DEMOJIZE) {
            buf = emoji::demojize_rust(&buf, false);
        }

        // 4. Strip accents (NFD decompose + strip combining marks)
        if self.steps.contains(PipelineSteps::STRIP_ACCENTS) {
            buf = transliterate::_strip_accents(&buf);
        }

        // 5. Transliterate (Unicode → ASCII)
        if self.steps.contains(PipelineSteps::TRANSLITERATE) {
            buf = transliterate::transliterate_impl(
                &buf,
                self.lang.as_deref(),
                transliterate::ErrorMode::Ignore,
                "",
                self.strict_iso9,
            )
            .into_owned();
        }

        // 6. Fold case (after transliteration)
        if self.steps.contains(PipelineSteps::FOLD_CASE) {
            buf = case_fold::_fold_case(&buf);
        }

        // 7. Collapse whitespace + strip control (final cleanup)
        if self.steps.contains(PipelineSteps::COLLAPSE_WS) {
            buf = whitespace::_collapse_whitespace(&buf, self.strip_control, self.strip_zero_width);
        }

        Ok(buf)
    }
}
