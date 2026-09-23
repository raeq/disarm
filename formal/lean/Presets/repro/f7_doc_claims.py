"""Finding 7: documented properties of the presets and profiles that do not hold.

(a) The empty-key census: "N single characters reduce to "" here, and so does every string
    built from them" (`ml_normalize` docstring, `docs/limitations.md`).
(b) `catalog_key`, `search_key`, `sort_key` docstrings: "Private-use characters survive
    into the key".
(c) `docs/api/pipelines.md`: `ml_corpus_normalize` output is "ASCII".
(d) The `digit_policy` notes on `search_key`/`sort_key`/`catalog_key`: the policy "folds
    digit variants on the raw text". It folds every confusable. And `docs/limitations.md`
    "Five surfaces rewrite printable ASCII": `search_key` and `sort_key` "no", and "these are
    the only printable ASCII characters any surface changes".
(e) The `strip_obfuscation` docstring lists a `demojize` step; `canonicalize_strict`'s
    docstring puts `strip_zalgo` before `confusables`.
"""

from __future__ import annotations

import inspect

from common import profile, w

import disarm

ri_u, ri_s = w(0x1F1FA), w(0x1F1F8)
print(
    "(a) ml_normalize(U) =",
    repr(disarm.ml_normalize(ri_u)),
    " ml_normalize(S) =",
    repr(disarm.ml_normalize(ri_s)),
    " ml_normalize(U + S) =",
    repr(disarm.ml_normalize(ri_u + ri_s)),
)

pua = "ab" + w(0xE000)
print("(b)", {k: ascii(getattr(disarm, k)(pua)) for k in ("catalog_key", "search_key", "sort_key")})

cjk = w(0x4E2D, 0x6587)
print("(c) ml_corpus_normalize(two CJK ideographs) =", ascii(profile("ml_corpus_normalize")(cjk)))

cyr = w(0x440, 0x430, 0x443, 0x440, 0x430, 0x6C)  # Cyrillic er, a, u, er, a + Latin l
for pol in ("numeric", "preserve"):
    print(
        f"(d) search_key(cyrillic 'paypal', digit_policy={pol!r}) =",
        repr(disarm.search_key(cyr, digit_policy=pol)),
        " sort_key:",
        repr(disarm.sort_key(cyr, digit_policy=pol)),
    )

for name in ("search_key", "sort_key"):
    f = getattr(disarm, name)
    print(
        f"(d) {name}('|' '\"' '`', digit_policy='tr39') =",
        [f(c, digit_policy="tr39") for c in '|"`'],
        " default:",
        [f(c) for c in '|"`'],
    )
print("(d) skeleton_key('I') =", repr(disarm.skeleton_key("I")))

doc = inspect.getdoc(disarm.strip_obfuscation) or ""
print(
    "(e) strip_obfuscation docstring names demojize:", "demojize" in doc.split("Pipeline:")[1][:200]
)
print("    strip_obfuscation(grinning face) =", ascii(disarm.strip_obfuscation(w(0x1F600))))
