"""No Python code runs while a Rust lock is held (TLA+ model, formal/tla/Concurrency).

`set_emoji_provider` and `_set_transliterate_fallback` replaced the stored
callable with `*guard = new` under the write lock, and assigning drops the old
`Py<PyAny>` there and then: its `__del__` ran inside the lock. Two ways that
hangs the interpreter, both found by TLC and reproduced here:

* re-entrancy: the old object's `__del__` calls `set_emoji_provider` or
  `demojize`, which waits on the lock its own thread holds;
* lock/GIL inversion, no re-entrancy at all: the `__del__` gives up the GIL
  (closing a file or socket does), another thread's `demojize` takes the GIL and
  blocks on the read lock *holding it*, and the first thread cannot get the GIL
  back to finish.

Each case runs in a subprocess under a timeout, so a regression is a timeout
here rather than a hung test run.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

REENTER_SET = """
import disarm

class Old:
    def lookup(self, seq):
        return None
    def __del__(self):
        disarm.set_emoji_provider(None)

class New:
    def lookup(self, seq):
        return None

disarm.set_emoji_provider(Old())
disarm.set_emoji_provider(New())
"""

REENTER_DEMOJIZE = """
import disarm

class Old:
    def lookup(self, seq):
        return None
    def __del__(self):
        disarm.demojize("x \\U0001F600")

disarm.set_emoji_provider(Old())
disarm.set_emoji_provider(None)
"""

GIL_INVERSION = """
import threading, time
import disarm

stop = threading.Event()

class Old:
    def lookup(self, seq):
        return None
    def __del__(self):
        time.sleep(0.05)  # anything that gives up the GIL: closing a file, a socket

def reader():
    while not stop.is_set():
        disarm.demojize("plain text, no emoji")

disarm.set_emoji_provider(Old())
t = threading.Thread(target=reader, daemon=True)
t.start()
time.sleep(0.1)
disarm.set_emoji_provider(None)
stop.set()
t.join()
"""

FALLBACK_REENTER = """
import disarm
from disarm import _api
from disarm._core import _set_transliterate_fallback

orig = _api._transliterate_dispatch

class Wrapper:
    def __call__(self, *a, **kw):
        return orig(*a, **kw)
    def __del__(self):
        disarm.transliterate(["caf\\u00e9"])

_set_transliterate_fallback(Wrapper())
disarm.transliterate(["na\\u00efve"])
_set_transliterate_fallback(orig)
"""


@pytest.mark.parametrize(
    "script",
    [REENTER_SET, REENTER_DEMOJIZE, GIL_INVERSION, FALLBACK_REENTER],
    ids=["del-reenters-set", "del-reenters-demojize", "del-releases-gil", "fallback-del"],
)
def test_replacing_a_callable_never_hangs(script: str) -> None:
    try:
        run = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(script)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("deadlock: the old callable's __del__ ran under a Rust lock")
    assert run.returncode == 0, run.stderr
