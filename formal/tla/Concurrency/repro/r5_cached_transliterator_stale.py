"""F5: make_cached_transliterator can keep a pre-registration result forever.

python/disarm/_api.py:3693-3716. `cached()` checks the generation, clears if it
moved, then calls the lru-cached `_cached(text)`. Nothing ties the value that
`_cached` computes to the generation it was checked against:

  T1  cached(k): gen == seen          -> miss -> transliterate(k) with OLD table
      [GIL switch at the eval-breaker check after the CALL, before lru_cache
       stores the result]
  W   register_replacements(...)      -> table NEW, then generation bumped
  T2  cached(k'): gen != seen         -> cache_clear(); seen = gen
  T1  lru_cache stores OLD result for k   (after the clear)
  --  every later cached(k) sees gen == seen and returns the OLD value,
      contradicting the docstring ("never serves results that pre-date a table
      change") until the *next* registration.

Every reader call uses a fresh key (unbounded cache), so a computation is in
flight almost all the time and a stale entry is never overwritten; after the
round every key is re-checked. That only makes the window frequent and the
result observable -- repeated keys have the same window on any miss.

TLA+ counterexample: CachedTransliterator.tla, invariant NoStaleAfterQuiesce.
Run: timeout 120 python3 r5_cached_transliterator_stale.py
"""

import itertools
import sys
import threading
import time

import disarm

# Widen the interleaving space (semantics unchanged). Pass --default-switch to
# keep CPython's 5 ms switch interval.
if "--default-switch" not in sys.argv:
    sys.setswitchinterval(1e-6)


def reader(cached, counter, used, go, stop):
    go.wait()
    while not stop.is_set():
        k = f"q{next(counter)}"
        used.append(k)
        cached(k)


stale = 0
ROUNDS = 1000
example = None
for i in range(ROUNDS):
    disarm.clear_replacements()
    cached = disarm.make_cached_transliterator(maxsize=None)
    counter = itertools.count()
    used: list[str] = []
    go = threading.Event()
    stop = threading.Event()
    args = (cached, counter, used, go, stop)
    readers = [threading.Thread(target=reader, args=args) for _ in range(3)]
    for r in readers:
        r.start()
    go.set()
    while len(used) < 200:  # let the readers get going
        time.sleep(0)
    disarm.register_replacements({"q": f"v{i}-"})  # the table change
    mark = len(used)
    while len(used) < mark + 200:  # let the readers run past the change
        time.sleep(0)
    stop.set()
    for r in readers:
        r.join()
    # Quiescent: no thread is inside cached(); the registration has returned and
    # nothing registers again this round. Every cached value must now be fresh.
    bad = [k for k in used if cached(k) != disarm.transliterate(k)]
    if bad:
        stale += 1
        k = bad[0]
        example = example or (i, len(bad), k, cached(k), disarm.transliterate(k))

disarm.clear_replacements()
if example:
    i, n, k, got, want = example
    print(f"e.g. round {i}: {n} stale key(s); cached({k!r}) = {got!r}, transliterate = {want!r}")
print(f"rounds ending with a stale cached value: {stale}/{ROUNDS}")
