//! The premises of `Text/CaseFold.lean` and `Text/Hom.lean`, checked on every Unicode
//! scalar against the library's own table and the `to_lowercase` compiled into the same
//! build (which is the one `is_case_fold_stable` compares against).
//!
//! Run from this directory:
//!     CARGO_TARGET_DIR=../../.lake/cargo cargo run --release
//!
//! Exit status 0 iff every premise holds; the last lines also test the theorem's
//! conclusion directly on random strings.

use disarm::api::{fold_case, is_case_fold_stable};

const SIGMA: char = '\u{03A3}';

fn scalars() -> impl Iterator<Item = char> {
    (0u32..=0x10FFFF).filter_map(char::from_u32)
}

fn main() {
    let mut fails = 0usize;
    let mut fail = |what: &str, c: char| {
        fails += 1;
        if fails <= 20 {
            eprintln!("FAIL {what}: U+{:04X}", c as u32);
        }
    };
    let mut n = 0usize;
    let mut differ = Vec::new();
    // Scalars the bundled table leaves alone and this toolchain's `to_lowercase` moves:
    // where `is_case_fold_stable` depends on the compiling toolchain (#718).
    let mut toolchain_only = Vec::new();
    for c in scalars() {
        n += 1;
        let s = c.to_string();
        let f = fold_case(&s).into_owned();
        let low: String = c.to_lowercase().collect();
        // Hom.lean, per-scalar image of fold_case
        if f.is_empty() {
            fail("fold is empty", c);
        }
        if fold_case(&f) != f {
            fail("fold not idempotent", c);
        }
        if f.chars().any(|x| x.is_ascii_uppercase()) {
            fail("fold leaves ASCII uppercase", c);
        }
        if c.is_ascii() && !f.is_ascii() {
            fail("ASCII folds to non-ASCII", c);
        }
        // CaseFold.lean `ctx`: only SIGMA lowercases differently in context
        if c != SIGMA {
            let alone = s.to_lowercase();
            let medial = format!("a{c}a").to_lowercase();
            let last = format!("a{c}").to_lowercase();
            let first = format!("{c}a").to_lowercase();
            let after_sigma = format!("{SIGMA}{c}").to_lowercase();
            if alone != low
                || medial != format!("a{low}a")
                || last != format!("a{low}")
                || first != format!("{low}a")
                || !after_sigma.ends_with(&low)
            {
                fail("context-sensitive lowercase", c);
            }
        }
        // `dom`: lowercase no longer than the fold
        if low.chars().count() > f.chars().count() {
            fail("lowercase longer than fold", c);
        }
        // `ascii`
        if c.is_ascii() && (f != low || c == SIGMA) {
            fail("ASCII fold != lowercase", c);
        }
        // the predicate on single scalars (the Rust tier-3 test, restated)
        if is_case_fold_stable(&s) != (f == s.to_lowercase()) {
            fail("predicate disagrees on a single scalar", c);
        }
        if f != low || f != s {
            differ.push(c);
        }
        if f == s && low != s {
            toolchain_only.push(format!("U+{:04X}", c as u32));
        }
    }
    // `sigma`: U+03A3 folds to what it lowercases to alone, and its lowercase in any
    // context is one scalar long.
    let fs = fold_case("\u{03A3}").into_owned();
    if fs != "\u{03C3}" || "\u{03A3}".to_lowercase() != "\u{03C3}" {
        fail("sigma premise", SIGMA);
    }
    for ctx in ["a\u{03A3}", "\u{03A3}a", "a\u{03A3}a", "a\u{03A3}\u{03A3}", "\u{03A3}\u{03A3}"] {
        if ctx.to_lowercase().chars().count() != ctx.chars().count() {
            fail("sigma chunk length", SIGMA);
        }
    }
    println!("scalars checked: {n}; scalars whose fold or lowercase moves: {}", differ.len());
    let (maj, min, pat) = char::UNICODE_VERSION;
    println!(
        "to_lowercase is Unicode {maj}.{min}.{pat}; scalars it moves and the fold table does not: {} {:?}",
        toolchain_only.len(),
        &toolchain_only[..toolchain_only.len().min(12)]
    );

    // The conclusion of `stable_correct`, directly, on random strings built from the
    // scalars that move plus sigma, ASCII and a few neutral letters.
    let mut pool = differ.clone();
    pool.extend(['a', 'A', 'z', ' ', SIGMA, '\u{03C3}', '\u{03C2}', '\u{00DF}', '\u{0130}']);
    let mut x: u64 = 0x9E37_79B9_7F4A_7C15;
    let mut next = || {
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        x
    };
    let trials = 2_000_000usize;
    let mut bad = 0usize;
    for _ in 0..trials {
        let len = (next() % 8) as usize;
        let s: String = (0..len)
            .map(|_| pool[(next() % pool.len() as u64) as usize])
            .collect();
        let want = fold_case(&s) == s.to_lowercase();
        if is_case_fold_stable(&s) != want {
            bad += 1;
            if bad <= 5 {
                eprintln!("FAIL random string: {s:?}");
            }
        }
        // Hom.lean: fold_case is per-scalar
        let per: String = s.chars().map(|c| fold_case(&c.to_string()).into_owned()).collect();
        if fold_case(&s) != per {
            bad += 1;
            if bad <= 5 {
                eprintln!("FAIL fold_case not per-scalar on {s:?}");
            }
        }
    }
    println!("random strings: {trials}, disagreements: {bad}");
    println!("premise failures: {fails}");
    if fails > 0 || bad > 0 {
        std::process::exit(1);
    }
}
