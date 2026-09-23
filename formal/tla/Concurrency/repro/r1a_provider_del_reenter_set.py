"""F1a: single-thread self-deadlock in set_emoji_provider.

set_emoji_provider(new) runs `*guard = provider` (src/py/emoji.rs:29-30) with the
GLOBAL_PROVIDER *write* guard held. The assignment drops the old Py<PyAny>; the
thread is attached, so pyo3 (instance.rs `impl Drop for Py<T>`) Py_DECREFs
immediately and the old provider's __del__ runs *inside* the write-locked
region. If __del__ calls set_emoji_provider again, the same thread requests the
write lock it already holds. std's futex RwLock is not re-entrant: it blocks
forever, holding the GIL, so the whole interpreter freezes.

TLA+ counterexample: EmojiProvider.tla, config EmojiProvider_reentrant.cfg.
Run: timeout 20 python3 r1a_provider_del_reenter_set.py  (exit 124 == hang)
"""

import disarm


class Old:
    def lookup(self, seq):
        return None

    def __del__(self):
        print("Old.__del__: calling set_emoji_provider(None)", flush=True)
        disarm.set_emoji_provider(None)  # re-enters GLOBAL_PROVIDER.write()
        print("Old.__del__: nested set_emoji_provider returned", flush=True)


class New:
    def lookup(self, seq):
        return None


disarm.set_emoji_provider(Old())  # the only reference now lives in GLOBAL_PROVIDER
print("replacing provider ...", flush=True)
disarm.set_emoji_provider(New())  # drops Old under the write guard
print("OK: no deadlock", flush=True)
