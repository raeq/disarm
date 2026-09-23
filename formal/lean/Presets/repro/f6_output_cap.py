"""Finding 6: the preset output ceiling is neither an output bound nor input-size neutral.

`docs/api/exceptions.md` and the 0.15 changelog: "Every preset now raises
`ResourceLimitError` above 10 MiB of produced output"; "The cap is on produced output, so
ordinary text cannot reach it"; `src/limits.rs`: "disarm does not cap raw input size".
The check sits on the NFKC step's output only (src/presets.rs L319-L331).
"""

from __future__ import annotations

from common import w

import disarm

MIB = 1024 * 1024

# (a) A step after NFKC amplifies, uncapped. U+1FAF0 is 4 bytes and is named in 40.
s = w(0x1FAF0) * 2_600_000
out = disarm.ml_normalize(s)
print(
    f"(a) ml_normalize: {len(s.encode()):,} bytes in -> {len(out.encode()):,} bytes out, no error"
    f" (limit {10 * MIB:,})"
)

# (b) The ceiling rejects ordinary input that expands by nothing, and only when the fast
#     path does not return it first.
big = "a" * (11 * MIB)
print("(b) canonicalize(11 MiB of 'a'):", len(disarm.canonicalize(big)), "chars, accepted")
for label, text, f in (
    ("canonicalize('\"' + 11 MiB of 'a')", '"' + big, disarm.canonicalize),
    ("search_key('A' + 11 MiB of 'a')", "A" + big, disarm.search_key),
):
    try:
        f(text)
        print(f"    {label}: accepted")
    except disarm.ResourceLimitError as e:
        print(f"    {label}: ResourceLimitError: {e}")
