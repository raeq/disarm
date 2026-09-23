"""Finding 1: `canonicalize` deletes a deprecated format control from inside a word, and
`has_anomalies` says nothing. The same shape #813 fixed for `U+1D173`."""

import disarm

for s in [
    "pay\u200bpal",
    "pay\U0001d173pal",  # reported: #700, #813
    "pay\u206apal",
    "pay\u206fpal",
    "pay\ufff9pal",
    "pay\ufffbpal",  # not reported
    "pay\ufdd0pal",
]:  # a noncharacter: deleted too, not reported
    print(
        ascii(s),
        disarm.has_anomalies(s),
        ascii(disarm.canonicalize(s)),
        ascii(disarm.strip_bidi(s)),
    )
