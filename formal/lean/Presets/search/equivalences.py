#!/usr/bin/env python3
"""Library-only sweeps for the equivalences the docs claim between surfaces.

    python3 search/equivalences.py

1. Each named profile against the `TextPipeline` transcribed from its `ProfileSpec`
   (src/pipeline.rs), field for field (#918: "A `TextPipeline` transcribed from a
   `ProfileSpec` field for field must behave like the profile").
2. `is_canonical(text, preset=name)` against `name(text) == text`, for every preset name, the
   three deprecated aliases and every profile (#730: "Equivalent to
   `globals()[preset](text) == text` and defined by it").
3. `digit_policy="numeric"` against no argument, on every builder ("a genuine no-op").

Over every scalar in planes 0-3 and 14 (surrogates excepted), and every string of the `F2`
and `F3` families of `idempotence.py`. Prints mismatch counts; exit status 0 when there are
none.
"""

from __future__ import annotations

import multiprocessing as mp
import sys

import disarm

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from idempotence import gen  # noqa: E402

TRANSCRIBED = {
    "scholarly_cyrillic_iso9": dict(
        normalize="NFKC",
        transliterate=True,
        strict_iso9=True,
        fold_case=True,
        collapse_whitespace=True,
        strip_pua=True,
        strip_plane14=True,
    ),
    "library_catalog_key_eu": dict(
        normalize="NFKC",
        transliterate=True,
        confusables=True,
        strip_accents=True,
        fold_case=True,
        collapse_whitespace=True,
        strip_pua=True,
        strip_plane14=True,
    ),
    "normalize_web_input": dict(
        normalize="NFKC", confusables=True, collapse_whitespace=True, strip_pua=True
    ),
    "ml_corpus_normalize": dict(
        normalize="NFKC",
        demojize=True,
        strip_accents=True,
        fold_case=True,
        collapse_whitespace=True,
        strip_pua=True,
        strip_plane14=True,
    ),
    "search_index": dict(
        normalize="NFKC",
        transliterate=True,
        strip_accents=True,
        fold_case=True,
        collapse_whitespace=True,
        strip_pua=True,
        strip_plane14=True,
    ),
    "code_context": dict(strip_bidi=True, strip_zero_width=True, strip_control=True),
    "llm_guardrail": dict(
        normalize="NFKC",
        resolve_deletions=True,
        strip_zalgo=0,
        strip_bidi=True,
        strip_zero_width=True,
        strip_control=True,
        confusables=True,
        strip_accents=True,
        fold_case=True,
        collapse_whitespace=True,
        strip_pua=True,
        strip_plane14=True,
    ),
    "rag_ingest": dict(
        normalize="NFKC",
        resolve_deletions=True,
        strip_bidi=True,
        strip_control=True,
        strip_zero_width=True,
        transliterate=True,
        strip_accents=True,
        collapse_whitespace=True,
        strip_pua=True,
        strip_plane14=True,
    ),
}

PRESET_NAMES = [
    "canonicalize",
    "canonicalize_strict",
    "strip_format",
    "strip_obfuscation",
    "search_key",
    "catalog_key",
    "sort_key",
    "ml_normalize",
]
ALIASES = {
    "security_clean": "canonicalize",
    "display_clean": "strip_format",
    "normalize_user_input": "canonicalize_strict",
}
POLICY_BUILDERS = [
    "canonicalize",
    "canonicalize_strict",
    "strip_obfuscation",
    "search_key",
    "catalog_key",
    "sort_key",
    "skeleton_key",
]


def inputs():
    for cp in list(range(0, 0x40000)) + list(range(0xE0000, 0xE1000)):
        if 0xD800 <= cp < 0xE000:
            continue
        yield chr(cp)


def check(strs):
    import warnings

    warnings.simplefilter("ignore", DeprecationWarning)
    bad = {}
    prof = {n: disarm.get_pipeline(n) for n in TRANSCRIBED}
    hand = {n: disarm.TextPipeline(**kw) for n, kw in TRANSCRIBED.items()}
    for s in strs:
        for n in TRANSCRIBED:
            if prof[n](s) != hand[n](s):
                bad.setdefault(f"profile!=transcribed:{n}", []).append(s)
        for n in PRESET_NAMES + list(ALIASES) + list(TRANSCRIBED):
            f = getattr(disarm, ALIASES.get(n, n)) if n not in TRANSCRIBED else prof[n]
            if disarm.is_canonical(s, preset=n) != (f(s) == s):
                bad.setdefault(f"is_canonical:{n}", []).append(s)
        for n in POLICY_BUILDERS:
            f = getattr(disarm, n)
            if f(s, digit_policy="numeric") != f(s):
                bad.setdefault(f"numeric_noop:{n}", []).append(s)
    return {k: (len(v), v[:3]) for k, v in bad.items()}


def main() -> int:
    strs = list(inputs()) + list(gen("F2")) + list(gen("F3"))
    chunks = [strs[i::32] for i in range(32)]
    with mp.Pool(4) as pool:
        res = pool.map(check, chunks)
    total = {}
    for r in res:
        for k, (n, ex) in r.items():
            t = total.setdefault(k, [0, []])
            t[0] += n
            t[1] += ex
    print(f"strings: {len(strs)}")
    for k, (n, ex) in sorted(total.items()):
        print(f"MISMATCH {k}: {n}  e.g. {[ascii(e) for e in ex[:3]]}")
    if not total:
        print("no mismatches")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
