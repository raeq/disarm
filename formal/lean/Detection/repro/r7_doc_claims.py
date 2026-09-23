"""Finding 7: documentation the code contradicts."""

import disarm

# docs/api/predicates.md: "the detector never fires on text the canonicalizer would leave alone"
for s in ["a\u03bb", "a\u05d0"]:
    print(ascii(s), disarm.is_canonical(s), disarm.inspect_anomalies(s).kinds)

# src/anomalies.rs, DuplicateMark: "a duplicate survives canonicalization whatever the cap is"
print(ascii(disarm.canonicalize("x\u0301\u0301")), ascii(disarm.canonicalize("x\u0301")))
