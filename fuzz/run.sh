#!/usr/bin/env bash
# Run fuzz targets from the committed seeds for FUZZ_SECONDS each (default 60).
#
#   bash fuzz/run.sh                  # every target
#   bash fuzz/run.sh anomalies text   # just these
#   FUZZ_SECONDS=900 bash fuzz/run.sh presets
#
# Needs a nightly toolchain and cargo-fuzz (see CONTRIBUTING.md, "Fuzzing"). The corpus a
# run grows goes to fuzz/corpus/<target>/ and a failing input to fuzz/artifacts/<target>/,
# both gitignored; the seeds under fuzz/seeds/ are read and never written. The default
# build (no -O) keeps debug assertions and overflow checks on, which is the point: several
# of the library's invariants are debug_assert!s.
set -euo pipefail
cd "$(dirname "$0")/.."

secs="${FUZZ_SECONDS:-60}"
if [ "$#" -eq 0 ]; then
    mapfile -t targets < <(cargo fuzz list)
else
    targets=("$@")
fi

group() {
    if [ -n "${GITHUB_ACTIONS:-}" ]; then echo "::group::$1"; else echo "== $1"; fi
}
endgroup() {
    if [ -n "${GITHUB_ACTIONS:-}" ]; then echo "::endgroup::"; fi
}

status=0
for t in "${targets[@]}"; do
    seeds=fuzz/seeds/unicode
    [ "$t" = decode_bytes ] && seeds=fuzz/seeds/bytes
    mkdir -p "fuzz/corpus/$t"
    group "$t (${secs}s)"
    # -timeout: an input that takes 30 s is a finding (a quadratic path), not noise.
    if ! cargo fuzz run "$t" "fuzz/corpus/$t" "$seeds" -- \
        -max_total_time="$secs" -timeout=30 -rss_limit_mb=4096 -print_final_stats=1; then
        echo "::error title=fuzz $t::$t failed; the input is under fuzz/artifacts/$t/"
        status=1
    fi
    endgroup
done
exit "$status"
