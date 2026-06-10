//! Criterion benchmarks for translit core transforms.
#![allow(missing_docs)] // Benchmark harness code does not require documentation.
//!
//! Run with: `cargo bench --no-default-features`
//!
//! These benchmarks measure the pure-Rust implementation functions
//! directly, without PyO3 boundary-crossing overhead.

use std::hint::black_box;

use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};

use _translit::case_fold::_fold_case;
use _translit::confusables::_normalize_confusables;
use _translit::grapheme::{_grapheme_len, _grapheme_split};
use _translit::scripts::{_detect_scripts, _is_mixed_script};
use _translit::slugify::{slugify_impl, SlugConfig};
use _translit::tables::lookup_default;
use _translit::transliterate::transliterate_impl;
use _translit::whitespace::_collapse_whitespace;
use _translit::ErrorMode;

// ---------------------------------------------------------------------------
// Input corpus
// ---------------------------------------------------------------------------

const ASCII_SHORT: &str = "hello world";
const ASCII_LONG: &str = "The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs. How vexingly quick daft zebras jump.";
const LATIN_DIACRITICS: &str = "café résumé naïve Ångström";
const CYRILLIC: &str = "Москва — столица России";
const CJK: &str = "北京是中国的首都";
const MIXED_SCRIPT: &str = "Hello Мир 世界 café";
const EMOJI_TEXT: &str = "Hello 👨‍👩‍👧‍👦 World 🌍🎉";
const WHITESPACE_MESSY: &str = "  hello   \t  world  \n  foo  \u{200B}  bar  \u{2060}  ";

/// Throughput for a string-keyed benchmark: characters (the primary, meaningful
/// unit here) and bytes, so criterion 0.8 reports both chars/sec and bytes/sec
/// (#162). Elements are chars rather than bytes because the transforms are
/// codepoint-oriented.
fn text_throughput(text: &str) -> Throughput {
    Throughput::ElementsAndBytes {
        elements: text.chars().count() as u64,
        bytes: text.len() as u64,
    }
}

// ---------------------------------------------------------------------------
// Transliteration benchmarks
// ---------------------------------------------------------------------------

fn bench_transliterate(c: &mut Criterion) {
    let mut group = c.benchmark_group("transliterate");

    for (name, input) in [
        ("ascii_short", ASCII_SHORT),
        ("ascii_long", ASCII_LONG),
        ("latin_diacritics", LATIN_DIACRITICS),
        ("cyrillic", CYRILLIC),
        ("cjk", CJK),
        ("mixed_script", MIXED_SCRIPT),
    ] {
        group.throughput(text_throughput(input));
        group.bench_with_input(BenchmarkId::new("default", name), input, |b, text| {
            b.iter(|| {
                transliterate_impl(
                    black_box(text),
                    None,
                    ErrorMode::Replace,
                    "[?]",
                    false,
                    false,
                    false,
                )
            });
        });
    }

    // Language-specific transliteration
    group.throughput(text_throughput(CYRILLIC));
    group.bench_function("cyrillic_lang_ru", |b| {
        b.iter(|| {
            transliterate_impl(
                black_box(CYRILLIC),
                Some("ru"),
                ErrorMode::Replace,
                "[?]",
                false,
                false,
                false,
            )
        });
    });

    group.finish();
}

// ---------------------------------------------------------------------------
// Table lookup benchmarks
// ---------------------------------------------------------------------------

fn bench_table_lookup(c: &mut Criterion) {
    let mut group = c.benchmark_group("table_lookup");

    group.bench_function("latin_extended_e_acute", |b| {
        b.iter(|| lookup_default(black_box('é')));
    });

    group.bench_function("cyrillic_zhe", |b| {
        b.iter(|| lookup_default(black_box('Ж')));
    });

    group.bench_function("cjk_bei", |b| {
        b.iter(|| lookup_default(black_box('北')));
    });

    group.bench_function("hangul_han", |b| {
        b.iter(|| lookup_default(black_box('한')));
    });

    group.bench_function("ascii_passthrough", |b| {
        b.iter(|| lookup_default(black_box('a')));
    });

    group.finish();
}

// ---------------------------------------------------------------------------
// Slugify benchmarks
// ---------------------------------------------------------------------------

fn bench_slugify(c: &mut Criterion) {
    let mut group = c.benchmark_group("slugify");

    let default_config = SlugConfig::default();

    for (name, input) in [
        ("ascii_title", "Hello World This Is A Title"),
        ("unicode_title", "Héllo Wörld Straße München"),
        ("long_text", "The Quick Brown Fox Jumps Over The Lazy Dog And Then Some More Words To Make It Long Enough"),
    ] {
        group.throughput(text_throughput(input));
        group.bench_with_input(BenchmarkId::new("default", name), input, |b, text| {
            b.iter(|| slugify_impl(black_box(text), &default_config));
        });
    }

    // With max_length + word_boundary
    let bounded_config = SlugConfig {
        max_length: 30,
        word_boundary: true,
        ..SlugConfig::default()
    };
    let bounded_input = "The Quick Brown Fox Jumps Over The Lazy Dog";
    group.throughput(text_throughput(bounded_input));
    group.bench_function("bounded_30_word_boundary", |b| {
        b.iter(|| slugify_impl(black_box(bounded_input), &bounded_config));
    });

    group.finish();
}

// ---------------------------------------------------------------------------
// Case folding benchmarks
// ---------------------------------------------------------------------------

fn bench_fold_case(c: &mut Criterion) {
    let mut group = c.benchmark_group("fold_case");

    for (name, input) in [
        ("ascii_short", "HELLO WORLD"),
        ("ascii_long", ASCII_LONG),
        ("latin_diacritics", "CAFÉ RÉSUMÉ NAÏVE ÅNGSTRÖM"),
        ("german_eszett", "GROSSE STRAßE"),
        ("greek", "ΣΟΦΙΑ ΕΛΛΗΝΙΚΑ"),
        ("mixed", "Hello Мир WORLD Straße"),
    ] {
        group.throughput(text_throughput(input));
        group.bench_with_input(BenchmarkId::new("fold", name), input, |b, text| {
            b.iter(|| _fold_case(black_box(text)));
        });
    }

    group.finish();
}

// ---------------------------------------------------------------------------
// Whitespace benchmarks
// ---------------------------------------------------------------------------

fn bench_whitespace(c: &mut Criterion) {
    let mut group = c.benchmark_group("whitespace");

    group.throughput(text_throughput(WHITESPACE_MESSY));
    group.bench_function("messy_full_strip", |b| {
        b.iter(|| _collapse_whitespace(black_box(WHITESPACE_MESSY), true, true));
    });

    group.bench_function("messy_no_strip", |b| {
        b.iter(|| _collapse_whitespace(black_box(WHITESPACE_MESSY), false, false));
    });

    group.throughput(text_throughput("hello world"));
    group.bench_function("clean_passthrough", |b| {
        b.iter(|| _collapse_whitespace(black_box("hello world"), true, true));
    });

    group.finish();
}

// ---------------------------------------------------------------------------
// Script detection benchmarks
// ---------------------------------------------------------------------------

fn bench_scripts(c: &mut Criterion) {
    let mut group = c.benchmark_group("scripts");

    for (name, input) in [
        ("ascii_only", ASCII_SHORT),
        ("mixed_3_scripts", MIXED_SCRIPT),
        ("cyrillic_pure", CYRILLIC),
        ("cjk_pure", CJK),
    ] {
        group.throughput(text_throughput(input));
        group.bench_with_input(BenchmarkId::new("detect", name), input, |b, text| {
            b.iter(|| _detect_scripts(black_box(text)));
        });

        group.bench_with_input(BenchmarkId::new("is_mixed", name), input, |b, text| {
            b.iter(|| _is_mixed_script(black_box(text)));
        });
    }

    group.finish();
}

// ---------------------------------------------------------------------------
// Grapheme cluster benchmarks
// ---------------------------------------------------------------------------

fn bench_grapheme(c: &mut Criterion) {
    let mut group = c.benchmark_group("grapheme");

    group.throughput(text_throughput(ASCII_SHORT));
    group.bench_function("len_ascii", |b| {
        b.iter(|| _grapheme_len(black_box(ASCII_SHORT)));
    });

    group.throughput(text_throughput(EMOJI_TEXT));
    group.bench_function("len_emoji", |b| {
        b.iter(|| _grapheme_len(black_box(EMOJI_TEXT)));
    });

    group.throughput(text_throughput(ASCII_SHORT));
    group.bench_function("split_ascii", |b| {
        b.iter(|| _grapheme_split(black_box(ASCII_SHORT)));
    });

    group.throughput(text_throughput(EMOJI_TEXT));
    group.bench_function("split_emoji", |b| {
        b.iter(|| _grapheme_split(black_box(EMOJI_TEXT)));
    });

    group.finish();
}

// ---------------------------------------------------------------------------
// Confusable normalization benchmarks (#252 — previously no coverage)
// ---------------------------------------------------------------------------

fn bench_confusables(c: &mut Criterion) {
    let mut group = c.benchmark_group("confusables");

    // ASCII is the common case in the web/RAG/catalog profiles. NOTE: this is
    // NOT a no-op — translit's table maps a few ASCII sources (e.g. `|`→`l`), so
    // an "is_ascii fast path" would be incorrect (#252 O6.1, rejected).
    let ascii = "The quick brown fox jumps over the lazy dog. ".repeat(8);
    group.throughput(text_throughput(&ascii));
    group.bench_function("ascii_doc", |b| {
        b.iter(|| _normalize_confusables(black_box(&ascii), black_box("latin")).unwrap());
    });

    // Cyrillic/Greek homoglyphs — the fold actually fires here.
    let homoglyph = "Москва раураl Ελλάδα gооgle ".repeat(8);
    group.throughput(text_throughput(&homoglyph));
    group.bench_function("homoglyph_doc", |b| {
        b.iter(|| _normalize_confusables(black_box(&homoglyph), black_box("latin")).unwrap());
    });

    group.finish();
}

// ---------------------------------------------------------------------------
// Criterion groups
// ---------------------------------------------------------------------------

criterion_group!(
    benches,
    bench_transliterate,
    bench_table_lookup,
    bench_slugify,
    bench_fold_case,
    bench_whitespace,
    bench_scripts,
    bench_grapheme,
    bench_confusables,
);
criterion_main!(benches);
