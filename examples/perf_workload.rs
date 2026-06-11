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

use _disarm::case_fold::_fold_case;
use _disarm::slugify::{slugify_impl, SlugConfig};
use _disarm::transliterate::{_strip_accents, find_untranslatable_impl, transliterate_impl};
use _disarm::ErrorMode;

#[path = "../benchmarks/persona_corpus.rs"]
mod persona_corpus;

fn usage() -> ! {
    eprintln!("usage: perf_workload <persona> <op> <iters>");
    eprintln!("       perf_workload --fingerprint");
    eprintln!("  see header comment for valid personas and ops");
    std::process::exit(2);
}

/// Emit the Rust half of the perf fingerprint (#234 gate V5) as one JSON line:
/// the runtime corpus digest (V6) plus the facts only the compiled binary knows
/// — the crate version and the build target it was compiled for. `scripts/
/// perf_fingerprint.py` merges this with the host/toolchain/comparator fields.
fn print_fingerprint() {
    let profile = if cfg!(debug_assertions) {
        "debug"
    } else {
        "release"
    };
    // All values are ASCII (hex digest, semver, arch/os consts) — no JSON
    // escaping needed.
    println!(
        "{{\"corpus_digest\":\"{}\",\"disarm_version\":\"{}\",\
         \"build_arch\":\"{}\",\"build_os\":\"{}\",\
         \"pointer_width_bits\":{},\"build_profile\":\"{}\"}}",
        persona_corpus::corpus_digest(),
        env!("CARGO_PKG_VERSION"),
        std::env::consts::ARCH,
        std::env::consts::OS,
        usize::BITS,
        profile,
    );
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() == 2 && args[1] == "--fingerprint" {
        print_fingerprint();
        return;
    }
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
