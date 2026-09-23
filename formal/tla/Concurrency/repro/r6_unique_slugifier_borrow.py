"""F6: UniqueSlugifier holds a PyO3 &mut borrow across the `check` callback.

`_UniqueSlugifier::slugify(&mut self, ...)` (src/py/slugify.rs:397) calls the
Python `check` callback (slugify.rs:464) while PyO3's exclusive borrow of the
object is held. Nothing deadlocks (PyO3's borrow flag is not a lock) but:

  (a) re-entrant use from inside `check` raises RuntimeError("Already borrowed");
  (b) a second thread calling the same UniqueSlugifier while the first thread's
      `check` runs Python code / blocking I/O (the documented use: "e.g.
      database lookup") gets RuntimeError("Already borrowed") instead of
      waiting.

Run: timeout 20 python3 r6_unique_slugifier_borrow.py
"""

import threading
import time

import disarm

# (a) re-entrant
holder = {}


def check_reentrant(candidate):
    try:
        holder["u"]("nested")
    except Exception as e:  # noqa: BLE001
        holder["err"] = f"{type(e).__name__}: {e}"
    return False


holder["u"] = disarm.UniqueSlugifier(check=check_reentrant)
print("(a) outer result:", holder["u"]("Hello"), "| nested call ->", holder.get("err"))


# (b) two threads, check does blocking I/O
def check_db(candidate):
    time.sleep(0.05)  # stand-in for a DB round-trip (releases the GIL)
    return False


u = disarm.UniqueSlugifier(check=check_db)
errors = []


def worker(title):
    try:
        u(title)
    except Exception as e:  # noqa: BLE001
        errors.append(f"{type(e).__name__}: {e}")


ts = [threading.Thread(target=worker, args=(f"post {i}",)) for i in range(4)]
for t in ts:
    t.start()
for t in ts:
    t.join()
print(f"(b) {len(errors)}/4 concurrent calls raised; e.g. {errors[:1]}")
