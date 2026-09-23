"""Finding 2: `search_key` and `sort_key` are not fixed points under a digit policy.

Model: `Findings.search_vy`, `search_click`, `sort_macron`, `search_vy_numeric`.
"""

from __future__ import annotations

import functools

from common import show, w

import disarm

for name in ("search_key", "sort_key", "catalog_key"):
    for pol in ("numeric", "tr39", "preserve"):
        f = functools.partial(getattr(disarm, name), digit_policy=pol)
        show(f"{name}[{pol}] Latin capital VY", w(0xA760), f)
        show(f"{name}[{pol}] lateral click", w(0x1C1), f)
        show(f"{name}[{pol}] A with macron", w(0x100), f)

print()
cyr = w(0x440, 0x430, 0x443, 0x440, 0x430, 0x6C)
for pol in ("numeric", "tr39", "preserve"):
    print(
        f"search_key({ascii(cyr)}, digit_policy={pol!r}) = {disarm.search_key(cyr, digit_policy=pol)!r}"
    )
