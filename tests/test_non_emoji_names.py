"""#757 — the CLDR name table only fires for code points that are actually emoji.

CLDR ``annotationsDerived`` names characters that carry no Unicode emoji property:
typographic punctuation, currency, math operators, brackets. Standalone ``demojize``
naming them is the point of that function. A *preset* naming them inserts words that
were in neither the input nor any emoji, which is the mechanism
``docs/security/adversarial-defense.md`` disqualifies ``unidecode`` for.

The classification is recomputed here from the two shipped TSVs rather than copied
from a list, so the test tracks a table refresh instead of going stale against one.
``build.rs`` asserts the same set's size at compile time; this asserts what the set
*does*.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from disarm import demojize, ml_normalize, strip_obfuscation

DATA = Path(__file__).resolve().parent.parent / "src" / "tables" / "data"

# The number build.rs asserts. Duplicated deliberately: if only one of the two moves,
# the data and the gate have diverged.
EXPECTED_NON_EMOJI_ROWS = 326


def _rows() -> dict[int, str]:
    out: dict[int, str] = {}
    for line in (DATA / "emoji_single.tsv").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        cp, name = line.split("\t")
        out[int(cp, 16)] = name
    return out


def _property_ranges() -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for line in (DATA / "emoji_property.tsv").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        lo, hi = line.split("\t")[:2]
        out.append((int(lo, 16), int(hi, 16)))
    return out


def _has_emoji_property(cp: int, ranges: list[tuple[int, int]]) -> bool:
    return any(lo <= cp <= hi for lo, hi in ranges)


ROWS = _rows()
RANGES = _property_ranges()
NON_EMOJI = sorted(cp for cp in ROWS if not _has_emoji_property(cp, RANGES))
IS_EMOJI = sorted(cp for cp in ROWS if _has_emoji_property(cp, RANGES))


def test_the_reviewed_set_has_not_moved() -> None:
    """A CLDR refresh that annotates more punctuation must be reviewed, not absorbed."""
    assert len(NON_EMOJI) == EXPECTED_NON_EMOJI_ROWS, (
        f"emoji_single.tsv rows with no emoji property: expected "
        f"{EXPECTED_NON_EMOJI_ROWS}, found {len(NON_EMOJI)}. A new row means a preset "
        f"now passes through a character it used to name. Review it, then update this "
        f"count and the one in build.rs."
    )


def test_the_property_table_is_pinned_to_a_ucd_release() -> None:
    """Not a floating download: the header names the release the set was derived from."""
    header = (DATA / "emoji_property.tsv").read_text(encoding="utf-8").splitlines()[0]
    assert re.search(r"UCD \d+\.\d+\.\d+", header), header


@pytest.mark.parametrize("cp", NON_EMOJI, ids=lambda c: f"U+{c:04X}")
def test_presets_never_emit_a_non_emoji_row_name(cp: int) -> None:
    """No preset may put the CLDR name of a non-emoji code point into its output.

    Checked against the *name*, not against the input: NFKC runs first, so `‼` legally
    becomes `!!` and `½` becomes `1⁄2`. What must never appear is the English phrase.
    """
    ch, name = chr(cp), ROWS[cp]
    # Single-word names like "euro" or "bullet" can occur inside an unrelated token, so
    # the assertion is on the name as a standalone word run.
    pattern = re.compile(rf"(?<![\w]){re.escape(name)}(?![\w])")
    for preset in (lambda s: ml_normalize(s), strip_obfuscation):
        got = preset(ch)
        assert not pattern.search(got), f"{preset} named U+{cp:04X} {ch!r} as {name!r}: {got!r}"


def test_demojize_still_names_every_row() -> None:
    """#614 settled that the rows are not wrong, only which table wins inside a bundle."""
    named = [cp for cp in NON_EMOJI if ROWS[cp] in demojize(chr(cp))]
    assert len(named) == len(NON_EMOJI), (
        f"demojize stopped naming {len(NON_EMOJI) - len(named)} non-emoji rows; the "
        f"suppression is supposed to be preset-only"
    )


def test_real_emoji_are_still_named_by_the_presets() -> None:
    """The gate must not have swallowed the feature it guards.

    Restricted to rows NFKC leaves alone — `‼` U+203C is a real emoji whose NFKC form
    is `!!`, and the name never gets the chance to fire.
    """
    import unicodedata

    def folded(s: str) -> str:
        """`ml_normalize` also strips accents, so `piñata` is named as `pinata`."""
        d = unicodedata.normalize("NFD", s)
        return "".join(c for c in d if not unicodedata.combining(c)).casefold()

    stable = [cp for cp in IS_EMOJI if unicodedata.normalize("NFKC", chr(cp)) == chr(cp)]
    assert len(stable) > 1_000, f"only {len(stable)} NFKC-stable emoji rows to check"
    missed = [
        f"U+{cp:04X} {ROWS[cp]!r} -> {ml_normalize(chr(cp))!r}"
        for cp in stable
        if folded(ROWS[cp].split(":")[0]) not in ml_normalize(chr(cp))
    ]
    assert not missed, f"{len(missed)} emoji rows stopped being named, e.g. {missed[:5]}"


def test_body_text_gains_no_words() -> None:
    """The #757 headline: 30 words in, 30 words out.

    Every non-ASCII character here is ordinary typographic punctuation an editor or a
    word processor inserts on its own.
    """
    sentence = (
        "The film’s result is a powerful, naturally dramatic piece — "
        "low-budget filmmaking at its best. “A triumph,” she said; "
        "tickets cost €12–15, and it earned ½ of its budget back."
    )
    assert len(sentence.split()) == 30
    assert len(ml_normalize(sentence).split()) == 30
    assert "right apostrophe" not in ml_normalize(sentence)
    assert "film’s" in ml_normalize(sentence)


def test_a_named_row_does_not_fuse_with_its_neighbour() -> None:
    """`a†b` produced `a dagger signb` — a word in neither the input nor the name."""
    assert strip_obfuscation("a†b") == "a†b"
    assert ml_normalize("a†b") == "a†b"


def test_614_precedence_is_unchanged() -> None:
    """The confusable fold still wins inside the comparison preset (CVE-2017-5383)."""
    assert strip_obfuscation("€xample.com") == "example.com"
    assert strip_obfuscation("‘quote’") == "'quote'"


def test_the_two_suppression_sets_are_not_the_same_set() -> None:
    """Six of #614's 49 rows are genuine emoji, so neither rule subsumes the other."""
    confusable = {
        int(line.split("\t")[0], 16)
        for line in (DATA / "confusables_to_latin.tsv").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }
    tr39_claimed = {cp for cp in ROWS if cp in confusable}
    assert len(tr39_claimed) == 49
    assert tr39_claimed - set(NON_EMOJI) == {
        0x203C,
        0x2049,
        0x2139,
        0x2795,
        0x2796,
        0x2797,
    }
