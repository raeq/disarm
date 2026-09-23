- **A registration could land after `seal_registrations()` returned, and past the
  language cap.** Found by a TLA+ model of the registration paths
  (`formal/tla/Concurrency`). In the public Rust API the seal check, the cap check and
  the write each took and released their own lock, so a `register_lang` already past
  the seal check still wrote its table after another thread's `seal_registrations()`
  had returned, which is the one thing a seal is for, and sixteen threads racing for
  the last of the 100 language slots took it 10 to 16 times. Every mutator, and the
  seal, now go through one registration gate. Python was not exposed to either race,
  since it holds the GIL across the call. It was exposed to a third: one
  `UniqueSlugifier` shared between threads raised `RuntimeError: Already borrowed`
  whenever a `check` callback doing I/O was running on another thread. Calls to one
  instance are now serialised. The `register_lang` and `register_replacements`
  docstrings now also say that a batch call already in progress can mix the old table
  with the new.
