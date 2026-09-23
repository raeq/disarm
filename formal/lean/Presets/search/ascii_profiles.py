#!/usr/bin/env python3
"""`docs/api/pipelines.md` lists four profiles whose output is "ASCII". Count, over every
scalar in planes 0-3 and 14, the inputs each one maps to a non-ASCII string."""

from __future__ import annotations

import disarm

for name in ("library_catalog_key_eu", "ml_corpus_normalize", "search_index", "rag_ingest"):
    f = disarm.get_pipeline(name)
    bad = []
    for cp in list(range(0, 0x40000)) + list(range(0xE0000, 0xE1000)):
        if 0xD800 <= cp < 0xE000:
            continue
        out = f(chr(cp))
        if not out.isascii():
            bad.append((cp, out))
    print(
        f"{name:<24} non-ASCII outputs: {len(bad):>7}  e.g. {[(hex(c), ascii(o)) for c, o in bad[:3]]}"
    )
