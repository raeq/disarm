//! Document-scale persona benchmarks tied to the optimization backlog.
#![allow(missing_docs)] // Benchmark harness code does not require documentation.
//!
//! Run with: `cargo bench --no-default-features --bench bench_personas`
//!
//! Where `bench_core.rs` measures short strings (per-call constants), this
//! file measures ~16 KiB documents (the per-character hot loop and table
//! locality), plus one group per identified optimization finding so each
//! change lands with a before/after number. See `benchmarks/README.md` for
//! the finding → benchmark mapping and the baseline workflow.

use std::collections::HashMap;
use std::hint::black_box;

use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};

use _disarm::case_fold::_fold_case;
use _disarm::presets::{_search_key, _security_clean};
use _disarm::slugify::{slugify_impl, SlugConfig};
use _disarm::transliterate::{_strip_accents, find_untranslatable_impl, transliterate_impl};
use _disarm::ErrorMode;

#[path = "persona_corpus.rs"]
mod persona_corpus;
use persona_corpus::{build_doc, PERSONAS, SHORT_ASCII, SHORT_UNICODE};

fn text_throughput(text: &str) -> Throughput {
    Throughput::ElementsAndBytes {
        elements: text.chars().count() as u64,
        bytes: text.len() as u64,
    }
}

/// Engine-only transliteration call (Ignore mode, no replacement assembly),
/// so the measurement isolates the per-character loop + table lookups.
fn engine(text: &str, lang: Option<&str>) -> usize {
    transliterate_impl(text, lang, ErrorMode::Ignore, "", false, false, false).len()
}

// ---------------------------------------------------------------------------
// Per-persona document throughput (the headline numbers)
// ---------------------------------------------------------------------------

fn bench_doc_transliterate(c: &mut Criterion) {
    let mut group = c.benchmark_group("doc_transliterate");
    for (name, seed) in PERSONAS {
        let doc = build_doc(seed);
        group.throughput(text_throughput(&doc));
        group.bench_with_input(BenchmarkId::new("default", *name), &doc, |b, text| {
            b.iter(|| engine(black_box(text), None));
        });
    }
    group.finish();
}

// ---------------------------------------------------------------------------
// Finding: per-char lang dispatch + RwLock fallback (resolve-once refactor)
// ---------------------------------------------------------------------------

fn bench_lang_dispatch(c: &mut Criterion) {
    let mut group = c.benchmark_group("lang_dispatch");

    // "ru" has a small PHF override table: most Cyrillic chars miss it and
    // fall through to the RwLock-guarded registered-table probe.
    let cyr = persona_corpus::doc("cyrillic_doc").expect("persona exists");
    group.throughput(text_throughput(&cyr));
    group.bench_function("ru_phf_mostly_miss", |b| {
        b.iter(|| engine(black_box(&cyr), Some("ru")));
    });

    // "ar" has NO PHF override table at all: every non-ASCII char takes the
    // string-match miss + RwLock probe. Worst case for the current dispatch.
    let ara = persona_corpus::doc("arabic_doc").expect("persona exists");
    group.throughput(text_throughput(&ara));
    group.bench_function("ar_no_override_table", |b| {
        b.iter(|| engine(black_box(&ara), Some("ar")));
    });

    // User-registered language: exercises the Cow::Owned clone-per-matched-char
    // path in tables::lookup_lang.
    let mut mappings = HashMap::new();
    mappings.insert("м".to_owned(), "m*".to_owned());
    mappings.insert("а".to_owned(), "a*".to_owned());
    mappings.insert("о".to_owned(), "o*".to_owned());
    _disarm::tables::register_lang("x-bench", mappings).expect("valid single-char keys");
    group.throughput(text_throughput(&cyr));
    group.bench_function("registered_lang_clone_path", |b| {
        b.iter(|| engine(black_box(&cyr), Some("x-bench")));
    });

    group.finish();
}

// ---------------------------------------------------------------------------
// Finding: strict mode collects-all-then-takes-first / double engine pass
// ---------------------------------------------------------------------------

fn bench_strict_scan(c: &mut Criterion) {
    let mut group = c.benchmark_group("strict_scan");
    for name in ["mixed_web", "cyrillic_doc"] {
        let doc = persona_corpus::doc(name).expect("persona exists");
        group.throughput(text_throughput(&doc));
        group.bench_with_input(
            BenchmarkId::new("find_untranslatable", name),
            &doc,
            |b, text| {
                b.iter(|| find_untranslatable_impl(black_box(text), None, false, false, false));
            },
        );
    }
    group.finish();
}

// ---------------------------------------------------------------------------
// Finding: slugify ASCII-identity copies (decode_entities / transliterate /
// lowercase all allocate even when nothing changes)
// ---------------------------------------------------------------------------

fn bench_slugify_doc(c: &mut Criterion) {
    let mut group = c.benchmark_group("slugify_doc");
    let config = SlugConfig::default();
    for name in ["ascii_doc", "mixed_web"] {
        let doc = persona_corpus::doc(name).expect("persona exists");
        group.throughput(text_throughput(&doc));
        group.bench_with_input(BenchmarkId::new("default", name), &doc, |b, text| {
            b.iter(|| slugify_impl(black_box(text), &config));
        });
    }
    group.finish();
}

// ---------------------------------------------------------------------------
// Finding: scalar _strip_accents lacks the ASCII fast path the batch has
// ---------------------------------------------------------------------------

fn bench_strip_accents(c: &mut Criterion) {
    let mut group = c.benchmark_group("strip_accents");
    for name in ["ascii_doc", "latin_doc"] {
        let doc = persona_corpus::doc(name).expect("persona exists");
        group.throughput(text_throughput(&doc));
        group.bench_with_input(BenchmarkId::new("scalar", name), &doc, |b, text| {
            b.iter(|| _strip_accents(black_box(text)));
        });
    }
    group.finish();
}

// ---------------------------------------------------------------------------
// Reference: case folding at document scale (ASCII fast path vs PHF path)
// ---------------------------------------------------------------------------

fn bench_fold_case_doc(c: &mut Criterion) {
    let mut group = c.benchmark_group("fold_case_doc");
    for name in ["ascii_doc", "greek_doc"] {
        let doc = persona_corpus::doc(name).expect("persona exists");
        group.throughput(text_throughput(&doc));
        group.bench_with_input(BenchmarkId::new("fold", name), &doc, |b, text| {
            b.iter(|| _fold_case(black_box(text)));
        });
    }
    group.finish();
}

// ---------------------------------------------------------------------------
// Finding: pipeline/preset step chains allocate a fresh String per step
// ---------------------------------------------------------------------------

fn bench_presets_doc(c: &mut Criterion) {
    let mut group = c.benchmark_group("presets_doc");
    let doc = persona_corpus::doc("mixed_web").expect("persona exists");
    group.throughput(text_throughput(&doc));
    group.bench_function("security_clean", |b| {
        b.iter(|| _security_clean(black_box(&doc)));
    });
    group.bench_function("search_key", |b| {
        b.iter(|| _search_key(black_box(&doc), None));
    });
    group.finish();
}

// ---------------------------------------------------------------------------
// Per-call constants on short strings (FFI-adjacent; complements bench_core)
// ---------------------------------------------------------------------------

fn bench_short_per_call(c: &mut Criterion) {
    let mut group = c.benchmark_group("short_per_call");
    let config = SlugConfig::default();
    group.bench_function("transliterate_short_ascii", |b| {
        b.iter(|| engine(black_box(SHORT_ASCII), None));
    });
    group.bench_function("transliterate_short_unicode", |b| {
        b.iter(|| engine(black_box(SHORT_UNICODE), None));
    });
    group.bench_function("slugify_short_ascii", |b| {
        b.iter(|| slugify_impl(black_box("Hello World This Is A Title"), &config));
    });
    group.finish();
}

// ---------------------------------------------------------------------------
// Finding: replace_longest_match re-sorts key lengths per call.
// Kept LAST: registering replacements flips process-global state. It does NOT
// affect transliterate_impl (replacements are applied by the PyO3 wrappers,
// not the engine), but keeping it last makes that invariant easy to audit.
// ---------------------------------------------------------------------------

const REPLACEMENT_CAP: usize = 10 * 1024 * 1024;

fn bench_replacements(c: &mut Criterion) {
    let mut group = c.benchmark_group("replacements");

    let mut reps = HashMap::new();
    reps.insert("©".to_owned(), "(c)".to_owned());
    reps.insert("™".to_owned(), "(tm)".to_owned());
    reps.insert("€".to_owned(), "EUR".to_owned());
    _disarm::tables::register_replacements(reps).expect("under MAX_REPLACEMENTS");

    // No key occurs in ascii_doc: measures the scan + per-call length-sort
    // overhead on the borrowed (no-match) path.
    let ascii = persona_corpus::doc("ascii_doc").expect("persona exists");
    group.throughput(text_throughput(&ascii));
    group.bench_function("registered_no_match", |b| {
        b.iter(|| _disarm::tables::apply_replacements(black_box(&ascii), REPLACEMENT_CAP));
    });

    // mixed_web contains ©/™/€: measures the matching + rebuild path.
    let mixed = persona_corpus::doc("mixed_web").expect("persona exists");
    group.throughput(text_throughput(&mixed));
    group.bench_function("registered_with_matches", |b| {
        b.iter(|| _disarm::tables::apply_replacements(black_box(&mixed), REPLACEMENT_CAP));
    });

    group.finish();
}

criterion_group!(
    benches,
    bench_doc_transliterate,
    bench_lang_dispatch,
    bench_strict_scan,
    bench_slugify_doc,
    bench_strip_accents,
    bench_fold_case_doc,
    bench_presets_doc,
    bench_short_per_call,
    bench_replacements,
);
criterion_main!(benches);
