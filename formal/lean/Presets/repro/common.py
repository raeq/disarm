"""Shared helpers for the reproductions.

Test strings are built from code points with `w(...)`, never written as literals or escapes
in these files, so no invisible or non-ASCII character can enter the source by accident.
"""

from __future__ import annotations

import disarm


def w(*cps: int) -> str:
    return "".join(map(chr, cps))


def show(label: str, text: str, f) -> tuple[str, str]:
    once = f(text)
    twice = f(once)
    status = "fixed point" if once == twice else "NOT A FIXED POINT"
    print(f"{label:<44} {ascii(text):<24} -> {ascii(once):<22} -> {ascii(twice):<22} {status}")
    return once, twice


def profile(name: str, **kw):
    return disarm.get_pipeline(name, **kw)
