#!/usr/bin/env python3
"""Rewrite every non-ASCII character in the given files as a backslash escape.

The repository rejects literal invisible characters, and an editor can silently turn an
escape into the character it names. Run this over a file after editing it; it is
idempotent and only touches non-ASCII code points (which, in this directory, only ever
occur inside string literals).
"""

import sys

for path in sys.argv[1:]:
    with open(path, encoding="utf-8") as f:
        src = f.read()
    out = []
    for ch in src:
        cp = ord(ch)
        if cp < 0x80:
            out.append(ch)
        elif cp <= 0xFFFF:
            out.append(f"\\u{cp:04x}")
        else:
            out.append(f"\\U{cp:08x}")
    new = "".join(out)
    if new != src:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
        print(f"escaped {path}")
