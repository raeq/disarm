#!/usr/bin/env bash
# Run fuzz targets from the committed seeds for FUZZ_SECONDS each (default 60).
#
#   bash fuzz/run.sh                  # every target
#   bash fuzz/run.sh anomalies text   # just these
#   FUZZ_SECONDS=900 bash fuzz/run.sh presets
#
# Needs a nightly toolchain and cargo-fuzz (see docs/contributing/testing.md, "Fuzzing").
# New corpus entries are written to fuzz/corpus/<target>/ and failing inputs to
# fuzz/artifacts/<target>/, both gitignored; the seeds under fuzz/seeds/ are read and
# never written. The default build (no -O) keeps debug assertions and overflow checks on,
# which is the point: several of the library's invariants are debug_assert!s.
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

# One annotation per failed target, carrying what a reader needs to reproduce it: the
# kind of finding (the artifact's prefix: crash, timeout, oom, leak), what the target
# asserted, and the input itself in Base64. The job log runs to 50,000 lines and the
# uploaded artifact is behind a download, while an annotation is one API call away.
# `%`, CR and LF are escaped as workflow commands require.
report() {
    local t="$1" log="$2" artifact why input
    artifact="$(ls -t "fuzz/artifacts/$t"/* 2>/dev/null | head -n 1 || true)"
    why="$(grep -m 1 -A 4 -E "panicked at|ERROR: (libFuzzer|AddressSanitizer|LeakSanitizer)" "$log" \
        | cut -c 1-400 | tr '\n' ' ' || true)"
    input=""
    [ -n "$artifact" ] && input="$(base64 -w 0 "$artifact")"
    local msg="$t failed: ${why:-see the job log}; artifact ${artifact:-none}; input (base64) ${input:-none}"
    msg="${msg//%/%25}"
    msg="${msg//$'\r'/%0D}"
    msg="${msg//$'\n'/%0A}"
    echo "::error title=fuzz $t::$msg"
}

status=0
for t in "${targets[@]}"; do
    seeds=fuzz/seeds/unicode
    [ "$t" = decode_bytes ] && seeds=fuzz/seeds/bytes
    mkdir -p "fuzz/corpus/$t"
    group "$t (${secs}s)"
    # -timeout: an input that takes 30 s is a finding (a quadratic path), not noise.
    log="$(mktemp)"
    if ! cargo fuzz run "$t" "fuzz/corpus/$t" "$seeds" -- \
        -max_total_time="$secs" -timeout=30 -rss_limit_mb=4096 -print_final_stats=1 \
        2>&1 | tee "$log"; then
        report "$t" "$log"
        status=1
    fi
    rm -f "$log"
    endgroup
done
exit "$status"
