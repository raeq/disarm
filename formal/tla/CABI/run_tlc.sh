#!/usr/bin/env bash
# Model-check every spec/config pair in this directory and print a summary line
# per run. Usage:
#   TLA2TOOLS=/path/to/tla2tools.jar bash run_tlc.sh [config-glob]
# Full TLC output for each run goes to $OUT (default: a temp dir).
#
# Every config's verdict is compared with expected.tsv, and the script exits non-zero
# if one differs or has no entry there: CI runs it as a gate (.github/workflows/formal.yml).
set -u
here="$(cd "$(dirname "$0")" && pwd)"
jar="${TLA2TOOLS:?set TLA2TOOLS to the tla2tools.jar path}"
out="${OUT:-$(mktemp -d)}"
mkdir -p "$out"
pattern="${1:-*.cfg}"

# TLC 1.8 writes a trace-exploration spec next to the model on every violation unless
# told not to; 1.7 (what CI pins) never does and rejects the flag.
te_flag=""
if java -cp "$jar" tlc2.TLC -help 2>&1 | grep -q -- -noGenerateSpecTE; then
    te_flag="-noGenerateSpecTE"
fi

cd "$here"
# An array under nullglob: a pattern that matches nothing is an error, not a run of
# TLC on the literal pattern.
shopt -s nullglob
# shellcheck disable=SC2206  # the pattern is meant to glob
cfgs=($pattern)
shopt -u nullglob
if [ "${#cfgs[@]}" -eq 0 ]; then
    echo "no configuration matches $pattern in $here" >&2
    exit 1
fi
for cfg in "${cfgs[@]}"; do
    name="${cfg%.cfg}"
    spec="${name%%_*}.tla"
    java -XX:+UseParallelGC -cp "$jar" tlc2.TLC -workers auto $te_flag \
        -metadir "$out/states-$name" -config "$cfg" "$spec" >"$out/$name.out" 2>&1
    verdict="$(grep -m1 -E 'No error has been found|Deadlock reached|is violated' "$out/$name.out" |
        sed 's/^Error: //')"
    states="$(grep -E '^[0-9,]+ states generated' "$out/$name.out" | tail -1)"
    case "$verdict" in
        "Model checking completed. No error has been found.") got=pass ;;
        "Deadlock reached.") got=deadlock ;;
        "Invariant "*" is violated.") got="${verdict#Invariant }"; got="${got% is violated.}" ;;
        *) got="?" ;;
    esac
    want="$(awk -F'\t' -v c="$cfg" '$1 == c { print $2 }' expected.tsv)"
    mark=ok
    if [ "$got" != "$want" ]; then
        mark="MISMATCH (expected ${want:-no entry in expected.tsv})"
        failed=1
    fi
    printf '%-36s %-50s %-8s %s\n' "$cfg" "${verdict:-?}" "$mark" "$states"
done
echo "full output: $out"
exit "${failed:-0}"
