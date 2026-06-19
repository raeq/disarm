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
//! allocations on every thread, not just the current one. To keep the count exact
//! and deterministic we measure both presets inside a single `#[test]` (the only
//! test in this binary), so there is no concurrent test thread to pollute the
//! global counters.
use std::alloc::System;

use stats_alloc::{Region, StatsAlloc, INSTRUMENTED_SYSTEM};

#[global_allocator]
static GLOBAL: &StatsAlloc<System> = &INSTRUMENTED_SYSTEM;

/// Count the number of heap allocations during one call of `f`, after a warm-up
/// call (so one-time statics / lazy tables are not charged to the measured call).
fn allocs_for(f: impl Fn()) -> usize {
    f(); // warm up lazy statics / tables
    let region = Region::new(GLOBAL);
    f();
    region.change().allocations
}

/// Both presets are measured in one test so the process-wide `stats_alloc`
/// counters are never read while another test thread is allocating.
#[test]
fn preset_per_call_allocations_are_bounded() {
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
    // step can change skips the whole pipeline. Only the final String return is
    // allocated — 1 alloc, not the 5–10 of the full run. (A `Cow` return would
    // make this zero; tracked as the follow-up in #458.)
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
        assert!(
            n <= 1,
            "{name} on benign ASCII allocated {n} times/call (fast path expected <=1)"
        );
    }
}
