"""`make_cached_transliterator` never serves a result that predates a registration.

Its docstring promises that after `register_lang`, `register_replacements`,
`remove_replacement` or `clear_replacements` the cache "never serves results that
pre-date a table change". A TLA+ model of it (formal/tla/Concurrency) found the
interleaving that breaks that: a call reads the generation, computes with the old
table, another call sees the new generation and clears the cache, and the first
then stores its old result into the fresh cache — served from then on. Reproduced
in about half of all rounds.

Runs in a subprocess: it registers replacements, which are process-global.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
import textwrap

import disarm

SCRIPT = """
import itertools, sys, threading, time
import disarm

sys.setswitchinterval(1e-6)

def reader(cached, counter, used, go, stop):
    go.wait()
    while not stop.is_set():
        k = f"q{next(counter)}"
        used.append(k)
        cached(k)

stale = 0
for i in range(300):
    disarm.clear_replacements()
    cached = disarm.make_cached_transliterator(maxsize=None)
    counter, used = itertools.count(), []
    go, stop = threading.Event(), threading.Event()
    readers = [
        threading.Thread(target=reader, args=(cached, counter, used, go, stop))
        for _ in range(3)
    ]
    for r in readers:
        r.start()
    go.set()
    while len(used) < 200:
        time.sleep(0)
    disarm.register_replacements({"q": f"v{i}-"})
    mark = len(used)
    while len(used) < mark + 200:
        time.sleep(0)
    stop.set()
    for r in readers:
        r.join()
    if any(cached(k) != disarm.transliterate(k) for k in used):
        stale += 1
disarm.clear_replacements()
print(stale)
"""


def test_a_registration_is_never_undone_by_an_in_flight_call() -> None:
    run = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(SCRIPT)],
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    )
    assert run.stdout.strip() == "0", f"{run.stdout.strip()} of 300 rounds served a stale value"


def test_the_callable_takes_one_string() -> None:
    """The generation is private: introspection must not see it (Copilot review on #1012)."""
    cached = disarm.make_cached_transliterator()
    assert list(inspect.signature(cached).parameters) == ["text"]
