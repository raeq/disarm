- **Replacing the emoji provider could hang the interpreter.** `set_emoji_provider`
  stored the new provider with the write lock held, and storing it dropped the old one
  there and then — running its `__del__`, which is arbitrary Python, inside the lock. If
  that `__del__` called `set_emoji_provider` or `demojize`, the thread waited on its own
  lock. With no re-entrancy at all, a `__del__` that gave up the GIL (closing a file or a
  socket does) let another thread's `demojize` take the GIL and then block on the lock
  while holding it, and neither thread could proceed. The internal transliterate
  dispatcher had the same shape. The old object is now dropped after the lock is
  released. Found by a TLA+ model of the binding's locks and the GIL
  (`formal/tla/Concurrency`); each case is now a subprocess test with a timeout.
