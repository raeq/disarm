#!/usr/bin/env bash
# Hardware-counter sweep over the persona corpus (Linux perf required).
#
# Runs examples/perf_workload.rs under `perf stat` for each persona x op and
# writes per-run CSV counter files plus a human-readable summary to
# target/perf-stat/. Use alongside the criterion benches: criterion tells you
# *how long*, this tells you *why* (IPC, branch-miss %, L1d/LLC miss %).
#
# Usage:
#   scripts/perf_stat.sh [iters]      # default 2000 (~32 MB processed per run)
#
# macOS note: `perf` is Linux-only. On a Mac, run this inside a Linux
# container/VM, or use `xctrace`/Instruments manually. The criterion benches
# work everywhere.
set -euo pipefail

ITERS="${1:-2000}"
EVENTS="task-clock,cycles,instructions,branches,branch-misses,L1-dcache-loads,L1-dcache-load-misses,LLC-loads,LLC-load-misses"
OUT_DIR="target/perf-stat"

if ! command -v perf >/dev/null 2>&1; then
    echo "error: 'perf' not found. This script requires Linux perf." >&2
    echo "On macOS, run inside a Linux container, or rely on criterion only." >&2
    exit 1
fi
if ! command -v cargo >/dev/null 2>&1; then
    echo "error: 'cargo' not found." >&2
    exit 1
fi

echo "Building workload binary (release, --no-default-features)..."
cargo build --release --no-default-features --example perf_workload

BIN="target/release/examples/perf_workload"
mkdir -p "$OUT_DIR"
SUMMARY="$OUT_DIR/summary.txt"
: > "$SUMMARY"

# persona:op pairs — every persona for the core engine, plus the
# finding-targeted ops on the personas where they are meaningful.
RUNS=(
    "ascii_doc:transliterate"
    "mixed_web:transliterate"
    "latin_doc:transliterate"
    "cyrillic_doc:transliterate"
    "greek_doc:transliterate"
    "arabic_doc:transliterate"
    "devanagari_doc:transliterate"
    "cjk_doc:transliterate"
    "hangul_doc:transliterate"
    "cyrillic_doc:lang"
    "arabic_doc:lang"
    "ascii_doc:slugify"
    "mixed_web:slugify"
    "ascii_doc:strip_accents"
    "latin_doc:strip_accents"
    "ascii_doc:fold_case"
    "greek_doc:fold_case"
    "mixed_web:strict_scan"
)

for run in "${RUNS[@]}"; do
    persona="${run%%:*}"
    op="${run##*:}"
    name="${persona}__${op}"
    csv="$OUT_DIR/${name}.csv"
    echo "== $name (iters=$ITERS)" | tee -a "$SUMMARY"
    # -x, gives machine-readable CSV; stderr carries the counters.
    perf stat -x, -e "$EVENTS" -o "$csv" -- \
        "$BIN" "$persona" "$op" "$ITERS" | tee -a "$SUMMARY"
    # Derive the two headline ratios into the summary.
    awk -F, '
        $3 == "instructions"           { inst = $1 }
        $3 == "cycles"                 { cyc = $1 }
        $3 == "branches"               { br = $1 }
        $3 == "branch-misses"          { brm = $1 }
        $3 == "L1-dcache-loads"        { l1 = $1 }
        $3 == "L1-dcache-load-misses"  { l1m = $1 }
        END {
            if (cyc > 0) printf "   IPC: %.2f\n", inst / cyc
            if (br  > 0) printf "   branch-miss: %.3f%%\n", 100 * brm / br
            if (l1  > 0) printf "   L1d-miss: %.3f%%\n", 100 * l1m / l1
        }' "$csv" | tee -a "$SUMMARY"
done

echo
echo "Per-run CSVs and summary written to $OUT_DIR/"
