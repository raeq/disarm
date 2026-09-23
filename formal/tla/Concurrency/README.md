# Concurrency model of the Python binding (TLA+/TLC)

This directory covers every piece of shared mutable state that the Python binding can
reach, and every place where the binding releases the GIL. It holds TLA+ (PlusCal)
models of those threads, locks and the GIL, TLC results for each model, and one real
Python reproduction for each counterexample TLC found.

> **Status.** F1-F3 are fixed in #1009, F5 in #1012, and F6 and F8 in #1014, which also
> documents F4 as outside the startup-only contract. F7 is latent and open.
> `Registration_fixed.cfg` models #1014's registration gate and passes.
> `run_tlc.sh` checks every verdict against `expected.tsv`.

Baseline: `main` at `bec93cf`, a release build of the extension, CPython 3.12.3 with
the GIL (not free-threaded), pyo3 0.29.2, and TLC2 2026.09.22.

## Findings at a glance

| # | What | Kind | Reproduced | Severity |
|---|------|------|------------|----------|
| F1 | `set_emoji_provider` runs the old provider's `__del__` while holding the `GLOBAL_PROVIDER` write guard. If that `__del__` calls `set_emoji_provider` or `demojize`, the thread deadlocks on itself | self-deadlock (whole process hangs with the GIL held) | yes, `r1a` and `r1b` hang 3/3 | medium |
| F2 | The same site with two threads and no re-entrancy: the `__del__` gives up the GIL, and another thread's `demojize` blocks on the read lock *while holding the GIL* | GIL / RwLock lock-order inversion | yes, `r2` hangs 3/3, and also with `--busy` | medium–high |
| F3 | The F1 pattern on `TRANSLITERATE_FALLBACK` (`_set_transliterate_fallback`) | self-deadlock | yes, `r3` hangs | low (private API) |
| F4 | One `transliterate(list)` call does not see one table version. Items differ, and one output **string** can mix two `register_lang` versions | atomicity | yes, `r4`: 20/20 and 5/5 | low (documented as startup-only config) |
| F5 | `make_cached_transliterator` can keep serving a pre-registration result after `register_*` returns, which contradicts its docstring | atomicity (Python layer) | yes, `r5`: 466/1000 rounds | medium |
| F6 | `UniqueSlugifier` holds a PyO3 `&mut` borrow across the `check` callback | defined error (`RuntimeError: Already borrowed`), not a deadlock | yes, `r6` | low |
| F7 | `recover_lock` attaches to the GIL and calls `warnings.warn` while holding the recovered guard. Inside `py.detach` that is lock-then-GIL, which deadlocks against a GIL-holding writer | latent deadlock | no: no reachable panic poisons these locks today | latent |
| F8 | `register_lang` checks the cap and the seal, then inserts, using three separate lock acquisitions | TOCTOU | not reachable from Python (the GIL makes it atomic). Model only for the public Rust API | low (Rust API) |

Verified safe: re-entrancy from `EmojiProvider.lookup` into `demojize` or
`set_emoji_provider`, both concurrently and on one thread. The `GLOBAL_REPLACEMENTS` /
`GLOBAL_REPLACEMENTS_AC` / `HAS_REPLACEMENTS` triple always stays mutually consistent,
and every item is linearizable. `TRANSLITERATE_FALLBACK` on the read path is also safe.
See "Checked and clean" below.

## Semantics that were modelled

* **GIL.** Modelled as a mutex. A `#[pyfunction]` body runs attached and holds the GIL.
  The GIL changes hands only (a) inside `py.detach(...)`, (b) while Python code runs
  (a callback, or an object's `__del__`), where the eval loop may switch threads, and
  (c) between bytecodes of pure-Python code. **Blocking on a `std::sync::RwLock` does
  not release the GIL.** Every deadlock found here comes from that fact.
* **`std::sync::RwLock` on Linux** is the futex implementation. It is not re-entrant: a
  write or read requested by a thread that already holds the write lock blocks forever
  (observed; no panic). It is writer-preferring: a new reader waits while a writer is
  waiting. `WriterPref = FALSE` models a reader-preferring lock. The two GIL deadlocks
  do not depend on the policy (`EmojiProvider_gil_readerpref.cfg`).
* **`Py<T>` drop.** pyo3 0.29.2 `impl Drop for Py<T>` (`instance.rs:2282`) runs
  `Py_DECREF` immediately when the thread is attached. So `*guard = new_value` on an
  `RwLock<Option<Py<PyAny>>>` runs the old object's finaliser **inside** the guarded
  region.
* **Poisoning.** Only a panic while a *write* guard is live poisons a std `RwLock`.

## Correspondence to the code

| State / call site | File:line | Where it is modelled |
|---|---|---|
| `GLOBAL_PROVIDER: RwLock<Option<Py<PyAny>>>` | `src/py/emoji.rs:25` | `EmojiProvider.tla` `slot`, `writer`, `readers`, `wwait` |
| `set_provider`: `write()`, `*guard = provider` (drops the old `Py` under the guard) | `src/py/emoji.rs:28-31` | `SetProvider` (`sp_lock` … `sp_unlock`) |
| `_demojize`: `read()`, `clone_ref`, guard dropped at the end of the `else` block | `src/py/emoji.rs:265-270` | `Demojize` (`dj_read`, `dj_clone`) |
| `provider.call_method1("lookup")`, with no guard held | `src/py/emoji.rs:60` | `Lookup` (a GIL switch point; may re-enter) |
| `TRANSLITERATE_FALLBACK` write (drops the old callable under the guard) | `src/py/transliterate.rs:100-101, 112-113` | same shape as `SetProvider` (F3) |
| `TRANSLITERATE_FALLBACK` read: `clone_ref`, guard dropped, then call | `src/py/transliterate.rs:169-172, 188` | same shape as `Demojize` (safe) |
| `GLOBAL_REPLACEMENTS`, `GLOBAL_REPLACEMENTS_AC`, `HAS_REPLACEMENTS` | `src/tables/mod.rs:88, 105, 138` | `ReplacementTables.tla` `table`, `ac`, `has`, `tblLock`, `acWriter`, `acReaders` |
| mutators: table write, then AC write, then `HAS` store | `src/tables/mod.rs:602-631, 644-650, 661-666` (AC swap at `128-132`) | `wr` process (`w_tbl` … `w_done`) |
| `apply_replacements`: `HAS` load, then AC `read()` for the item | `src/tables/mod.rs:682-695` | `rd` process (`r_start` … `r_val`) |
| `_transliterate_batch`: chunked `py.detach` | `src/py/transliterate.rs:419-460` (detach at `427`) | `r_detach` / `r_items` / `r_attach` |
| `LANG_TABLES` read per **character** in the same detach | `src/tables/mod.rs:419-428` | the same reader, with "item" read as "character" (F4b) |
| `register_lang`: seal check, count, cap, insert | `src/transliterate.rs:1654-1678`, `src/tables/mod.rs:561-565` | `Registration.tla` |
| `seal_registrations` | `src/tables/mod.rs:167-170` | `Registration.tla` `s` process |
| `crate::recover_lock`: on poison, `Python::attach` then `warnings.warn` with the guard held | `src/lib.rs:402-441` | `ReplacementTables.tla` `Poisoned` (`r_poison`) |
| `make_cached_transliterator` and `_registration_generation` | `python/disarm/_api.py:3432-3438, 3693-3716`; bumps at `3475, 3507, 3528, 3540` | `CachedTransliterator.tla` |
| `_UniqueSlugifier::slugify(&mut self)` calls `check` | `src/py/slugify.rs:397, 464` | not model-checked (PyO3 borrow flag, not a lock); reproduced directly |

## Specs, invariants and TLC results

Run everything with `TLA2TOOLS=/path/to/tla2tools.jar bash run_tlc.sh` (or pass a config
glob). The `.tla` files contain the PlusCal source plus its translation. To regenerate
the translation, run `java -cp tla2tools.jar pcal.trans -nocfg <Spec>.tla`.

Each spec checks TLC's deadlock detection (`CHECK_DEADLOCK TRUE`; a PlusCal process
that has finished is not counted as a deadlock) together with these invariants:

* `EmojiProvider.tla`:
  * `NoGuardAcrossPython`: Python code (a callback or `__del__`) never starts while the
    same thread holds a Rust lock guard. This is the root-cause property.
  * `NoSelfWait`: no thread waits on a lock that it holds.
* `ReplacementTables.tla`:
  * `ACInSync`: when no mutation is in progress, the automaton equals the table and
    `HAS` equals "table non-empty". This is the pair invariant.
  * `ItemLinearizable`: each item's result is the content of a table version that was
    current during that item.
  * `BatchLinearizable`: the same, over the whole batch.
  * `BatchSingleVersion`: every item of one batch saw the same version.
* `CachedTransliterator.tla`:
  * `NoStaleAfterRegistration`: a call that starts after the registration has returned
    never returns a pre-registration value.
  * `NoStaleAfterQuiesce`: once every thread has finished, no live cache entry is stale.
* `Registration.tla`:
  * `CapRespected`: the number of registered languages is at most the maximum.
  * `NoMutationAfterSeal`: nothing is inserted after `seal_registrations` has returned.

| Config | Models | Result | States generated / distinct |
|---|---|---|---|
| `EmojiProvider_lookup.cfg` | real code, 2 threads, re-entrant `lookup` (nested `demojize` and `set_emoji_provider`), a concurrent setter | **pass** | 787 / 520 (depth 50) |
| `EmojiProvider_reentrant.cfg` | real code, 1 thread, the old provider's `__del__` re-enters | **deadlock** (F1) | 12 / 12 |
| `EmojiProvider_gil.cfg` | real code, 2 threads, the old provider's `__del__` releases the GIL | **deadlock** (F2) | 242 / 167 at the counterexample |
| `EmojiProvider_gil_readerpref.cfg` | the same, with a reader-preferring lock | **deadlock** (F2) | 231 / 155 at the counterexample |
| `EmojiProvider_fixed.cfg` | the fix, 3 threads, all four `__del__` behaviours, re-entrant `lookup` | **pass** | 49,185 / 25,432 (depth 82) |
| `ReplacementTables.cfg` | real code, 2 writers × 2 ops, 1 batch of 3 items in chunks of 2 | **pass** (`ACInSync`, `ItemLinearizable`, `BatchLinearizable`, no deadlock) | 1,336,827 / 606,436 |
| `ReplacementTables_batch.cfg` | real code | **`BatchSingleVersion` violated** (F4) | 492 / 309 at the counterexample |
| `ReplacementTables_poison.cfg` | real code with the AC lock poisoned | **deadlock** (F7, latent) | 661 / 439 at the counterexample |
| `ReplacementTables_fixed.cfg` | the fix (one `Arc` snapshot taken attached), also poisoned | **pass** | 440,645 / 196,568 |
| `CachedTransliterator.cfg` | real code, 2 readers × 2 calls, 1 registration | **`NoStaleAfterRegistration` violated** (F5) | 2,625 / 1,306 at the counterexample |
| `CachedTransliterator_fixed.cfg` | the fix (the generation is part of the lru key), 2 × 3 calls | **pass** | 14,404 / 6,483 |
| `Registration_python.cfg` | the GIL-held PyO3 shim | **pass** | 56 / 50 |
| `Registration_rust.cfg` | the public Rust API, with no GIL | **`CapRespected` violated** (F8) | 432 / 226 at the counterexample |
| `Registration_rust_seal.cfg` | the public Rust API, with no GIL | **`NoMutationAfterSeal` violated** (F8) | 221 / 118 at the counterexample |
| `Registration_fixed.cfg` | the fix (#1014): one gate held by the sealer and by every mutator from check to write, 3 registrants for 1 slot | **pass** (`CapRespected`, `NoMutationAfterSeal`) | 208 / 184 |

TLC runs with multiple workers, so the state counts it prints at a counterexample vary
a little from run to run. The counts for passing runs are exact.

## Findings in detail

Each script in `repro/` must be run under a timeout so that a deadlock shows up as exit
status 124 instead of hanging the session:
`timeout 20 python3 repro/<script>.py`.

### F1: `set_emoji_provider` self-deadlocks when it replaces a provider whose `__del__` re-enters

*TLC trace* (`EmojiProvider_reentrant.cfg`, 9 steps):
1. `t_acq`: attach to the GIL.
2. `sp_lock`: `writer = 1`, `slot := None`.
3. `sp_drop`: the refcount of P0 reaches 0.
4. `del_py` → `del_act`: `__del__` calls `demojize`.
5. `dj_read` waits for `writer = 0`, but it is the waiting thread itself that holds the
   writer. No step is enabled.

The other branch is the same with `sp_lock` in place of `dj_read`.

*Reproduction:*

* `r1a_provider_del_reenter_set.py`: `__del__` calls `set_emoji_provider(None)`.
* `r1b_provider_del_reenter_demojize.py`: `__del__` calls `demojize()`.

*Observed:* both print `Old.__del__: calling …` and then hang until `timeout` kills them
(exit 124). The hang holds the GIL, so the whole interpreter freezes.

*Fix:* take the old value out, release the guard, then drop the old value:

```rust
pub fn set_provider(provider: Option<Py<PyAny>>) {
    let old = {
        let mut guard = crate::recover_lock(GLOBAL_PROVIDER.write(), "GLOBAL_PROVIDER");
        std::mem::replace(&mut *guard, provider)
    }; // guard released here
    drop(old); // __del__ (if any) runs with no lock held
}
```

`EmojiProvider_fixed.cfg` passes with this change.

### F2: GIL ↔ `GLOBAL_PROVIDER` deadlock between two threads, with no re-entrancy

*TLC trace* (`EmojiProvider_gil.cfg`):
1. T1: `set_emoji_provider(None)` takes the write lock.
2. T1: the old provider's `__del__` gives up the GIL.
3. T2: `t_acq` takes the GIL. `_demojize` then waits on `GLOBAL_PROVIDER.read()` while
   holding the GIL.
4. T1 waits for the GIL; T2 waits for the lock.

The same happens with a reader-preferring lock.

*Reproduction:* `r2_provider_del_gil_inversion.py`. One thread calls `demojize` on plain
text in a loop. The main thread calls `set_emoji_provider(None)`. The old provider's
`__del__` either calls `time.sleep(0.05)` or, with `--busy`, spins in pure Python for
50 ms.

*Observed:* it prints `reader running (≈100k calls); resetting provider ...` and then
hangs: exit 124 in 3 of 3 runs, and again in `--busy` mode. The reader is required to
demojize *plain* text. When the reader looks up an emoji, its in-flight
`effective_provider` clone keeps the old provider alive, so the last reference is
dropped later, outside the lock, and nothing hangs. That matches the model: `refs > 0`
at `sp_drop`.

*Reach:* the only requirement is a finaliser that gives up the GIL, whether through
blocking I/O, `time.sleep`, a lock wait, or more than 5 ms of Python work. The finaliser
can belong to the provider or to anything whose last reference the provider holds. In
testing, a provider that merely owned an open file did **not** trigger it, because the
finaliser's syscalls release the GIL too briefly.

*Fix:* the same as F1.

### F3: the same pattern on `TRANSLITERATE_FALLBACK`

`_set_transliterate_fallback` (`src/py/transliterate.rs:112-113`) drops the previous
callable under the write guard.

*Reproduction:* `r3_fallback_del_reenter.py`. It installs a wrapper whose `__del__`
calls `transliterate([...])`, then restores the original dispatcher.

*Observed:* hangs (exit 124).

*Reach:* only through the private `disarm._core._set_transliterate_fallback`, which the
package calls once at import and again on `importlib.reload(disarm)`. The functions it
installs have no finaliser, so the risk is low.

*Fix:* the same `mem::replace` → drop the guard → drop the old value. The read path
(`transliterate.rs:169-172`) is already correct.

### F4: a batch does not see one table version

*TLC trace* (`ReplacementTables_batch.cfg`, 22 steps):
1. The reader attaches and then detaches.
2. Item 1 reads `HAS = FALSE` and produces 0.
3. The writer, holding the GIL, runs register: table, AC, then `HAS = TRUE`.
4. Item 2 reads `HAS = TRUE` and gets AC content 1.

`results = <<0, 1>>` inside a single chunk, so within one `py.detach`.

*Reproduction:* `r4_batch_torn_read.py`.

*Observed:*

* (a) `register_replacements` flipping `q → A/B`: 20 of 20 batches of 20,000 items
  contained both `A` and `B`.
* (b) `register_lang("zz", …)` flipping `ж → 1/2`: 5 of 5 **single output strings**
  (one item of 2,000,000 characters) contained both `1` and `2`. `lookup_registered`
  re-takes `LANG_TABLES.read()` for every character.

*Classification:* a real atomicity violation, but outside the documented contract.
`register_lang` is documented as "startup-only / single-writer". The scalar
`transliterate(str)` path is atomic because it never releases the GIL. Every result
still passes `ItemLinearizable` and `BatchLinearizable`, so no reader ever sees a torn
table or automaton, and `ACInSync` holds for the pair.

*Fix, if batch atomicity is wanted:*

* Replacements: store the automaton as `RwLock<Option<Arc<ReplacementAutomaton>>>`.
  Clone the `Arc` once, attached, before the chunk loop, and use it for every item.
  `ReplacementTables_fixed.cfg` passes this.
* Language tables: resolve `LANG_TABLES.get(lang)` once into an `Arc<HashMap<char, String>>`
  before detaching (store the values as `Arc`). That also removes a lock round-trip per
  character.

### F5: `make_cached_transliterator` serves stale results

*TLC trace* (`CachedTransliterator.cfg`, 15 steps):
1. R1 `c_check`: gen 0 = seen 0.
2. R1 `c_lookup`: miss.
3. R1 `c_compute`: result from the OLD table.
4. W `w_reg`: table updated.
5. W `w_bump`: gen = 1.
6. R2 `c_check`: gen ≠ seen, so `c_clear`.
7. **R1 `c_store`**: the OLD value is stored after the clear.
8. R2 `c_seen`: seen = 1.
9. R2 `c_lookup`: hit, and it returns the OLD value. R2's call began after the
   registration returned.

From then on `gen == seen`, and the stale entry is served until the next registration.

*Reproduction:* `r5_cached_transliterator_stale.py`. Three threads share one cached
transliterator and use fresh keys. The main thread calls `register_replacements` once
per round. After all threads have stopped, it re-checks every key against
`transliterate`.

*Observed:*

* 466 of 1000 rounds end with a stale entry, for example
  `cached('q220') = 'q220', transliterate = 'v0-220'`.
* With the default 5 ms switch interval (`--default-switch`): 433 of 1000 rounds.

*Classification:* a real bug in the Python layer. The docstring says the cache "never
serves results that pre-date a table change".

*Fix:* make the generation read at call start part of the lru key:

```python
@lru_cache(maxsize=maxsize)
def _cached(text, _gen): ...


def cached(text):
    g = _registration_generation
    if g != seen_generation:
        _cached.cache_clear()  # memory only
        seen_generation = g
    return _cached(text, g)
```

A result computed from an old table can then only be stored under the old generation,
which no later call looks up. `CachedTransliterator_fixed.cfg` passes this.

### F6: `UniqueSlugifier` with a `check` callback

`_UniqueSlugifier::slugify(&mut self)` (`src/py/slugify.rs:397`) calls `check`
(`:464`) while PyO3's exclusive borrow is held.

*Reproduction:* `r6_unique_slugifier_borrow.py`.

*Observed:*

* (a) A re-entrant call from inside `check` raises `RuntimeError: Already borrowed`.
* (b) Four threads share one slugifier whose `check` sleeps 50 ms (standing in for a
  database lookup): 3 of 4 calls raise `RuntimeError: Already borrowed`.

*Classification:* nothing deadlocks and no state is corrupted; the error is PyO3's
defined borrow error. The object is simply not usable from more than one thread, and
the docs do not say so.

*Fix:* document the object as single-threaded. Alternatively, wrap it in a Python
`threading.Lock` in `UniqueSlugifier.__call__`, or restructure the Rust method so that
it releases the borrow around `check`: take `&self` for the scan, re-borrow `&mut` to
insert, and re-check `seen` after `check` returns.

### F7: `recover_lock` attaches to the GIL while holding the recovered guard (latent)

`recover_lock` (`src/lib.rs:402-441`) receives a `LockResult` whose `Err` already
contains the guard, then calls `Python::attach` → `warnings.warn`.

*Consequences:*

* Inside `py.detach` (`apply_replacements` at `tables/mod.rs:690`, `lookup_registered`
  at `:423`, the slugify automaton cache at `slugify.rs:228/238`), this is a lock-then-GIL
  order. It deadlocks against any GIL-holding writer (`ReplacementTables_poison.cfg`).
* On the attached writer paths it runs arbitrary Python code (the
  `warnings.showwarning` hook or filters) under a write guard, which is the F1 shape.

*Why it is latent:* only a panic while a *write* guard is live poisons a std `RwLock`.
The write regions are:

* `GLOBAL_REPLACEMENTS_AC`: `*slot = built` at `mod.rs:130-131`.
* `LANG_TABLES`: `HashMap::insert` at `mod.rs:561-565`.
* The slugify caches: `clear`/`insert`.

None of these can panic in practice. The one `.expect` under a write guard is the
aho-corasick build at `mod.rs:120`, under `GLOBAL_REPLACEMENTS`. It needs more than
2^31 automaton states, meaning gigabytes of keys, and only writers take that lock
anyway. I found no way to poison any of these locks from Python, so there is no
reproduction.

*Fix:* in `recover_lock`, call `into_inner()` first and emit the warning after the
caller has dropped the guard. Alternatively, only record the poisoning (for example
`tl_error!` plus an atomic flag) and emit the warning from an attached, guard-free point.
At minimum, never `Python::attach` while holding the guard.

### F8: `register_lang` check-then-act (Rust API only)

`check_not_sealed`, `registered_lang_count()` and `register_lang` each take and release
their own lock or atomic.

*Model results:*

* With the GIL (the PyO3 shim holds it for the whole call, runs no Python in between,
  and blocking on `LANG_TABLES.write()` does not release it): **pass**
  (`Registration_python.cfg`).
* Without it (the public Rust API, `src/api/transliterate.rs:271-272`):
  * two concurrent registrations exceed `MAX_REGISTERED_LANGS`;
  * a registration can land after `seal_registrations()` has returned.

`register_replacements` checks its cap under the write lock and is not affected by the
cap race, but it is affected by the seal race.

*Reproduction:* none. It is not reachable from Python, and no other binding exposes
`register_lang`. Building a Rust reproduction was outside the constraints of this
exercise.

*Fix:* move the seal check and the cap check inside the `LANG_TABLES` write guard.
Check `REGISTRATIONS_SEALED` again under the guard, and have `seal_registrations` take
the same write locks when it sets the flag.

## Checked and clean

* **Provider `lookup` re-entrancy** (`r0_provider_lookup_reentrancy.py`, exit 0).
  `_demojize` drops its read guard before calling `lookup`, so a `lookup` that calls
  `demojize` and `set_emoji_provider` works.
  * The in-flight call keeps using the provider it snapshotted:
    `OUTER[INNER] OUTER[OTHER]`, where both emoji are named by the snapshotted provider.
  * The next call sees the new provider (`OTHER`).
  * 20,000 `demojize` calls against a thread swapping providers returned only
    `{'OTHER', 'grinning face'}` and never deadlocked.
  * This is the defined outcome of `set_emoji_provider` during `demojize`: snapshot per
    call.
* **The replacement pair.** `ACInSync`, `ItemLinearizable` and `BatchLinearizable` hold
  for 2 writers and 1 batch reader (606k distinct states). The lock order is always
  table → AC, and readers never take the table lock. `HAS_REPLACEMENTS` is only a hint:
  a stale `false` linearizes before the unreturned mutation.
* **Detached closures.**
  * `_normalize_batch` (`src/py/normalize.rs:60`) and `_strip_accents_batch`
    (`src/py/transliterate.rs:487`) touch no lock and no Python object.
  * `_transliterate_batch` and `_slugify_batch` (`src/py/slugify.rs:162`) take only
    `GLOBAL_REPLACEMENTS_AC`, `LANG_TABLES` and `REPLACEMENT_AUTOMATON_CACHE`, all for
    short, non-nested scopes. They never re-attach, except on the F7 poison path, and
    never call the Python fallback.
  * Writers wait on those locks while holding the GIL, but the detached holders need no
    GIL to finish, so there is no cycle.
* **No nested acquisition anywhere.** Every `read()` and `write()` site (`emoji.rs:29,268`;
  `transliterate.rs:112,170`; `tables/mod.rs:130,185,190,423,488,561,603,645,662,690`;
  `slugify.rs:67,72,228,238`) holds its guard for a short scope that makes no nested
  acquisition of the same lock. So the writer-preferring "recursive read" hazard is
  unreachable.
* **`OnceLock` / `LazyLock` initialisers.** These are the context dictionaries
  (`src/context.rs:549-551`), `HANGUL_ROMANIZATIONS`, the contraction automaton and the
  lock statics. They are pure Rust and never call Python, so a detached thread
  initialising one can never wait on the GIL.
* **`src/presets.rs` `thread_local!`** (`:894-899`) is `#[cfg(test)]` only.

## Files

* `EmojiProvider.tla` + `EmojiProvider_{lookup,reentrant,gil,gil_readerpref,fixed}.cfg`
* `ReplacementTables.tla` + `ReplacementTables{,_batch,_poison,_fixed}.cfg`
* `CachedTransliterator.tla` + `CachedTransliterator{,_fixed}.cfg`
* `Registration.tla` + `Registration_{python,rust,rust_seal}.cfg`
* `run_tlc.sh`: runs every config and prints a verdict line for each.
* `repro/r0` … `repro/r6`: the Python reproductions. Each docstring names its site, the
  TLC config and the expected exit code.
