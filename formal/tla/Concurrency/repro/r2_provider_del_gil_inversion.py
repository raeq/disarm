"""F2: two-thread lock-order inversion GLOBAL_PROVIDER.write <-> GIL.

No re-entrancy into disarm is needed: the old provider's __del__ only has to
give up the GIL once. Any blocking I/O does (time.sleep stands in for closing a
file / DB connection / socket that the provider owns), and so does plain Python
work that outlasts the 5 ms switch interval (`--busy`). (A provider that merely
owns an open file, with no __del__, did NOT hang in testing: the finaliser's
syscalls release the GIL too briefly for the reader to win it. Only a
finaliser that gives up the GIL for real is shown to trigger it.)

  T1  set_emoji_provider(None)      GIL held -> GLOBAL_PROVIDER.write() acquired
                                    (emoji.rs:29) -> `*guard = None` drops Old
                                    -> Old.__del__ -> time.sleep releases the GIL
  T2  demojize(...) in a loop       takes the GIL -> _demojize ->
                                    GLOBAL_PROVIDER.read() (emoji.rs:268) blocks
                                    *while holding the GIL*
  T1  sleep returns, needs the GIL to resume __del__ -> waits on T2
  => T1 waits GIL (held by T2), T2 waits RwLock (held by T1): deadlock.

TLA+ counterexample: EmojiProvider.tla, config EmojiProvider_gil.cfg.
Run: timeout 20 python3 r2_provider_del_gil_inversion.py  (exit 124 == hang)
"""

import sys
import threading
import time

import disarm

BUSY = "--busy" in sys.argv  # CPU-bound __del__ instead of a blocking one
stop = threading.Event()
calls = 0


class Old:
    def lookup(self, seq):
        return None

    def __del__(self):
        if BUSY:
            # Pure-Python work for longer than the 5 ms switch interval: the
            # eval loop hands the GIL to the waiting reader thread by itself.
            end = time.perf_counter() + 0.05
            while time.perf_counter() < end:
                pass
        else:
            # Stand-in for releasing a resource: any call that drops the GIL.
            time.sleep(0.05)


def reader():
    global calls
    while not stop.is_set():
        disarm.demojize("plain text, no emoji")  # never calls lookup: no clone in flight
        calls += 1


disarm.set_emoji_provider(Old())
t = threading.Thread(target=reader, daemon=True)
t.start()
time.sleep(0.1)
print(f"reader running ({calls} calls); resetting provider ...", flush=True)
disarm.set_emoji_provider(None)
stop.set()
t.join()
print(f"OK: no deadlock ({calls} demojize calls)", flush=True)
