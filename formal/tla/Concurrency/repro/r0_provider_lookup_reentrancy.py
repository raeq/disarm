"""Negative control: re-entrancy from EmojiProvider.lookup is safe.

`_demojize` (src/py/emoji.rs:265-270) clones the provider handle under
GLOBAL_PROVIDER.read() and drops the guard at the end of the `else` block,
*before* demojize_impl calls `provider.lookup`. So a lookup that calls
set_emoji_provider (write) or demojize (read) never waits on a lock its own
thread holds. TLC agrees (EmojiProvider.tla, NoDeadlock + SnapshotSemantics).

Defined outcome of set_emoji_provider during demojize: the in-flight call keeps
the provider it snapshotted; the next call sees the new one.

Run: timeout 20 python3 r0_provider_lookup_reentrancy.py  (expect exit 0)
"""

import threading

import disarm

GRIN = "\U0001f600"


class Other:
    def lookup(self, seq):
        return "OTHER" if seq == [0x1F600] else None


class Reentrant:
    depth = 0

    def lookup(self, seq):
        if seq != [0x1F600]:
            return None
        if Reentrant.depth == 0:
            Reentrant.depth += 1
            inner = disarm.demojize(GRIN)  # nested read of GLOBAL_PROVIDER
            disarm.set_emoji_provider(Other())  # nested write of GLOBAL_PROVIDER
            Reentrant.depth -= 1
            return f"OUTER[{inner}]"
        return "INNER"


disarm.set_emoji_provider(Reentrant())
first = disarm.demojize(f"{GRIN} {GRIN}")
second = disarm.demojize(GRIN)
print("in-flight call :", first)  # both emoji resolved by the snapshotted provider
print("next call      :", second)  # sees the provider installed mid-call

# Two threads: one swaps providers in a loop, one demojizes in a loop.
stop = threading.Event()
seen = set()


def swapper():
    while not stop.is_set():
        disarm.set_emoji_provider(Other())
        disarm.set_emoji_provider(None)


t = threading.Thread(target=swapper)
t.start()
for _ in range(20000):
    seen.add(disarm.demojize(GRIN))
stop.set()
t.join()
disarm.set_emoji_provider(None)
print("outcomes under concurrent swaps:", sorted(seen))
print("OK: no deadlock")
