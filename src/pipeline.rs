use std::borrow::Cow;

use pyo3::prelude::*;

use bitflags::bitflags;

use crate::{case_fold, confusables, emoji, normalize, transliterate, whitespace, zalgo};

bitflags! {
    #[derive(Debug, Clone, Copy, PartialEq, Eq)]
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
        const STRIP_BIDI       = 0b10_0000_0000;
        const STRIP_ZALGO      = 0b100_0000_0000;
    }
}

/// The single source of truth for pipeline step ordering (#174).
///
/// BOTH `process()` (execution) and `steps()` (introspection/`__repr__`) iterate
/// this one list, so the order a pipeline *reports* can never diverge from the
/// order it *runs* — structurally preventing the #141-class bug where reported
/// and executed positions drifted apart. To add a step: add its flag here in the
/// correct position and handle it in `apply_step`. Do not encode order anywhere
/// else.
///
/// Transliterate runs BEFORE confusables so non-Latin scripts are fully
/// romanized before confusable normalization; running confusables first on
/// Cyrillic/Greek text creates mixed-script gibberish because only some
/// characters have Latin confusables.
const STEP_ORDER: &[(PipelineSteps, &str)] = &[
    (PipelineSteps::NORMALIZE, "normalize"),
    (PipelineSteps::STRIP_ZALGO, "strip_zalgo"),
    (PipelineSteps::STRIP_BIDI, "strip_bidi"),
    (PipelineSteps::DEMOJIZE, "demojize"),
    (PipelineSteps::STRIP_ACCENTS, "strip_accents"),
    (PipelineSteps::TRANSLITERATE, "transliterate"),
    (PipelineSteps::CONFUSABLES, "confusables"),
    (PipelineSteps::FOLD_CASE, "fold_case"),
    (PipelineSteps::STRIP_CONTROL, "strip_control"),
    (PipelineSteps::STRIP_ZERO_WIDTH, "strip_zero_width"),
    (PipelineSteps::COLLAPSE_WS, "collapse_whitespace"),
];

/// Composable, pre-compiled text cleaning pipeline.
#[pyclass]
#[pyo3(name = "_TextPipeline")]
pub struct _TextPipeline {
    steps: PipelineSteps,
    normalize_form: Option<String>,
    zalgo_max_marks: Option<usize>,
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
        strip_bidi=false,
        strip_zalgo=None,
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
        strip_bidi: bool,
        strip_zalgo: Option<i64>,
    ) -> PyResult<Self> {
        let mut steps = PipelineSteps::empty();

        if let Some(form) = normalize {
            // Validate the form
            if !matches!(form, "NFC" | "NFD" | "NFKC" | "NFKD") {
                return Err(crate::Error::InvalidPipelineNormForm {
                    got: form.to_owned(),
                }
                .into());
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
        if strip_bidi {
            steps |= PipelineSteps::STRIP_BIDI;
        }

        // strip_zalgo's value is `max_marks`, which must be >= 0. Validate here
        // in the core — `new()` is the construction boundary for every caller,
        // not just the Python wrapper — so a negative can never reach the
        // `as usize` cast below, where it would silently wrap into an enormous
        // cap (effectively disabling the step) instead of being rejected.
        let zalgo_max_marks = match strip_zalgo {
            Some(n) if n < 0 => {
                return Err(crate::InvalidArgumentError::new_err(format!(
                    "strip_zalgo (max_marks) must be non-negative, got {n}"
                )));
            }
            Some(n) => {
                steps |= PipelineSteps::STRIP_ZALGO;
                Some(n as usize)
            }
            None => None,
        };

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
            return Err(crate::Error::MutuallyExclusivePipeline.into());
        }

        let pipeline = Self {
            steps,
            normalize_form: normalize.map(std::borrow::ToOwned::to_owned),
            zalgo_max_marks,
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
    /// Iterates the shared [`STEP_ORDER`] source, so the reported order is by
    /// construction the same order `process()` executes (#174).
    fn steps(&self) -> Vec<(String, Option<String>)> {
        STEP_ORDER
            .iter()
            .filter(|(flag, _)| self.steps.contains(*flag))
            .map(|(flag, name)| ((*name).to_owned(), self.step_param(*flag)))
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
    /// Iterates the single [`STEP_ORDER`] source so the execution order is, by
    /// construction, the order `steps()` reports — there is no second list to
    /// drift out of sync (#174). Each active step is applied as its own pass via
    /// `apply_step`.
    ///
    /// Uses `Cow<str>` to avoid cloning the input when no steps modify it
    /// (e.g. empty pipeline, or input that passes through unchanged).
    ///
    /// Note: the strip_control + strip_zero_width + collapse_whitespace tail
    /// now runs as up to three separate passes rather than the previous fused
    /// single pass. The result is identical — control and zero-width characters
    /// are transparent to whitespace-run collapsing whether skipped inline or
    /// removed first — at the cost of two extra linear scans over the (by then
    /// usually short, ASCII) tail. Correctness of the single source of truth is
    /// worth more than that micro-optimization; the fused `_collapse_whitespace`
    /// remains available to direct callers.
    fn process(&self, text: &str) -> PyResult<String> {
        // #236 item 7: ping-pong two reusable buffers across the active steps
        // instead of allocating a fresh String per step. `cur` holds the current
        // text; each step writes its output into `scratch` (reusing its
        // capacity), then we swap — recycling `cur`'s old allocation into
        // `scratch` for the next step. The number of live/reused buffers is O(1)
        // (two) regardless of step count; a buffer may still *grow* (realloc)
        // when a step's output exceeds its current capacity (e.g. demojize or
        // case-fold expansions), but once both buffers reach the largest
        // intermediate size, later steps reuse them with no further allocation.
        let mut cur = text.to_owned();
        let mut scratch = String::new();
        for (flag, _name) in STEP_ORDER {
            if self.steps.contains(*flag) && self.apply_step_into(*flag, &cur, &mut scratch)? {
                std::mem::swap(&mut cur, &mut scratch);
            }
        }
        Ok(cur)
    }
}

impl _TextPipeline {
    /// Apply one pipeline step, writing the transformed text into `out` (the
    /// reused scratch buffer). Returns `true` when `out` holds the result (the
    /// caller swaps it in) or `false` for a no-op (input unchanged, `out` left
    /// untouched as a spare buffer).
    ///
    /// Called only with single-flag values from [`STEP_ORDER`]: `process()` owns
    /// the *ordering* (by iterating that one list), this owns the *per-step
    /// transform*. Every flag in `STEP_ORDER` must be handled here — an
    /// unhandled flag would silently no-op, which
    /// `every_step_in_order_is_actually_applied` guards against.
    fn apply_step_into(
        &self,
        step: PipelineSteps,
        input: &str,
        out: &mut String,
    ) -> PyResult<bool> {
        if step == PipelineSteps::NORMALIZE {
            match self.normalize_form {
                Some(ref form) => {
                    normalize::normalize_into(input, form, out)?;
                    Ok(true)
                }
                None => Ok(false),
            }
        } else if step == PipelineSteps::STRIP_ZALGO {
            zalgo::strip_zalgo_into(input, self.zalgo_max_marks.unwrap_or(0), out);
            Ok(true)
        } else if step == PipelineSteps::STRIP_BIDI {
            crate::presets::strip_bidi_into(input, out);
            Ok(true)
        } else if step == PipelineSteps::DEMOJIZE {
            emoji::demojize_rust_into(input, false, out);
            Ok(true)
        } else if step == PipelineSteps::STRIP_ACCENTS {
            transliterate::strip_accents_into(input, out);
            Ok(true)
        } else if step == PipelineSteps::TRANSLITERATE {
            // #236 item 5: only reallocate when transliterate actually changed
            // the text. On a borrowed (ASCII / no-op) result, signal no-op so the
            // pipeline keeps `cur` unchanged. On an owned result, move its buffer
            // into `out` (no copy) for the caller to swap in.
            match transliterate::transliterate_impl(
                input,
                self.lang.as_deref(),
                crate::ErrorMode::Ignore,
                "",
                self.strict_iso9,
                self.gost7034,
                false,
            ) {
                Cow::Borrowed(_) => Ok(false),
                Cow::Owned(s) => {
                    *out = s;
                    Ok(true)
                }
            }
        } else if step == PipelineSteps::CONFUSABLES {
            confusables::normalize_confusables_into(input, "latin", out)?;
            Ok(true)
        } else if step == PipelineSteps::FOLD_CASE {
            case_fold::fold_case_into(input, out);
            Ok(true)
        } else if step == PipelineSteps::STRIP_CONTROL {
            whitespace::strip_control_chars_into(input, out);
            Ok(true)
        } else if step == PipelineSteps::STRIP_ZERO_WIDTH {
            whitespace::strip_zero_width_chars_into(input, out);
            Ok(true)
        } else if step == PipelineSteps::COLLAPSE_WS {
            // Collapse only — strip_control / strip_zero_width are their own
            // steps. With both flags false this preserves any control and
            // zero-width characters those steps didn't run, collapsing solely
            // whitespace runs.
            whitespace::collapse_whitespace_into(input, false, false, out);
            Ok(true)
        } else {
            Ok(false)
        }
    }

    /// The parameter shown for `step` in `steps()` / `__repr__`, or `None`.
    fn step_param(&self, step: PipelineSteps) -> Option<String> {
        if step == PipelineSteps::NORMALIZE {
            self.normalize_form.clone()
        } else if step == PipelineSteps::STRIP_ZALGO {
            self.zalgo_max_marks.map(|m| m.to_string())
        } else if step == PipelineSteps::CONFUSABLES {
            Some("latin".to_owned())
        } else if step == PipelineSteps::TRANSLITERATE {
            self.lang.clone()
        } else {
            None
        }
    }
}

// ── Named policy profiles (#229) ──────────────────────────────────────────
//
// The single source of truth for the named profiles that `get_pipeline` builds.
// Previously this registry lived in Python (`_presets.py::_POLICY_PROFILES`),
// duplicating pipeline knowledge that only the Rust core executes; defining it
// here means every binding shares one definition (#179).

/// A named profile's `_TextPipeline` configuration. Field names and defaults
/// mirror `_TextPipeline::new`.
#[derive(Default)]
struct ProfileSpec {
    normalize: Option<&'static str>,
    transliterate: bool,
    strict_iso9: bool,
    confusables: bool,
    strip_accents: bool,
    fold_case: bool,
    collapse_whitespace: bool,
    strip_control: Option<bool>,
    strip_zero_width: Option<bool>,
    demojize: bool,
    strip_bidi: bool,
    strip_zalgo: Option<i64>,
}

impl ProfileSpec {
    fn build(&self) -> PyResult<_TextPipeline> {
        _TextPipeline::new(
            self.normalize,
            self.transliterate,
            None, // lang
            self.strict_iso9,
            false, // gost7034
            self.confusables,
            self.strip_accents,
            self.fold_case,
            self.collapse_whitespace,
            self.strip_control,
            self.strip_zero_width,
            self.demojize,
            self.strip_bidi,
            self.strip_zalgo,
        )
    }
}

/// Profile names, sorted (matches the previous `list_profiles()` ordering).
const PROFILE_NAMES: &[&str] = &[
    "library_catalog_key_eu",
    "llm_guardrail",
    "ml_corpus_normalize",
    "rag_ingest",
    "scholarly_cyrillic_iso9",
    "search_index",
    "web_input_sanitize",
];

fn profile_spec(name: &str) -> Option<ProfileSpec> {
    Some(match name {
        "scholarly_cyrillic_iso9" => ProfileSpec {
            normalize: Some("NFKC"),
            transliterate: true,
            strict_iso9: true,
            fold_case: true,
            collapse_whitespace: true,
            ..ProfileSpec::default()
        },
        "library_catalog_key_eu" => ProfileSpec {
            normalize: Some("NFKC"),
            transliterate: true,
            confusables: true,
            strip_accents: true,
            fold_case: true,
            collapse_whitespace: true,
            ..ProfileSpec::default()
        },
        "web_input_sanitize" => ProfileSpec {
            normalize: Some("NFKC"),
            confusables: true,
            collapse_whitespace: true,
            ..ProfileSpec::default()
        },
        "ml_corpus_normalize" => ProfileSpec {
            normalize: Some("NFKC"),
            demojize: true,
            strip_accents: true,
            fold_case: true,
            collapse_whitespace: true,
            ..ProfileSpec::default()
        },
        "search_index" => ProfileSpec {
            normalize: Some("NFKC"),
            transliterate: true,
            strip_accents: true,
            fold_case: true,
            collapse_whitespace: true,
            ..ProfileSpec::default()
        },
        "llm_guardrail" => ProfileSpec {
            normalize: Some("NFKC"),
            strip_zalgo: Some(0),
            strip_bidi: true,
            strip_zero_width: Some(true),
            strip_control: Some(true),
            demojize: true,
            confusables: true,
            strip_accents: true,
            fold_case: true,
            collapse_whitespace: true,
            ..ProfileSpec::default()
        },
        // rag_ingest canonicalizes by phonetic *romanization* (transliterate),
        // NOT visual homoglyph folding (#258). Because STEP_ORDER runs
        // transliterate before confusables (#174), adding `confusables` here
        // would be a no-op — transliterate has already consumed the non-Latin
        // characters (a Cyrillic look-alike of "paypal" romanizes to "raural", a
        // distinct key, rather than folding to "paypal"). That is intentional: it
        // romanizes legitimate non-Latin for retrieval (Москва → Moskva) without
        // mangling it into mixed-script gibberish. For homoglyph-spoof folding
        // (fold the spoof onto the term it imitates) use `llm_guardrail`.
        "rag_ingest" => ProfileSpec {
            normalize: Some("NFKC"),
            strip_bidi: true,
            strip_control: Some(true),
            strip_zero_width: Some(true),
            transliterate: true,
            strip_accents: true,
            collapse_whitespace: true,
            ..ProfileSpec::default()
        },
        _ => return None,
    })
}

/// Build the `_TextPipeline` for a named policy profile (`get_pipeline`).
#[pyfunction]
pub fn _get_pipeline(profile: &str) -> PyResult<_TextPipeline> {
    match profile_spec(profile) {
        Some(spec) => spec.build(),
        None => Err(crate::InvalidArgumentError::new_err(format!(
            "Unknown profile {profile:?}; available: {}",
            PROFILE_NAMES.join(", ")
        ))),
    }
}

/// Sorted names of the available named policy profiles (`list_profiles`).
#[pyfunction]
pub fn _list_profiles() -> Vec<String> {
    PROFILE_NAMES.iter().map(|s| (*s).to_owned()).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── Helper to build a pipeline from bitflags ────────────────────
    fn pipeline(steps: PipelineSteps, normalize_form: Option<&str>) -> _TextPipeline {
        _TextPipeline {
            steps,
            normalize_form: normalize_form.map(ToOwned::to_owned),
            zalgo_max_marks: None,
            lang: None,
            strict_iso9: false,
            gost7034: false,
        }
    }

    // ── Ordering invariant: the single source of truth (#174) ───────
    //
    // These lock the structural guarantee that `steps()` (reporting) and
    // `process()` (execution) cannot drift apart, the #141-class bug class.

    #[test]
    fn step_order_lists_every_flag_exactly_once() {
        // If a new PipelineSteps flag is added but not registered in STEP_ORDER,
        // it would be neither executed nor reported. This fails loudly instead.
        let mut seen = PipelineSteps::empty();
        for (flag, _name) in STEP_ORDER {
            assert!(
                !seen.contains(*flag),
                "STEP_ORDER lists {flag:?} more than once"
            );
            seen |= *flag;
        }
        assert_eq!(
            seen,
            PipelineSteps::all(),
            "STEP_ORDER must list every PipelineSteps flag exactly once"
        );
    }

    #[test]
    fn every_step_in_order_is_actually_applied() {
        // For each step, a pipeline with ONLY that step enabled must change a
        // witness input — proving apply_step has a real branch for the flag
        // rather than silently falling through to the `else { buf }` arm. A new
        // step added to STEP_ORDER without a witness here panics, forcing the
        // author to exercise its apply_step branch.
        for (flag, name) in STEP_ORDER {
            let (form, input): (Option<&str>, &str) = if *flag == PipelineSteps::NORMALIZE {
                (Some("NFC"), "e\u{0301}") // e + combining acute → é
            } else if *flag == PipelineSteps::STRIP_ZALGO {
                (None, "a\u{0301}\u{0301}\u{0301}\u{0301}b")
            } else if *flag == PipelineSteps::STRIP_BIDI {
                (None, "a\u{202e}b")
            } else if *flag == PipelineSteps::DEMOJIZE {
                (None, "\u{2615}") // ☕
            } else if *flag == PipelineSteps::STRIP_ACCENTS {
                (None, "é")
            } else if *flag == PipelineSteps::TRANSLITERATE {
                (None, "Москва")
            } else if *flag == PipelineSteps::CONFUSABLES {
                (None, "\u{0410}pple") // Cyrillic А
            } else if *flag == PipelineSteps::FOLD_CASE {
                (None, "ABC")
            } else if *flag == PipelineSteps::STRIP_CONTROL {
                (None, "a\u{0000}b")
            } else if *flag == PipelineSteps::STRIP_ZERO_WIDTH {
                (None, "a\u{200b}b")
            } else if *flag == PipelineSteps::COLLAPSE_WS {
                (None, "a  b")
            } else {
                panic!(
                    "no witness for new step '{name}'; add one so apply_step coverage stays gated"
                );
            };
            let out = pipeline(*flag, form).process(input).unwrap();
            assert_ne!(
                out, input,
                "step '{name}' left its witness unchanged — apply_step may be missing a branch"
            );
        }
    }

    /// Independent oracle: apply each active step via the public *returning*
    /// functions (the pre-#236-item-7 strategy), used to prove the new
    /// double-buffered `process()` produces byte-identical output.
    fn process_via_returning_fns(p: &_TextPipeline, text: &str) -> PyResult<String> {
        let mut s = text.to_owned();
        for (flag, _name) in STEP_ORDER {
            if !p.steps.contains(*flag) {
                continue;
            }
            s = if *flag == PipelineSteps::NORMALIZE {
                match p.normalize_form {
                    Some(ref form) => normalize::_normalize(&s, form)?,
                    None => s,
                }
            } else if *flag == PipelineSteps::STRIP_ZALGO {
                zalgo::_strip_zalgo(&s, p.zalgo_max_marks.unwrap_or(0))
            } else if *flag == PipelineSteps::STRIP_BIDI {
                crate::presets::_strip_bidi(&s)
            } else if *flag == PipelineSteps::DEMOJIZE {
                emoji::demojize_rust(&s, false)
            } else if *flag == PipelineSteps::STRIP_ACCENTS {
                transliterate::_strip_accents(&s)
            } else if *flag == PipelineSteps::TRANSLITERATE {
                transliterate::transliterate_impl(
                    &s,
                    p.lang.as_deref(),
                    crate::ErrorMode::Ignore,
                    "",
                    p.strict_iso9,
                    p.gost7034,
                    false,
                )
                .into_owned()
            } else if *flag == PipelineSteps::CONFUSABLES {
                confusables::_normalize_confusables(&s, "latin")?
            } else if *flag == PipelineSteps::FOLD_CASE {
                case_fold::fold_case_impl(&s)
            } else if *flag == PipelineSteps::STRIP_CONTROL {
                whitespace::strip_control_chars(&s)
            } else if *flag == PipelineSteps::STRIP_ZERO_WIDTH {
                whitespace::strip_zero_width_chars(&s)
            } else if *flag == PipelineSteps::COLLAPSE_WS {
                whitespace::_collapse_whitespace(&s, false, false)
            } else {
                s
            };
        }
        Ok(s)
    }

    #[test]
    fn double_buffer_process_matches_returning_fns() {
        // #236 item 7: the ping-pong double-buffer `process()` must be
        // byte-identical to applying each step's returning function in order.
        let inputs = [
            "",
            "hello world",
            "Héllo  WÖRLD",
            "café ☕ résumé 👨‍👩‍👧‍👦",
            "Ｆｕｌｌｗｉｄｔｈ ＡＢＣ",
            "a\u{0301}\u{0301}\u{0301}\u{0301}b zalgo",
            "x\u{202e}rtl\u{202c}y",
            "Привет, мир! Москва",
            "北京 Beijing 2008",
            "  leading and   trailing  ",
            "a\u{0000}\u{200b}\u{feff}b",
            "\u{0410}pple \u{0405}cam", // Cyrillic homoglyphs
        ];

        let mut all = pipeline(PipelineSteps::all(), Some("NFKC"));
        all.lang = Some("ru".to_owned());

        let mut translit = pipeline(
            PipelineSteps::NORMALIZE
                | PipelineSteps::TRANSLITERATE
                | PipelineSteps::STRIP_ACCENTS
                | PipelineSteps::FOLD_CASE
                | PipelineSteps::COLLAPSE_WS,
            Some("NFKC"),
        );
        translit.lang = Some("ru".to_owned());

        let security = pipeline(
            PipelineSteps::NORMALIZE
                | PipelineSteps::CONFUSABLES
                | PipelineSteps::STRIP_BIDI
                | PipelineSteps::COLLAPSE_WS,
            Some("NFKC"),
        );

        let empty = pipeline(PipelineSteps::empty(), None);

        for p in [&all, &translit, &security, &empty] {
            for input in inputs {
                assert_eq!(
                    p.process(input).unwrap(),
                    process_via_returning_fns(p, input).unwrap(),
                    "double-buffer output diverged for steps={:?} input={input:?}",
                    p.steps
                );
            }
        }
    }

    #[test]
    fn report_order_equals_execution_order() {
        // steps() must report in the same order process() runs. With every step
        // enabled, the reported names must equal STEP_ORDER's names in order —
        // both derive from the one list, so this pins that they keep doing so.
        let mut p = pipeline(PipelineSteps::all(), Some("NFKC"));
        // strict_iso9/gost7034 are mutually exclusive and unrelated to ordering.
        p.lang = Some("ru".to_owned());
        let reported: Vec<String> = p.steps().into_iter().map(|(name, _)| name).collect();
        let expected: Vec<String> = STEP_ORDER
            .iter()
            .map(|(_, name)| (*name).to_owned())
            .collect();
        assert_eq!(reported, expected);
    }

    #[test]
    fn whitespace_tail_matches_former_fused_pass() {
        // The three-pass strip_control → strip_zero_width → collapse tail must
        // equal the old fused _collapse_whitespace(_, true, true) it replaced,
        // including for chars that are both control and whitespace-adjacent.
        let tail = PipelineSteps::STRIP_CONTROL
            | PipelineSteps::STRIP_ZERO_WIDTH
            | PipelineSteps::COLLAPSE_WS;
        let p = pipeline(tail, None);
        for input in [
            "a\nb",
            "a\t\tb",
            "a\u{0000}\nb",
            "a \u{200b} b",
            "a\n\n  b\tc",
            "  lead\u{0000}ing \u{200d} trail  ",
            "\u{feff}bom\rcr",
        ] {
            assert_eq!(
                p.process(input).unwrap(),
                whitespace::_collapse_whitespace(input, true, true),
                "tail diverged from fused pass for {input:?}"
            );
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

    #[test]
    fn test_pipeline_strip_bidi_only() {
        let p = pipeline(PipelineSteps::STRIP_BIDI, None);
        // U+202E (Right-to-Left Override) is removed
        let result = p.process("ad\u{202E}min").unwrap();
        assert!(
            !result.contains('\u{202E}'),
            "bidi not stripped: {result:?}"
        );
        assert_eq!(result, "admin");
    }

    #[test]
    fn test_pipeline_strip_zalgo_only() {
        // max_marks 0 strips all stacked combining marks
        let mut p = pipeline(PipelineSteps::STRIP_ZALGO, None);
        p.zalgo_max_marks = Some(0);
        // "a" + 4 stacked combining acute accents
        let input = "a\u{0301}\u{0301}\u{0301}\u{0301}b";
        let result = p.process(input).unwrap();
        assert!(
            result
                .chars()
                .all(|c| !unicode_normalization::char::is_combining_mark(c)),
            "combining marks not stripped: {result:?}"
        );
        assert_eq!(result, "ab");
    }

    #[test]
    fn test_pipeline_strip_zalgo_and_bidi_steps_report() {
        let mut p = pipeline(PipelineSteps::STRIP_ZALGO | PipelineSteps::STRIP_BIDI, None);
        p.zalgo_max_marks = Some(0);
        let steps = p.steps();
        assert_eq!(
            steps,
            vec![
                ("strip_zalgo".to_owned(), Some("0".to_owned())),
                ("strip_bidi".to_owned(), None),
            ]
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
                "strip_zalgo",
                "strip_bidi",
                "demojize",
                "strip_accents",
                "transliterate",
                "confusables",
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
            None, false, None, false, false, false, false, false, true,  // collapse_whitespace
            None,  // strip_control (defaults to collapse_whitespace=true)
            None,  // strip_zero_width (defaults to collapse_whitespace=true)
            false, // demojize
            false, // strip_bidi
            None,  // strip_zalgo
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
            false,       // demojize
            false,       // strip_bidi
            None,        // strip_zalgo
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
            false,      // demojize
            false,      // strip_bidi
            None,       // strip_zalgo
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
            None, false, None, false, false, false, false, false, false, None, None, false, false,
            None,
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
