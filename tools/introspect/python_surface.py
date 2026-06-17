#!/usr/bin/env python3
"""Emit disarm's LIVE Python public surface as a JSON array of operation names.

Reality, not source-scraping: import the built/installed package and read what it
actually exposes. The parity checker (scripts/parity_check.py) diffs this against
the manifest. Run after `maturin develop` (or against an installed wheel):

    python tools/introspect/python_surface.py > surfaces/python.json

Op granularity = lowercase public callables in ``__all__`` (classes like
``Lexicon``/``Text`` and constants are excluded, matching the manifest's ops).
"""

from __future__ import annotations

import json

import disarm

names = sorted(
    n
    for n in getattr(disarm, "__all__", [])
    if n[:1].islower() and n != "__version__" and callable(getattr(disarm, n, None))
)
print(json.dumps(names))
