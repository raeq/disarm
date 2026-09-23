"""Shared helpers for the premise searches (see ../README.md).

Every search drives the *installed* `disarm` Python package (the real Rust core
behind the PyO3 binding); nothing here reimplements transliteration.
"""

from __future__ import annotations

import itertools
import json
import random
import sys
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

import disarm

T = disarm.transliterate
SURROGATES = range(0xD800, 0xE000)


def all_scalars(lo: int = 0, hi: int = 0x10FFFF) -> Iterator[str]:
    """Every Unicode scalar value in [lo, hi] (surrogates excluded)."""
    for cp in range(lo, hi + 1):
        if cp not in SURROGATES:
            yield chr(cp)


def block(lo: int, hi: int, assigned_only: bool = True) -> list[str]:
    """Characters of a code-point range; by default only assigned ones."""
    return [c for c in all_scalars(lo, hi) if not assigned_only or unicodedata.category(c) != "Cn"]


@dataclass(frozen=True)
class Opts:
    """One `transliterate` keyword profile."""

    lang: str | None = None
    errors: str = "ignore"
    strict_iso9: bool = False
    gost7034: bool = False
    tones: bool = False
    context: bool = False
    replace_with: str = "[?]"

    def kwargs(self) -> dict[str, Any]:
        kw: dict[str, Any] = {"errors": self.errors}
        if self.lang is not None:
            kw["lang"] = self.lang
        if self.strict_iso9:
            kw["strict_iso9"] = True
        if self.gost7034:
            kw["gost7034"] = True
        if self.tones:
            kw["tones"] = True
        if self.context:
            kw["context"] = True
        if self.errors == "replace":
            kw["replace_with"] = self.replace_with
        return kw

    def f(self, s: str) -> str:
        return T(s, **self.kwargs())

    def call_repr(self, s: str) -> str:
        """A copy-pasteable Python expression for this call."""
        kw = ", ".join(f"{k}={v!r}" for k, v in self.kwargs().items())
        return f"disarm.transliterate({s!r}, {kw})"

    def label(self) -> str:
        parts = [f"errors={self.errors}"]
        if self.lang is not None:
            parts.append(f"lang={self.lang}")
        for flag in ("strict_iso9", "gost7034", "tones", "context"):
            if getattr(self, flag):
                parts.append(flag)
        return ",".join(parts)


def langs() -> list[str]:
    return list(disarm.list_langs())


def profiles(
    errors_modes: Iterable[str] = ("ignore",),
    include_langs: bool = True,
    include_tones: bool = True,
) -> list[Opts]:
    """The option cross-product the invariants are checked under.

    `strict_iso9` and `gost7034` are mutually exclusive (the API rejects both);
    `tones` is combinable with everything forward. `context=True` needs a
    dictionary and is handled by `context_dict.py`.
    """
    out: list[Opts] = []
    lang_axis: list[str | None] = [None, "auto"] + (langs() if include_langs else [])
    for errors in errors_modes:
        for lang in lang_axis:
            for iso9, gost in ((False, False), (True, False), (False, True)):
                for tones in (False, True) if include_tones else (False,):
                    out.append(Opts(lang, errors, iso9, gost, tones))
    return out


def is_ascii(s: str) -> bool:
    return s.isascii()


def i7_bound(s: str) -> int:
    return len(s.encode("utf-8")) * 5 + len(s)


@dataclass
class Tally:
    """Counts checks and keeps the shortest counterexamples per key."""

    checked: int = 0
    failures: dict[str, int] = field(default_factory=dict)
    examples: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    keep: int = 5

    def ok(self) -> None:
        self.checked += 1

    def fail(self, key: str, example: dict[str, Any]) -> None:
        self.checked += 1
        self.failures[key] = self.failures.get(key, 0) + 1
        ex = self.examples.setdefault(key, [])
        ex.append(example)
        ex.sort(key=lambda e: (len(e.get("input", "")), e.get("input", "")))
        del ex[self.keep :]

    def to_json(self) -> dict[str, Any]:
        return {"checked": self.checked, "failures": self.failures, "examples": self.examples}


def dump(obj: Any, path: str | None = None) -> None:
    text = json.dumps(obj, ensure_ascii=True, indent=1, sort_keys=True)
    if path:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    else:
        sys.stdout.write(text + "\n")


def pairs(xs: list[str], ys: list[str] | None = None) -> Iterator[tuple[str, str]]:
    return itertools.product(xs, ys if ys is not None else xs)


def sample(xs: list[str], k: int, seed: int = 0) -> list[str]:
    if len(xs) <= k:
        return list(xs)
    return random.Random(seed).sample(xs, k)
