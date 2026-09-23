#!/usr/bin/env bash
# S1 and D1, the two differences the all-of-Unicode sweep found, in every binding.
#   DISARM_PYTHON=... bash formal/bindings/repro/sweep_findings.sh
set -u
root="$(cd "$(dirname "$0")/../../.." && pwd)"
lib="${CARGO_TARGET_DIR:-$root/target/formal-bindings}"
py="${DISARM_PYTHON:-python3}"

echo "S1 strip_accents(U+037E GREEK QUESTION MARK), D1 demojize(U+1F1E6 lone regional indicator)"
"$py" -c 'import disarm; print("python", ascii(disarm.strip_accents("\u037e")), ascii(disarm.demojize("\U0001f1e6")))'
node -e 'const d = require(process.argv[1]); console.log("node  ", JSON.stringify(d.stripAccents("\u037e")).replace(/[^\x20-\x7e]/g, c => "\\u" + c.charCodeAt(0).toString(16)), JSON.stringify(d.demojize("\u{1f1e6}")))' "$root/bindings/node/index.js"
ruby -I "$root/bindings/ruby/lib" -rdisarm -e 'puts "ruby   #{Disarm.strip_accents("\u037e").dump} #{Disarm.demojize("\u{1f1e6}").dump}"'
DISARM_FFI="$lib/release/libdisarm_ffi.so" "$py" -c '
import ctypes as C, os
l = C.CDLL(os.environ["DISARM_FFI"])
for f in (l.disarm_strip_accents, ):
    f.restype = C.c_void_p; f.argtypes = [C.c_char_p]
l.disarm_demojize.restype = C.c_void_p; l.disarm_demojize.argtypes = [C.c_char_p, C.c_bool]
a = C.string_at(l.disarm_strip_accents("\u037e".encode())).decode()
b = C.string_at(l.disarm_demojize("\U0001f1e6".encode(), False)).decode()
print("c     ", ascii(a), ascii(b))'
