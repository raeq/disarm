#!/usr/bin/env python3
"""The hostname screen against the UTS #46 mapping it runs: which characters does the
mapping delete from a label without `is_suspicious_hostname` saying so?

    python3 scripts/sweep_hostname.py

For every non-ASCII scalar `c`, `ev<c>il.com` is screened. A row is printed when the
verdict is "not suspicious" and `canonical` is `evil.com`: the character vanished, so a
blocklist holding `evil.com` never sees the raw name, and a resolver maps it back to
`evil.com`. The anomaly detector's verdict on `ev<c>il` is printed beside it.
"""

from __future__ import annotations

import sys
import unicodedata

import disarm


def main() -> int:
    rows = []
    for cp in range(0x80, 0x110000):
        if 0xD800 <= cp <= 0xDFFF:
            continue
        suspicious, analysis = disarm.is_suspicious_hostname("ev" + chr(cp) + "il.com")
        if not suspicious and analysis.canonical == "evil.com":
            rows.append(cp)
    print(f"{len(rows)} code points deleted silently by the hostname screen")
    for cp in rows:
        c = chr(cp)
        print(
            f"  U+{cp:04X} {unicodedata.category(c)} {unicodedata.name(c, '?'):45}"
            f" has_anomalies('ev<c>il') = {disarm.has_anomalies('ev' + c + 'il')}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
