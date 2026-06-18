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
import unicodedata

from disarm import normalize_confusables

CONFUSABLES = pathlib.Path(__file__).resolve().parent.parent / "data" / "confusables.txt"
GENERATED = pathlib.Path(__file__).resolve().parent.parent / "src" / "tables" / "data"
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


def test_no_digit_source_folds_to_a_letter() -> None:
    """#439: a digit-category (``Nd``) source must never fold to a non-digit.

    A digit spoof (Arabic-Indic ٠, Devanagari ०, the outlined digits 𜳰/𜳱, …) must
    canonicalize to its plain ASCII digit, not a look-alike letter (𜳰→O / ٠→o was
    the bug). Checks the generated maps directly. Best-effort per the running
    Unicode version — a source assigned only in a newer Unicode is unknown to an
    older ``unicodedata`` and simply isn't classified as ``Nd`` here; the
    generator's own version guard ensures the committed maps were built correctly.
    """
    offenders: list[str] = []
    for name in ("confusables_to_latin.tsv", "confusables_to_cyrillic.tsv"):
        for raw in (GENERATED / name).read_text(encoding="utf-8").splitlines():
            if "\t" not in raw or raw.startswith("#"):
                continue
            src, tgt = raw.split("\t", 1)
            try:
                ch = chr(int(src, 16))
            except ValueError:
                continue
            if unicodedata.category(ch) != "Nd":
                continue
            if not (len(tgt) == 1 and tgt.isascii() and tgt.isdigit()):
                offenders.append(f"{src}({unicodedata.name(ch, '?')})→{tgt!r}")
    assert not offenders, f"digit sources folding to a non-digit: {offenders}"
