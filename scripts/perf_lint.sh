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
# Scope of this gate (cheap, static, every-commit):
#   * unnecessary heap allocations and clones
#   * needless owned-by-value params (force caller clones) and large by-value moves
#
# Out of scope here (use the right tool on demand, not as a per-commit gate):
#   * Runtime heap profiling / peak-space (space complexity):
#       DHAT via the `dhat-rs` crate — cross-platform, no valgrind (valgrind's
#       DHAT is unusable on Apple Silicon). Per-call-site alloc counts + bytes +
#       peak heap. See docs; the repo also pins specific per-call allocation
#       counts in `tests/preset_alloc_count.rs` (a `stats_alloc` counting
#       allocator) as a committed regression guard.
#   * Algorithmic / time complexity (O(n) or worse):
#       No acclaimed *static* detector exists for Rust — measure it. Use the
#       existing iai-callgrind harness (`benchmarks/bench_iai.rs`, the CI
#       `iai estimated-cycles gate`) with input-size sweeps; super-linear
#       scaling shows up as a non-constant instruction-count ratio.
#
# Usage:  bash scripts/perf_lint.sh          # pure core (default, quick)
#         EXT=1 bash scripts/perf_lint.sh    # also lint the binding layer
#
set -euo pipefail
cd "$(dirname "$0")/.."

# Curated allocation / space-cost lints. Grouped by intent; all promoted to deny.
LINTS=(
  # --- unnecessary allocations / clones (primary target) ---
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
  # --- space / by-value move cost ---
  clippy::large_enum_variant         # one fat variant inflates every value of the enum
  clippy::large_stack_arrays         # big arrays blown onto the stack
  clippy::large_types_passed_by_value
  clippy::trivially_copy_pass_by_ref # &Copy passed by ref (or vice-versa) — cache/space
  clippy::needless_pass_by_value     # owned param never consumed -> forces caller clones
)

# Start from `-A clippy::all` so ONLY the curated lints can fire (no style noise),
# then `-D` each one so any hit fails the gate with a non-zero exit.
args=( -A clippy::all )
for l in "${LINTS[@]}"; do args+=( -D "$l" ); done

echo "perf-lint: clippy (pure core) — ${#LINTS[@]} allocation/space lints denied"
cargo clippy --all-targets --no-default-features -- "${args[@]}"

if [[ "${EXT:-0}" == "1" ]]; then
  echo "perf-lint: clippy (extension-module, check-only)"
  cargo clippy --all-targets --features extension-module -- "${args[@]}"
fi

echo "perf-lint: clean ✓"
