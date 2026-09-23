"""One `UniqueSlugifier` is usable from several threads (F6).

`_UniqueSlugifier.slugify` holds PyO3's exclusive borrow of the object while it calls
`check`, and a `check` that does I/O, the documented use ("e.g. database lookup"),
gives up the GIL. A second thread's call then found the object borrowed and raised
`RuntimeError: Already borrowed` instead of waiting: three of four calls failed in the
TLA+ model's reproduction (`formal/tla/Concurrency`, F6). The wrapper now serialises
calls, which uniqueness needs anyway.
"""

from __future__ import annotations

import threading
import time

import pytest

from disarm import UniqueSlugifier


def _run(u: UniqueSlugifier, titles: list[str]) -> tuple[list[str], list[BaseException]]:
    slugs: list[str] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker(title: str) -> None:
        try:
            slug = u(title)
        except BaseException as e:  # noqa: BLE001 - collected and asserted on
            with lock:
                errors.append(e)
        else:
            with lock:
                slugs.append(slug)

    # Daemon threads, and an explicit check that each finished: a hung call must fail
    # here by name, not as a missing slug, and must not hold the interpreter open at
    # exit (Copilot review on #1014).
    threads = [threading.Thread(target=worker, args=(t,), daemon=True) for t in titles]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not any(t.is_alive() for t in threads), "a call did not return within 30 s"
    return slugs, errors


def _slow_check(candidate: str) -> bool:
    time.sleep(0.05)  # a database round-trip; releases the GIL
    return False


def test_concurrent_calls_wait_rather_than_raise() -> None:
    slugs, errors = _run(UniqueSlugifier(check=_slow_check), [f"post {i}" for i in range(4)])
    assert errors == []
    assert sorted(slugs) == [f"post-{i}" for i in range(4)]


def test_concurrent_calls_on_one_title_stay_unique() -> None:
    slugs, errors = _run(UniqueSlugifier(check=_slow_check), ["same"] * 4)
    assert errors == []
    assert sorted(slugs) == ["same", "same-1", "same-2", "same-3"]


def test_a_reentrant_call_from_check_still_fails_cleanly() -> None:
    """Re-entry is a caller bug; it must raise, not deadlock on the new lock."""
    holder: dict[str, UniqueSlugifier] = {}

    def check(candidate: str) -> bool:
        holder["u"]("nested")
        return False

    holder["u"] = UniqueSlugifier(check=check)
    with pytest.raises(RuntimeError):
        holder["u"]("outer")
