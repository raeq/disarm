//! Deterministic estimated-cycle benchmarks for the CI hard gate (#234 gate V10).
//!
//! Unlike the wall-clock criterion benches, iai-callgrind runs each function once
//! under Valgrind/Callgrind with **cache simulation on**, so the gated metric is
//! **estimated cycles** — deterministic and machine-independent *within an ISA*
//! (and so safe to hard-fail on). Cache simulation (not raw instruction count) is
//! the metric, so cache-layout work (cluster C / #237) is visible to the gate.
//!
//! Mostly doc scale: the 16 KiB persona documents are where a core cluster's cost shows.
//! The `short` cases in `entry_points` are gated too, deliberately. The rule they
//! replace ("short-string numbers are FFI-dominated and must never gate a core cluster")
//! is right for the Python and criterion benches, where a short call is mostly binding
//! overhead; here there is no binding, so a short input measures the core's own per-call
//! setup, which the documents cannot see (`canonicalize` spent ~35K instructions on a
//! 12-character name when this was written). The CI workflow runs this against both the
//! PR and its merge-base and compares **directionally** (regression-only).
//!
//! Requires Valgrind, so it only *runs* in Linux CI; it *compiles* anywhere
//! (the macros emit the harness; Valgrind is invoked at run time, not build time).
#![allow(missing_docs)]

use std::hint::black_box;

use disarm::api::strip_log_injection;
use disarm::api::{canonicalize, canonicalize_strict, ml_normalize, search_key, strip_obfuscation};
use disarm::api::{escape_html, percent_encode, UrlComponent};
use disarm::api::{find_confusables, is_confusable, normalize_confusables, skeleton_key};
use disarm::api::{normalize, DigitPolicy, NormalizationForm, TargetScript};
use disarm::api::{try_slugify, SlugConfig};
use disarm::api::{OnUnknown, Transliterate};

use iai_callgrind::{
    library_benchmark, library_benchmark_group, main, Callgrind, LibraryBenchmarkConfig,
};

#[path = "persona_corpus.rs"]
mod persona_corpus;

/// Build a persona document (setup; evaluated before the measured region).
fn doc(name: &str) -> String {
    persona_corpus::doc(name).expect("persona exists")
}

/// A document the confusable fold actually rewrites: Cyrillic and Greek letters standing in
/// for Latin ones inside Latin words, among real Cyrillic and Greek words. Kept here rather
/// than in `PERSONAS`, whose corpus digest buckets the criterion history; this gate compares
/// against the merge base and has no history to bucket.
fn homoglyph_doc() -> String {
    persona_corpus::build_doc("Москва раураl Ελλάδα gооgle аррlе micrоsоft Αθήνα ")
}

/// A short, typical per-call input (a name or a field), where call overhead dominates.
fn short_unicode() -> String {
    persona_corpus::SHORT_UNICODE.to_owned()
}

// Core transliterate path across the distinct table/dispatch regimes:
// ASCII fast path, Cyrillic (lang dispatch + BMP), hanzi table, Hangul compute.
// (No `///` here: the `#[library_benchmark]` macro rejects `#[doc]` attributes.)
#[library_benchmark]
#[bench::ascii(doc("ascii_doc"))]
#[bench::cyrillic(doc("cyrillic_doc"))]
#[bench::cjk(doc("cjk_doc"))]
#[bench::hangul(doc("hangul_doc"))]
fn transliterate_doc(text: String) -> usize {
    black_box(
        Transliterate::new()
            .on_unknown(OnUnknown::Ignore)
            .try_run(black_box(&text))
            .unwrap(),
    )
    .len()
}

// Slugify identity/ASCII path and a diacritic-heavy Latin path.
#[library_benchmark]
#[bench::ascii(doc("ascii_doc"))]
#[bench::latin(doc("latin_doc"))]
fn slugify_doc(text: String) -> usize {
    let config = SlugConfig::default();
    black_box(try_slugify(black_box(&text), &config).unwrap()).len()
}

// Output encoders (#311), fresh-string regime. escape_html on metacharacter-free
// docs exercises the scan + Cow::Borrowed fast path; percent_encode exercises the
// per-byte encode loop (latin = mostly-unreserved, cyrillic = mostly %XX).
#[library_benchmark]
#[bench::ascii(doc("ascii_doc"))]
#[bench::latin(doc("latin_doc"))]
fn escape_html_doc(text: String) -> usize {
    black_box(escape_html(black_box(&text))).len()
}

#[library_benchmark]
#[bench::latin(doc("latin_doc"))]
#[bench::cyrillic(doc("cyrillic_doc"))]
fn percent_encode_doc(text: String) -> usize {
    black_box(percent_encode(black_box(&text), UrlComponent::Query)).len()
}

// strip_log_injection (#307): clean docs exercise the scan + Cow::Borrowed fast
// path (the common all-printable line).
#[library_benchmark]
#[bench::ascii(doc("ascii_doc"))]
#[bench::cyrillic(doc("cyrillic_doc"))]
fn strip_log_injection_doc(text: String) -> usize {
    black_box(
        strip_log_injection(black_box(&text), black_box("\u{FFFD}"), black_box(false)).unwrap(),
    )
    .len()
}

// ── Romanization, the main entry point: one input per table regime, plus a short call ──
#[library_benchmark]
#[bench::latin(doc("latin_doc"))]
#[bench::mixed_web(doc("mixed_web"))]
#[bench::greek(doc("greek_doc"))]
#[bench::arabic(doc("arabic_doc"))]
#[bench::devanagari(doc("devanagari_doc"))]
#[bench::short(short_unicode())]
fn transliterate_more(text: String) -> usize {
    black_box(disarm::api::transliterate(black_box(&text))).len()
}

// ── Normalization presets ──────────────────────────────────────────────────────────────
#[library_benchmark]
#[bench::ascii(doc("ascii_doc"))]
#[bench::mixed_web(doc("mixed_web"))]
#[bench::homoglyph(homoglyph_doc())]
#[bench::short(short_unicode())]
fn canonicalize_doc(text: String) -> usize {
    black_box(canonicalize(black_box(&text)).unwrap()).len()
}

#[library_benchmark]
#[bench::mixed_web(doc("mixed_web"))]
#[bench::homoglyph(homoglyph_doc())]
fn canonicalize_strict_doc(text: String) -> usize {
    black_box(canonicalize_strict(black_box(&text)).unwrap()).len()
}

#[library_benchmark]
#[bench::mixed_web(doc("mixed_web"))]
#[bench::homoglyph(homoglyph_doc())]
#[bench::short(short_unicode())]
fn strip_obfuscation_doc(text: String) -> usize {
    black_box(strip_obfuscation(black_box(&text)).unwrap()).len()
}

#[library_benchmark]
#[bench::mixed_web(doc("mixed_web"))]
#[bench::cyrillic(doc("cyrillic_doc"))]
fn ml_normalize_doc(text: String) -> usize {
    black_box(ml_normalize(black_box(&text), None, "cldr", true).unwrap()).len()
}

#[library_benchmark]
#[bench::latin(doc("latin_doc"))]
#[bench::cyrillic(doc("cyrillic_doc"))]
#[bench::short(short_unicode())]
fn search_key_doc(text: String) -> usize {
    black_box(search_key(black_box(&text), None).unwrap()).len()
}

#[library_benchmark]
#[bench::mixed_web(doc("mixed_web"))]
#[bench::latin(doc("latin_doc"))]
fn nfkc_doc(text: String) -> usize {
    black_box(normalize(black_box(&text), NormalizationForm::Nfkc)).len()
}

// ── Confusables ────────────────────────────────────────────────────────────────────────
#[library_benchmark]
#[bench::ascii(doc("ascii_doc"))]
#[bench::cyrillic(doc("cyrillic_doc"))]
#[bench::homoglyph(homoglyph_doc())]
#[bench::short(short_unicode())]
fn normalize_confusables_doc(text: String) -> usize {
    black_box(normalize_confusables(black_box(&text), TargetScript::Latin)).len()
}

#[library_benchmark]
#[bench::homoglyph(homoglyph_doc())]
fn find_confusables_doc(text: String) -> usize {
    black_box(find_confusables(black_box(&text), TargetScript::Latin)).len()
}

#[library_benchmark]
#[bench::ascii(doc("ascii_doc"))]
#[bench::homoglyph(homoglyph_doc())]
fn is_confusable_doc(text: String) -> bool {
    black_box(is_confusable(black_box(&text), TargetScript::Latin))
}

#[library_benchmark]
#[bench::latin(doc("latin_doc"))]
#[bench::homoglyph(homoglyph_doc())]
fn skeleton_key_doc(text: String) -> usize {
    black_box(skeleton_key(black_box(&text), DigitPolicy::Numeric).unwrap()).len()
}

library_benchmark_group!(
    name = perf_gate;
    // Cache simulation on → iai reports Estimated Cycles, the gated metric (V10).
    config = LibraryBenchmarkConfig::default().tool(Callgrind::with_args(["--cache-sim=yes"]));
    benchmarks = transliterate_doc, slugify_doc, escape_html_doc, percent_encode_doc, strip_log_injection_doc
);

// The main entry points: romanization, the normalization presets and the confusable fold.
// Same cache-simulated config, so every group is gated on estimated cycles.
library_benchmark_group!(
    name = entry_points;
    config = LibraryBenchmarkConfig::default().tool(Callgrind::with_args(["--cache-sim=yes"]));
    benchmarks = transliterate_more, canonicalize_doc, canonicalize_strict_doc,
        strip_obfuscation_doc, ml_normalize_doc, search_key_doc, nfkc_doc,
        normalize_confusables_doc, find_confusables_doc, is_confusable_doc, skeleton_key_doc
);

main!(library_benchmark_groups = perf_gate, entry_points);
