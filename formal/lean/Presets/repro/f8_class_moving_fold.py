"""Finding 8: the fold moves a mark past `canonicalize`'s cap (#1072).

Model: `Findings.canon_gcedilla_once`, `canon_gcedilla_twice`, `canon_gcedilla_tr39`,
`canon_fixed_gcedilla`, `canon_moved_by_zalgo`.
"""

from __future__ import annotations

import functools

from common import show, w

import disarm

# g with cedilla, then three marks above: acute, diaeresis, tilde.
word = w(0x123, 0x301, 0x308, 0x303)

for name in ("canonicalize", "canonicalize_strict"):
    for pol in ("numeric", "tr39", "preserve"):
        f = functools.partial(getattr(disarm, name), digit_policy=pol)
        show(f"{name}[{pol}] g-cedilla + 3 above", word, f)
