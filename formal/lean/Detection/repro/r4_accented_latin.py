"""Finding 4: `confusable` fires on ordinary accented and stroked Latin letters, which the
anomaly guide lists as spared ("accented Latin, which the fold leaves alone")."""

import disarm

for s in [
    "Fran\u00e7ais",
    "gar\u00e7on",
    "T\u00fcrk\u00e7e",
    "a\u00e7\u00e3o",
    "K\u00f8benhavn",
    "\u0141\u00f3d\u017a",
    "\u0111\u01b0\u1eddng",
    "ch\u1ec9",
    "caf\u00e9",
    "na\u00efve",
    "stra\u00dfe",
]:
    r = disarm.inspect_anomalies(s)
    print(
        ascii(s),
        r.kinds,
        [f.detail.encode("ascii", "backslashreplace").decode() for f in r.findings],
        ascii(disarm.canonicalize(s)),
    )
