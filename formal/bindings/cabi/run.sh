#!/usr/bin/env bash
# Exercise the real C ABI from C. Run `bash formal/bindings/build.sh cabi` first.
#
#   1. contract.c under AddressSanitizer + LeakSanitizer + UBSan: every function, both
#      halves of every DisarmResult, success and error paths, all freed. Must be clean.
#   2. the same with one free deliberately skipped (-DSELFTEST_LEAK): LSan must report it,
#      which is what shows the clean run above means something.
#   3. contract.c under valgrind memcheck. Must be clean.
#   4. repro.c: the C1-C3 reproductions (expected to crash, in forked children).
set -u
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../../.." && pwd)"
lib="${CARGO_TARGET_DIR:-$root/target/formal-bindings}/release"
out="${CARGO_TARGET_DIR:-$root/target/formal-bindings}/cabi"
mkdir -p "$out"
cc_args=(-g -Wall -Wextra -I"$root/bindings/cabi" -L"$lib" -Wl,-rpath,"$lib")

gcc -O1 -fsanitize=address,undefined -fno-omit-frame-pointer "${cc_args[@]}" \
    "$here/contract.c" -ldisarm_ffi -o "$out/contract_asan"
gcc -O1 -DSELFTEST_LEAK -fsanitize=address -fno-omit-frame-pointer "${cc_args[@]}" \
    "$here/contract.c" -ldisarm_ffi -o "$out/contract_leak"
gcc -O0 "${cc_args[@]}" "$here/contract.c" -ldisarm_ffi -o "$out/contract"
gcc -O1 "${cc_args[@]}" "$here/repro.c" -ldisarm_ffi -o "$out/repro"

status=0
echo "== 1. contract under ASan/LSan/UBSan =="
ASAN_OPTIONS=detect_leaks=1 "$out/contract_asan" || status=1
echo "== 2. LSan self-test (a leak must be reported) =="
if ASAN_OPTIONS=detect_leaks=1 "$out/contract_leak" 2>&1 | grep -q 'SUMMARY: AddressSanitizer: .* leaked'; then
    echo "leak reported, as it must be"
else
    echo "LSan did NOT report the planted leak"; status=1
fi
echo "== 3. contract under valgrind =="
if command -v valgrind >/dev/null; then
    valgrind -q --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=9 "$out/contract" || status=1
else
    echo "valgrind not installed; skipped"
fi
echo "== 4. reproductions (C1-C3; crashes expected) =="
"$out/repro" all 2>&1 | grep -v '^ *[0-9]*: \|^ *at \|^stack backtrace\|^note: '
exit "$status"
