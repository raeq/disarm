"""E3: the one ResourceLimit error every binding can reach, and how each reports it.

U+FDFA expands to 18 characters under NFKC, so 600,000 of them (1.8 MB of input)
produce more than MAX_NORMALIZE_OUTPUT_BYTES (10 MiB) inside `canonicalize` (#768).

    DISARM_FFI=target/formal-bindings/release/libdisarm_ffi.so $DISARM_PYTHON resource_limit.py
"""

import ctypes as C
import os

import disarm

text = "\ufdfa" * 600_000

try:
    disarm.canonicalize(text)
except disarm.DisarmError as e:
    print("python canonicalize:", type(e).__name__, "|", str(e)[:70])
try:
    print("python is_canonical:", disarm.is_canonical(text))
except disarm.DisarmError as e:
    print("python is_canonical raised", type(e).__name__)

lib = C.CDLL(os.environ["DISARM_FFI"])


class R(C.Structure):
    _fields_ = [("value", C.c_void_p), ("error", C.c_void_p)]


lib.disarm_canonicalize.restype = R
lib.disarm_canonicalize.argtypes = [C.c_char_p]
lib.disarm_is_canonical.restype = C.c_int8
lib.disarm_is_canonical.argtypes = [C.c_char_p, C.c_char_p]
lib.disarm_string_free.argtypes = [C.c_void_p]
b = text.encode()
r = lib.disarm_canonicalize(b)
print(
    "C disarm_canonicalize: value",
    bool(r.value),
    "error",
    C.string_at(r.error).decode()[:70] if r.error else None,
)
lib.disarm_string_free(r.value)
lib.disarm_string_free(r.error)
print(
    'C disarm_is_canonical(text, "canonicalize") =',
    lib.disarm_is_canonical(b, b"canonicalize"),
    "(documented: -1 only when the preset name is unknown)",
)
