"""F3: the F1 pattern on TRANSLITERATE_FALLBACK (private API, low reach).

`_set_transliterate_fallback` (src/py/transliterate.rs:112-113) assigns into the
slot with the write guard held, dropping the previous callable under the lock.
If the previous callable's __del__ calls transliterate() on a shape that goes
to the fallback (a list, a str subclass, target=, context=True),
`_transliterate_entry` takes TRANSLITERATE_FALLBACK.read() (transliterate.rs:170)
on the thread that holds the write lock -> hang.

Only reachable through the private `disarm._core._set_transliterate_fallback`
(the package calls it once at import, and again on importlib.reload), so the
severity is low; the fix is the same as F1.

Run: timeout 20 python3 r3_fallback_del_reenter.py  (exit 124 == hang)
"""

import disarm
from disarm import _api
from disarm._core import _set_transliterate_fallback

orig = _api._transliterate_dispatch


class Wrapper:
    def __call__(self, *a, **kw):
        return orig(*a, **kw)

    def __del__(self):
        print("Wrapper.__del__: calling transliterate([...])", flush=True)
        print("nested ->", disarm.transliterate(["café"]), flush=True)


_set_transliterate_fallback(Wrapper())
print("list call via wrapper:", disarm.transliterate(["naïve"]), flush=True)
print("restoring original dispatcher ...", flush=True)
_set_transliterate_fallback(orig)  # drops Wrapper under the write guard
print("OK: no deadlock", flush=True)
