#!/usr/bin/env bash
#
# perf_lint.sh — allocation & space-cost lint gate.
#
# Catches unnecessary / costly allocations and clones that the default
# `cargo clippy -D warnings` gate misses, because the strongest lints for this
# class (`redundant_clone` from the nursery group, `or_fun_call`, and the
# pedantic allocation/by-value lints) are OFF by default.
#
# This is deliberately NOT a bespoke analyzer: it is `cargo clippy` — the
# widely-used Rust static analyzer — run with a curated, allocation-focused lint
# set promoted to `deny`, isolated from clippy's broader style lints so the
# signal is purely "this allocates/copies when it need not".
#
# Coverage — the core AND every binding's Rust glue:
#   Most usage flows through the language bindings (Python/pyo3, Node/napi,
#   Ruby/magnus, and the upcoming Java binding). A binding can *degenerate* and
#   introduce an allocation regression that is NOT in the core — a defensive
#   `.clone()`, a redundant string re-encode across the FFI boundary, an
#   intermediate `Vec` — so the allocation lints run on the binding glue too, not
#   just the core. (The binding Rust glue was previously linted by NOTHING in CI.)
#
# Two lint tiers:
#   ALLOC — allocation/clone lints. Valid on ANY Rust layer; run on core + glue.
#   BYVAL — by-value / API-shape lints. Run on the CORE ONLY: FFI entry points
#           (`#[pyfunction]`, napi, magnus) idiomatically take owned values, so
#           `needless_pass_by_value` & friends are false positives on glue.
#
# Out of scope here (use the right tool on demand, not as a per-commit gate):
#   * Runtime heap profiling / peak-space (space complexity):
#       DHAT via the `dhat-rs` crate — cross-platform, no valgrind (valgrind's
#       DHAT is unusable on Apple Silicon). Per-call-site alloc counts + bytes +
#       peak heap. The repo also pins specific per-call allocation counts in
#       `tests/preset_alloc_count.rs` (a `stats_alloc` counting allocator).
#   * Algorithmic / time complexity (O(n) or worse):
#       No acclaimed *static* detector exists for Rust — measure it. Use the
#       existing iai-callgrind harness (`benchmarks/bench_iai.rs`, the CI
#       `iai estimated-cycles gate`) with input-size sweeps; super-linear
#       scaling shows up as a non-constant instruction-count ratio.
#
# Usage:
#   bash scripts/perf_lint.sh                 # main crate: pure core (ALLOC+BYVAL)
#                                             #             + pyo3 ext layer (ALLOC)
#   BINDING=bindings/node bash scripts/perf_lint.sh   # a binding crate's glue (ALLOC)
#   BINDING=bindings/ruby bash scripts/perf_lint.sh   # (caller must have applied the
#                                                     #  [patch.crates-io] redirect so
#                                                     #  the crate builds vs the in-repo
#                                                     #  core — the CI binding jobs do)
#
set -euo pipefail
cd "$(dirname "$0")/.."

# --- ALLOC: allocation / clone lints (core + every binding's glue) ------------
ALLOC_LINTS=(
  clippy::redundant_clone            # nursery: a clone whose result is only read/dropped
  clippy::unnecessary_to_owned       # to_owned()/to_vec()/to_string() where a borrow works
  clippy::inefficient_to_string      # &&str -> String via Display instead of (*s).to_string()
  clippy::implicit_clone             # .to_owned()/.to_vec() via the ToOwned blanket impl
  clippy::cloned_instead_of_copied   # .cloned() where .copied() (no alloc) suffices
  clippy::map_clone                  # .map(|x| x.clone()) -> .cloned()/.copied()
  clippy::iter_overeager_cloned      # .cloned() before a filter/take that discards items
  clippy::useless_vec                # vec![..] where a slice/array literal works (no heap)
  clippy::slow_vector_initialization # Vec::with_capacity + resize patterns
  clippy::or_fun_call                # eager alloc inside unwrap_or/or/get_or_insert/...
  clippy::format_collect             # .map(|..| format!(..)).collect::<String>() chains
  clippy::format_push_string         # write! into a String you then push — extra alloc
  clippy::large_enum_variant         # one fat variant inflates every value of the enum
  clippy::large_stack_arrays         # big arrays blown onto the stack
)

# --- BYVAL: by-value / API-shape lints (core ONLY — FFI glue trips these) ------
BYVAL_LINTS=(
  clippy::needless_pass_by_value     # owned param never consumed -> forces caller clones
  clippy::large_types_passed_by_value
  clippy::trivially_copy_pass_by_ref # &Copy passed by ref (or vice-versa) — cache/space
)

# Build a clippy arg list: start from `-A clippy::all` so ONLY the curated lints
# can fire (no style noise), then `-D` each so any hit fails the gate.
mk() { local a=( -A clippy::all ); local l; for l in "$@"; do a+=( -D "$l" ); done; echo "${a[@]}"; }

if [[ -n "${BINDING:-}" ]]; then
  # A binding crate's Rust glue. ALLOC only (see BYVAL note). The caller must have
  # applied the `[patch.crates-io]` redirect so the crate builds against the
  # in-repo core (the Node/Ruby CI jobs do). Add the Java binding here when it lands.
  read -r -a A <<<"$(mk "${ALLOC_LINTS[@]}")"
  echo "perf-lint: clippy (binding glue: $BINDING) — ${#ALLOC_LINTS[@]} allocation lints denied"
  ( cd "$BINDING" && cargo clippy --all-targets -- "${A[@]}" )
  echo "perf-lint: $BINDING clean ✓"
  exit 0
fi

# Main crate: pure core gets ALLOC+BYVAL; the pyo3 extension layer gets ALLOC only.
read -r -a CORE <<<"$(mk "${ALLOC_LINTS[@]}" "${BYVAL_LINTS[@]}")"
read -r -a EXT  <<<"$(mk "${ALLOC_LINTS[@]}")"

echo "perf-lint: clippy (pure core) — $(( ${#ALLOC_LINTS[@]} + ${#BYVAL_LINTS[@]} )) lints denied"
cargo clippy --all-targets --no-default-features -- "${CORE[@]}"

echo "perf-lint: clippy (pyo3 extension layer) — ${#ALLOC_LINTS[@]} allocation lints denied"
cargo clippy --all-targets --features extension-module -- "${EXT[@]}"

echo "perf-lint: clean ✓"
