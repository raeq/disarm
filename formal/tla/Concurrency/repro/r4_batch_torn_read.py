"""F4: a batch transliterate call does not see one table version.

`_transliterate_batch` (src/py/transliterate.rs:419-460) runs each 64-item chunk
inside `py.detach` (GIL released). Inside the closure every item re-reads
HAS_REPLACEMENTS / GLOBAL_REPLACEMENTS_AC (tables/mod.rs:685-690), and the
per-character `lookup_registered` re-takes LANG_TABLES.read() for *every
character* (tables/mod.rs:419-428). A GIL-holding thread can call
register_replacements / register_lang meanwhile, so:

  (a) one batch result mixes items transliterated under different replacement
      tables (between items / between chunks);
  (b) one *single output string* mixes two language-table versions
      (between characters of the same item).

TLA+ counterexample: ReplacementTables.tla, invariant BatchSingleVersion
(config ReplacementTables.cfg) and LangTableTorn.
Run: timeout 20 python3 r4_batch_torn_read.py
"""

import sys
import threading
import time

import disarm

# ---- (a) replacements: mixed versions across items of one batch -------------
disarm.clear_replacements()
N = 20_000
batch = ["q"] * N
stop = threading.Event()


def flipper():
    i = 0
    while not stop.is_set():
        disarm.register_replacements({"q": "A" if i % 2 == 0 else "B"})
        i += 1
        time.sleep(0)  # yield the GIL


t = threading.Thread(target=flipper)
t.start()
mixed_a = 0
for _ in range(20):
    out = disarm.transliterate(batch)
    kinds = set(out)
    if len(kinds) > 1:
        mixed_a += 1
stop.set()
t.join()
disarm.clear_replacements()
print(f"(a) batches with >1 replacement version: {mixed_a}/20  e.g. {sorted(kinds)}")

# ---- (b) language table: torn inside ONE output string ----------------------
disarm.register_lang("zz", {"ж": "1"})
item = "ж" * 2_000_000  # one long string, one item
stop.clear()


def lang_flipper():
    i = 0
    while not stop.is_set():
        disarm.register_lang("zz", {"ж": "1" if i % 2 == 0 else "2"})
        i += 1
        time.sleep(0)


t = threading.Thread(target=lang_flipper)
t.start()
torn_b = 0
for _ in range(5):
    (s,) = disarm.transliterate([item], lang="zz")
    if "1" in s and "2" in s:
        torn_b += 1
stop.set()
t.join()
print(f"(b) single output strings containing both '1' and '2': {torn_b}/5")
sys.exit(0)
