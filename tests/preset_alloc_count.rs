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
    // Post-refactor measured: 7 allocs/call (ping-pong runner; deterministic).
    // Bound = measured + 1. Pre-refactor the chained presets allocated one String
    // per stage (~7-10/call, review D-3); a regression to per-stage allocation
    // (re-introducing a fresh String per stage) would push this past the bound.
    assert!(
        canon <= 8,
        "canonicalize allocated {canon} times/call (expected <=8 after ping-pong)"
    );

    let key_input = "CAFÉ\u{200B} ИМЯ";
    let key = allocs_for(|| {
        let _ = disarm::api::search_key(key_input, None);
    });
    // Post-refactor measured: 3 allocs/call (deterministic). Bound = measured + 1.
    assert!(
        key <= 4,
        "search_key allocated {key} times/call (expected <=4 after ping-pong)"
    );
}
