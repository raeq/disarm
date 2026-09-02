//! Regression guard for #453: the preset ping-pong runner must keep per-call heap
//! allocations low (the pre-refactor chained presets allocated one String per
//! stage — 7-10 per call, verified in docs/reviews/2026-06-18-hardening-pass-delta.md
//! finding D-3). This pins the post-refactor count so a future regression to
//! per-stage allocation fails CI.
//!
//! `unsafe_code = "forbid"` is in force package-wide (see Cargo.toml), so we
//! cannot hand-roll a `GlobalAlloc` here. We use `stats_alloc` (dev-only), which
//! keeps the `unsafe` `GlobalAlloc` impl inside that crate; this file declares a
//! `#[global_allocator]` static and reads counts via a `Region` — no unsafe in
//! our code.
//!
//! `stats_alloc` instruments the *process-wide* allocator, so a `Region` measures
//! allocations on every thread, not just the current one. Measuring every preset inside a
//! single `#[test]` (the only test in this binary) removes concurrent *test* threads —
//! but not the rest of the process, and that is not the same thing (#905).
//!
//! This gate failed a pull request that changed no Rust at all, reporting `search_key`
//! at 7 against a bound of 4, and passed on re-run of the same commit. The bound is
//! `measured + 1`, so one stray allocation anywhere in the process blocks a merge.
//!
//! The fix rests on the noise being **one-sided**. Another thread allocating inside the
//! measured window can only ADD to the count; nothing subtracts. So the minimum over
//! several runs is the tightest true observation, and a transient disturbance — which is
//! what CI hit — no longer decides the verdict.
//!
//! It does not make a process-wide counter safe against *sustained* interference, and
//! nothing can: measured with a thread allocating continuously, the minimum over nine
//! runs still read 39 against a true 3, because no window is quiet. That is why this
//! binary must keep exactly one `#[test]` — a second one runs concurrently by default and
//! reintroduces precisely that condition. `only_one_test_in_this_binary` below asserts
//! it, because the premise was previously a comment and a comment cannot fail.
use std::alloc::System;

use stats_alloc::{Region, StatsAlloc, INSTRUMENTED_SYSTEM};

#[global_allocator]
static GLOBAL: &StatsAlloc<System> = &INSTRUMENTED_SYSTEM;

/// How many times each measurement is repeated. Ambient noise is rare, so a handful of
/// runs is enough for at least one to land in a quiet window; the cost is microseconds.
const MEASUREMENT_RUNS: usize = 9;

/// The smallest number of heap allocations observed across [`MEASUREMENT_RUNS`] calls of
/// `f`, after a warm-up call (so one-time statics / lazy tables are not charged).
///
/// The minimum, not the mean or a single sample, because the counter is process-wide and
/// the noise only ever adds (#905). A mean would drift with load; one sample is what made
/// this gate unreliable.
fn allocs_for(f: impl Fn()) -> usize {
    f(); // warm up lazy statics / tables
    (0..MEASUREMENT_RUNS)
        .map(|_| {
            let region = Region::new(GLOBAL);
            f();
            region.change().allocations
        })
        .min()
        .expect("MEASUREMENT_RUNS is non-zero")
}

/// Both presets are measured in one test so the process-wide `stats_alloc`
/// counters are never read while another test thread is allocating.
#[test]
fn preset_per_call_allocations_are_bounded() {
    // The file's premise, asserted rather than assumed (#905). A second `#[test]` here
    // runs concurrently with this one and allocates while the counters are open, which
    // is the sustained-noise case the minimum cannot survive. Checked from the source so
    // adding one fails here rather than as an unexplained count.
    let source = include_str!("preset_alloc_count.rs");
    // Lines that ARE the attribute, not lines that mention it — this comment and the
    // message below both contain the string.
    let tests = source.lines().filter(|l| l.trim() == "#[test]").count();
    assert_eq!(
        tests, 1,
        "this binary must contain exactly one #[test]; found {tests}. `stats_alloc` counts \
         process-wide, so a concurrent test thread allocates into this measurement (#905)."
    );

    // Short, mixed-script input (homoglyphs + bidi override + zero-width).
    let canon_input = "Ηеllо\u{202E}\u{200B}Wоrld";
    let canon = allocs_for(|| {
        let _ = disarm::api::canonicalize(canon_input);
    });
    // Measured: 5 allocs/call. Bound = measured + 1. Pre-refactor the chained
    // presets allocated one String per stage (~10/call, review D-3); the ping-pong
    // runner plus the buffer-reusing confusables→NFC fixed-point loop (PR #454
    // review) brought this down. A regression to per-stage / per-iteration
    // allocation would push it past the bound.
    assert!(
        canon <= 6,
        "canonicalize allocated {canon} times/call (expected <=6 after ping-pong)"
    );

    // canonicalize_strict shares the buffer-reusing fixed-point loop.
    let strict = allocs_for(|| {
        let _ = disarm::api::canonicalize_strict(canon_input);
    });
    assert!(
        strict <= 6,
        "canonicalize_strict allocated {strict} times/call (expected <=6)"
    );

    let key_input = "CAFÉ\u{200B} ИМЯ";
    let key = allocs_for(|| {
        let _ = disarm::api::search_key(key_input, None);
    });
    // Measured: 3 allocs/call. Bound = measured + 1.
    assert!(
        key <= 4,
        "search_key allocated {key} times/call (expected <=4 after ping-pong)"
    );

    // sort_key: transliterate-preserving-latin now writes into the runner's scratch
    // (PR #454 review) instead of returning a fresh String.
    let sort_input = "Über ИМЯ Война";
    let sort = allocs_for(|| {
        let _ = disarm::api::sort_key(sort_input, None);
    });
    assert!(
        sort <= 6,
        "sort_key allocated {sort} times/call (expected <=6)"
    );

    // #458 fast path: benign / ASCII-dominated input (the deployment norm) that no
    // step can change skips the whole pipeline AND returns the input borrowed
    // (`Cow::Borrowed`), so it allocates **nothing** — down from the 5–10 of the
    // full run. The `disarm::api` presets return `Cow<str>`; only the bindings
    // clone at the FFI edge.
    let benign = "The quick brown fox jumps over the lazy dog. Hello world.";
    for (name, n) in [
        (
            "canonicalize",
            allocs_for(|| {
                let _ = disarm::api::canonicalize(benign);
            }),
        ),
        (
            "strip_obfuscation",
            allocs_for(|| {
                let _ = disarm::api::strip_obfuscation(benign);
            }),
        ),
        // lowercase so FoldCase has nothing to do either
        (
            "search_key",
            allocs_for(|| {
                let _ = disarm::api::search_key("the quick brown fox jumps over", None);
            }),
        ),
    ] {
        assert_eq!(
            n, 0,
            "{name} on benign ASCII allocated {n} times/call (Cow fast path expected 0)"
        );
    }

    // #458 Option D: benign *non-ASCII* that no step changes (pure Han + Hangul +
    // inert accented Latin — no combining marks, NFKC-stable, not confusable) also
    // skips, for the non-transliterating presets that do not strip accents. 0 allocs.
    // (A preset that transliterates, or strips accents off dakuten kana / precomposed
    // accents, correctly does NOT skip these — that path is covered elsewhere.)
    let benign_nonascii = "日本語漢字 한국어 café";
    let n = allocs_for(|| {
        let _ = disarm::api::canonicalize(benign_nonascii);
    });
    assert_eq!(
        n, 0,
        "canonicalize on benign non-ASCII allocated {n} times/call (Option D expected 0)"
    );

    // #464 WhitespaceOnly fast path: benign ASCII that is clean except for
    // whitespace (here a trailing space + a doubled interior space) reduces to a
    // single `collapse_whitespace` pass — one allocation for the owned output,
    // versus the 5–10 of the full pipeline. It cannot be zero (the result differs
    // from the borrowed input), but it must stay at the single collapse-output alloc.
    let ws_dirty = "the quick brown fox  jumps over the lazy dog. hello world. ";
    for (name, n) in [
        (
            "canonicalize",
            allocs_for(|| {
                let _ = disarm::api::canonicalize(ws_dirty);
            }),
        ),
        (
            "strip_obfuscation",
            allocs_for(|| {
                let _ = disarm::api::strip_obfuscation(ws_dirty);
            }),
        ),
    ] {
        assert!(
            n <= 1,
            "{name} on whitespace-only-dirty ASCII allocated {n} times/call (#464 expected <=1)"
        );
    }
}
