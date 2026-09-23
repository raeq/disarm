"""F1b: single-thread self-deadlock, read requested under the thread's own write.

Same site as F1a (src/py/emoji.rs:29-30). The old provider's __del__ calls
demojize(); `_demojize` takes GLOBAL_PROVIDER.read() (emoji.rs:268) while this
very thread still holds GLOBAL_PROVIDER.write(), so it blocks forever.

TLA+ counterexample: EmojiProvider.tla, config EmojiProvider_reentrant.cfg.
Run: timeout 20 python3 r1b_provider_del_reenter_demojize.py  (exit 124 == hang)
"""

import disarm


class Old:
    def lookup(self, seq):
        return None

    def __del__(self):
        print("Old.__del__: calling demojize()", flush=True)
        print("nested demojize ->", disarm.demojize("hi \U0001f600"), flush=True)


disarm.set_emoji_provider(Old())
print("resetting provider ...", flush=True)
disarm.set_emoji_provider(None)
print("OK: no deadlock", flush=True)
