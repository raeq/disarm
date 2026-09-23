#!/usr/bin/env python3
"""Every code point, through the Python binding: the confusable properties the docs
claim, checked directly against the installed library (no model involved).

Per code point c, for each of the 4 targets and 3 digit policies:
  idempotent          f(f(c)) == f(c)
  complete            not is_confusable(f(c))                (claimed; fails under preserve: F2)
  nfc_nfd             f(NFC c) == f(NFD c)                   (F4)
  isc_nfc_nfd         is_confusable(NFC c) == is_confusable(NFD c)
  is_vs_find          is_confusable(c) == bool(find_confusables(c))
  confusable_but_fixed  is_confusable(c) and f(c) == c
  unmapped_vs_find    c in unmapped_confusables(t) <=> find_unmapped_confusables(c) == [(c, 0)]
  unmapped_but_folds  c in unmapped_confusables(t) and f(c) != c
  tr39_nonlatin       tr39 differs from numeric under a non-Latin target
  tr39_diff / preserve_diff   (counted, not failures: the rows each policy owns)
and skeleton_key under each policy: idempotent (F1), lowercase, NFD-invariant (F3).

Then: non-NFC code points against their NFC image; lone surrogates and other odd
inputs never raise; find_key_collisions(key="normalize_confusables") against a
reference grouping, with the #763 reduced-count formula; and the documented counts.

Usage: python3 search/sweep_codepoints.py        (about 5 minutes)
"""

from __future__ import annotations

import collections
import random
import sys

import disarm as d

T = ["latin", "cyrillic", "arabic", "hebrew"]
P = ["numeric", "tr39", "preserve"]
nc = d.normalize_confusables
isc = d.is_confusable
bad: dict[str, list] = collections.defaultdict(list)
count: collections.Counter = collections.Counter()


def rec(k: str, v) -> None:
    count[k] += 1
    if len(bad[k]) < 8:
        bad[k].append(v)


unm = {t: d.unmapped_confusables(target_script=t) for t in T}
for cp in range(0x110000):
    if 0xD800 <= cp <= 0xDFFF:
        continue
    c = chr(cp)
    nfc = d.normalize(c, form="NFC")
    nfd = d.normalize(c, form="NFD")
    for t in T:
        r = {p: nc(c, target_script=t, digit_policy=p) for p in P}
        ic = isc(c, target_script=t)
        if ic != bool(d.find_confusables(c, target_script=t)):
            rec(f"is_vs_find/{t}", cp)
        if ic and r["numeric"] == c:
            rec(f"confusable_but_fixed/{t}", cp)
        for p in P:
            o = r[p]
            if nc(o, target_script=t, digit_policy=p) != o:
                rec(f"idempotent/{t}/{p}", cp)
            if isc(o, target_script=t):
                rec(f"complete/{t}/{p}", cp)
            if nc(nfc, target_script=t, digit_policy=p) != nc(nfd, target_script=t, digit_policy=p):
                rec(f"nfc_nfd/{t}/{p}", cp)
        if t != "latin" and r["tr39"] != r["numeric"]:
            rec(f"tr39_nonlatin/{t}", cp)
        if r["tr39"] != r["numeric"]:
            rec(f"(count) tr39_diff/{t}", cp)
        if r["preserve"] != r["numeric"]:
            rec(f"(count) preserve_diff/{t}", cp)
        if isc(nfc, target_script=t) != isc(nfd, target_script=t):
            rec(f"isc_nfc_nfd/{t}", cp)
        fu = d.find_unmapped_confusables(c, target_script=t)
        if (c in unm[t]) != (fu == [(c, 0)]):
            rec(f"unmapped_vs_find/{t}", cp)
        if c in unm[t] and r["numeric"] != c:
            rec(f"unmapped_but_folds/{t}", cp)
    for p in P:
        k = d.skeleton_key(c, digit_policy=p)
        if d.skeleton_key(k, digit_policy=p) != k:
            rec(f"sk_idempotent/{p}", cp)
        if d.fold_case(k) != k:
            rec(f"sk_lowercase/{p}", cp)
        if d.skeleton_key(nfd, digit_policy=p) != k:
            rec(f"sk_nfd/{p}", cp)
    if cp % 0x10000 == 0:
        print(f"... U+{cp:04X}", file=sys.stderr, flush=True)

# Non-NFC code points against their NFC image.
for cp in range(0x110000):
    if 0xD800 <= cp <= 0xDFFF:
        continue
    c = chr(cp)
    n = d.normalize(c, form="NFC")
    if n == c:
        continue
    for t in T:
        if isc(c, target_script=t) != isc(n, target_script=t):
            rec(f"(note) detect_c_vs_nfc/{t}", cp)
        a, b = nc(c, target_script=t), nc(n, target_script=t)
        if d.normalize(a, form="NFC") != d.normalize(b, form="NFC"):
            rec(f"fold_c_vs_nfc/{t}", cp)

# Odd inputs never raise.
for s in ["\ud800", "a\udfff", "", "\x00" * 5, "\U0010ffff", "\ufffd"]:
    for name, f in [
        ("normalize_confusables", lambda s: nc(s)),
        ("normalize_confusables(tr39)", lambda s: nc(s, digit_policy="tr39")),
        ("is_confusable", isc),
        ("skeleton_key", d.skeleton_key),
        ("find_confusables", d.find_confusables),
        ("find_unmapped_confusables", d.find_unmapped_confusables),
    ]:
        try:
            f(s)
        except Exception as e:  # noqa: BLE001 - the property is "never raises"
            rec(f"raises/{name}", (ascii(s), type(e).__name__))

# find_key_collisions(key="normalize_confusables") against a reference grouping.
rng = random.Random(3)
pool = [
    "admin",
    "\u0430dmin",
    "adm\u0131n",
    "Admin",
    "\u04aa\u0327",
    "\u00c7",
    "C",
    "c",
    "\u00a5\u0300",
    "\u1ef2",
    "\u0966",
    "0",
    "|",
    "l",
    "x",
]
for _ in range(3000):
    vals = [rng.choice(pool) + rng.choice(["", "a", "\u0430"]) for _ in range(rng.randint(0, 9))]
    got = [
        (g.key, list(g.values), list(g.indices))
        for g in d.find_key_collisions(vals, key="normalize_confusables")
    ]
    ref: dict = {}
    for i, v in enumerate(vals):
        k = nc(v)
        g = ref.setdefault(k, (k, [], []))
        if v not in g[1]:
            g[1].append(v)
        g[2].append(i)
    if got != [g for g in ref.values() if len(g[1]) > 1]:
        rec("collisions_vs_reference", vals)
    if len(set(vals)) - sum(len(g[1]) for g in got) + len(got) != len({nc(v) for v in vals}):
        rec("collisions_763_formula", vals)
count["(checked) collision batches"] = 3000

# Documented counts.
print("ASCII in unmapped_confusables('latin'):", sorted(ch for ch in unm["latin"] if ch.isascii()))
print("unmapped sizes:", {t: len(unm[t]) for t in T})

for k in sorted(count):
    ex = bad.get(k, [])
    shown = [f"U+{x:04X}" if isinstance(x, int) else x for x in ex]
    print(f"{k:40s} {count[k]:8d}  {shown}")
