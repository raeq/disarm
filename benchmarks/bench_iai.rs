//! Deterministic estimated-cycle benchmarks for the CI hard gate (#234 gate V10).
//!
//! Unlike the wall-clock criterion benches, iai-callgrind runs each function once
//! under Valgrind/Callgrind with **cache simulation on**, so the gated metric is
//! **estimated cycles** — deterministic and machine-independent *within an ISA*
//! (and so safe to hard-fail on). Cache simulation (not raw instruction count) is
//! the metric, so cache-layout work (cluster C / #237) is visible to the gate.
//!
//! Doc-scale subset only (gate at doc scale — short-string numbers are
//! FFI-dominated and must never gate a core cluster). The CI workflow runs this
//! against both the PR and its merge-base and compares **directionally**
//! (regression-only).
//!
//! Requires Valgrind, so it only *runs* in Linux CI; it *compiles* anywhere
//! (the macros emit the harness; Valgrind is invoked at run time, not build time).
#![allow(missing_docs)]

use std::hint::black_box;

use disarm::api::strip_log_injection;
use disarm::api::{escape_html, percent_encode, UrlComponent};
use disarm::api::{slugify, SlugConfig};
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
            .run(black_box(&text)),
    )
    .len()
}

// Slugify identity/ASCII path and a diacritic-heavy Latin path.
#[library_benchmark]
#[bench::ascii(doc("ascii_doc"))]
#[bench::latin(doc("latin_doc"))]
fn slugify_doc(text: String) -> usize {
    let config = SlugConfig::default();
    black_box(slugify(black_box(&text), &config)).len()
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

library_benchmark_group!(
    name = perf_gate;
    // Cache simulation on → iai reports Estimated Cycles, the gated metric (V10).
    config = LibraryBenchmarkConfig::default().tool(Callgrind::with_args(["--cache-sim=yes"]));
    benchmarks = transliterate_doc, slugify_doc, escape_html_doc, percent_encode_doc, strip_log_injection_doc
);

main!(library_benchmark_groups = perf_gate);
