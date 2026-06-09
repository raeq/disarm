//! Deterministic workload binary for hardware-counter measurement.
#![allow(missing_docs)]
//!
//! Criterion answers "how long"; this binary exists so `perf stat` (Linux) can
//! answer "why" — branch-miss rate, L1d/LLC miss rate, IPC — over exactly the
//! same persona corpus the criterion benches use.
//!
//! Usage:
//!   cargo run --release --no-default-features --example perf_workload -- <persona> <op> <iters>
//!
//! Personas: ascii_doc | mixed_web | latin_doc | cyrillic_doc | greek_doc |
//!           arabic_doc | devanagari_doc | cjk_doc | hangul_doc
//! Ops:      transliterate | lang | slugify | fold_case | strip_accents | strict_scan
//!           ("lang" maps cyrillic_doc→ru, arabic_doc→ar, else exits)
//!
//! Prints an accumulated checksum so the optimizer cannot elide the work.
//! Typically driven via scripts/perf_stat.sh rather than directly.

use std::hint::black_box;

use _translit::case_fold::_fold_case;
use _translit::slugify::{slugify_impl, SlugConfig};
use _translit::transliterate::{_strip_accents, find_untranslatable_impl, transliterate_impl};
use _translit::ErrorMode;

#[path = "../benchmarks/persona_corpus.rs"]
mod persona_corpus;

fn usage() -> ! {
    eprintln!("usage: perf_workload <persona> <op> <iters>");
    eprintln!("  see header comment for valid personas and ops");
    std::process::exit(2);
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 4 {
        usage();
    }
    let persona = args[1].as_str();
    let op = args[2].as_str();
    let iters: u64 = args[3].parse().unwrap_or_else(|_| usage());

    let Some(doc) = persona_corpus::doc(persona) else {
        eprintln!("unknown persona: {persona}");
        usage();
    };
    let lang: Option<&str> = match (op, persona) {
        ("lang", "cyrillic_doc") => Some("ru"),
        ("lang", "arabic_doc") => Some("ar"),
        ("lang", _) => {
            eprintln!("op 'lang' supports cyrillic_doc and arabic_doc only");
            usage();
        }
        _ => None,
    };
    let config = SlugConfig::default();

    let mut checksum: u64 = 0;
    for _ in 0..iters {
        let n = match op {
            "transliterate" | "lang" => transliterate_impl(
                black_box(&doc),
                lang,
                ErrorMode::Ignore,
                "",
                false,
                false,
                false,
            )
            .len(),
            "slugify" => slugify_impl(black_box(&doc), &config).len(),
            "fold_case" => match _fold_case(black_box(&doc)) {
                Ok(s) => s.len(),
                Err(_) => 0,
            },
            "strip_accents" => _strip_accents(black_box(&doc)).len(),
            "strict_scan" => {
                find_untranslatable_impl(black_box(&doc), None, false, false, false).len()
            }
            _ => usage(),
        };
        checksum = checksum.wrapping_add(n as u64);
    }

    // Defeat dead-code elimination and give the script a sanity value.
    println!(
        "persona={persona} op={op} iters={iters} bytes_in={} checksum={checksum}",
        doc.len()
    );
}
