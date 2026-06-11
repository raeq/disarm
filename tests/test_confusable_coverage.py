"""Coverage gate against the official Unicode UTS#39 confusables.

disarm's confusable table is generated from the pinned ``data/confusables.txt``.
This test asserts that every single-codepoint confusable whose official prototype
is a single basic Latin letter (A-Z / a-z) is actually neutralized by
``normalize_confusables(..., target_script="latin")``.

It guards against regressions and Unicode-version drift (see THREAT_MODEL.md:
"Unicode-version skew"). It does NOT assert coverage of confusables outside the
bundled data — those are documented out-of-scope.
"""

from __future__ import annotations

import pathlib

from disarm import normalize_confusables

CONFUSABLES = pathlib.Path(__file__).resolve().parent.parent / "data" / "confusables.txt"
_ASCII_LETTERS = set(range(0x41, 0x5B)) | set(range(0x61, 0x7B))


def _latin_letter_confusables() -> list[str]:
    """Source chars whose official prototype is a single basic ASCII letter."""
    # Fail hard, never skip: the pinned source is committed and required for the
    # gate to mean anything. Its absence is itself a regression to surface.
    assert CONFUSABLES.exists(), (
        f"pinned confusables source missing: {CONFUSABLES} — the coverage gate "
        f"cannot run without it"
    )
    out: list[str] = []
    for raw in CONFUSABLES.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 2:
            continue
        try:
            src = [int(x, 16) for x in parts[0].split()]
            tgt = [int(x, 16) for x in parts[1].split()]
        except ValueError:
            continue
        if len(src) == 1 and src[0] >= 0x80 and len(tgt) == 1 and tgt[0] in _ASCII_LETTERS:
            out.append(chr(src[0]))
    return out


def test_latin_letter_confusable_coverage() -> None:
    chars = _latin_letter_confusables()
    assert chars, "no Latin-letter confusables parsed — data file malformed?"
    misses = [c for c in chars if c in normalize_confusables(c, target_script="latin")]
    assert not misses, (
        f"{len(misses)} of {len(chars)} single-letter Latin confusables are not "
        f"neutralized: {[f'U+{ord(c):04X}' for c in misses]}"
    )
