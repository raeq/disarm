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
from conftest import UNNAMED_EMOJI

from disarm import TextPipeline, demojize, get_pipeline, ml_normalize, strip_obfuscation

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
    """Ten of #614's 54 rows are genuine emoji, so neither rule subsumes the other.

    49 until #801, which folded `\u222b` INTEGRAL to `s` — upstream maps it straight
    onto `\u0283` LATIN SMALL LETTER ESH, and closing the case asymmetry gave esh an
    ASCII representative. It is a CLDR-named non-emoji, so it lands in the intersection
    and not in the ten below.

    50 until #815, which gave the negative enclosed letters a fold. Four of them are
    dual-purpose: `\U0001f170` is both NEGATIVE SQUARED LATIN CAPITAL LETTER A and the
    blood-type A button. They are genuine emoji, so they join the six rather than the
    CLDR-named non-emoji, and they are the reason this count moved.
    """
    confusable = {
        int(line.split("\t")[0], 16)
        for line in (DATA / "confusables_to_latin.tsv").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }
    tr39_claimed = {cp for cp in ROWS if cp in confusable}
    assert len(tr39_claimed) == 54
    assert tr39_claimed - set(NON_EMOJI) == {
        0x203C,
        0x2049,
        0x2139,
        0x2795,
        0x2796,
        0x2797,
        # The dual-purpose buttons (#815): a letter shape and an emoji at once.
        0x1F170,
        0x1F171,
        0x1F17E,
        0x1F17F,
    }


# --- #990: the unknown-emoji branch asks the UCD, not a block range ----------

#: The candidate half of the block ranges `emoji::is_emoji_codepoint` matches. Until #990
#: those ranges decided the unknown-emoji branch of both `demojize` scanners, so anything
#: in them CLDR did not name was rewritten as an emoji the library lacked data for.
#: `U+2600..27BF` is Miscellaneous Symbols and Dingbats and `U+1FC00..1FFFF` is entirely
#: unassigned — neither has ever been emoji.
#:
#: Two of the predicate's six ranges are deliberately absent, because a character in them
#: is not a candidate for this question: `U+FE00..FE0F` are the variation selectors, which
#: `demojize` strips by design before this branch is reached, and `U+E0020..E007F` is the
#: Plane 14 TAG block, which it removes by design and which `ml_normalize` relies on it to
#: remove (#914). Sweeping either would assert the opposite of what those two want.
EMOJI_BLOCK_RANGES = (
    (0x2600, 0x27BF),
    (0x2B50, 0x2B55),
    (0x1F000, 0x1FAFF),
    (0x1FC00, 0x1FFFF),
)


def test_a_block_range_neighbour_with_no_emoji_property_is_left_alone() -> None:
    """`demojize` replaced `☆` with `[?]`, and the pipeline deleted it (#990).

    Derived from the shipped tables rather than a fixed list, like the rest of this
    module: every code point in the old block ranges that carries no emoji property
    and that CLDR does not name must survive `demojize` untouched. On the pre-#990
    build 777 of them did not.
    """
    ranges = _property_ranges()
    casualties = [
        cp
        for lo, hi in EMOJI_BLOCK_RANGES
        for cp in range(lo, hi + 1)
        if not _has_emoji_property(cp, ranges)
        and cp not in ROWS
        and demojize(f"a{chr(cp)}b") != f"a{chr(cp)}b"
    ]
    assert casualties == [], (
        f"{len(casualties)} non-emoji characters are still rewritten by demojize, "
        f"first five: {[f'U+{c:04X}' for c in casualties[:5]]}"
    )


@pytest.mark.parametrize(
    ("ch", "what"),
    [
        ("☆", "WHITE STAR — no emoji property at all"),
        ("☓", "SALTIRE — no emoji property at all"),
        ("★", "BLACK STAR — Extended_Pictographic, but text presentation"),
    ],
)
def test_no_route_rewrites_a_text_presentation_symbol(ch: str, what: str) -> None:
    """Standalone marked it `[?]`; the pipeline deleted it outright.

    Silent deletion is the worse of the two and it is the one a shipped profile
    reached, through `ml_corpus_normalize`.
    """
    assert demojize(f"rated 3 {ch} of 5") == f"rated 3 {ch} of 5", what
    assert TextPipeline(demojize=True)(f"a{ch}b") == f"a{ch}b", what
    assert get_pipeline("ml_corpus_normalize")(f"a{ch}b") == f"a{ch}b", what


def _presentation_ranges() -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for line in (DATA / "emoji_presentation.tsv").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        lo, hi = line.split("\t")[:2]
        out.append((int(lo, 16), int(hi, 16)))
    return out


@pytest.mark.parametrize(
    ("ch", "what"),
    [
        ("\u00a9", "COPYRIGHT SIGN — Emoji=Yes, text by default"),
        ("\u00ae", "REGISTERED SIGN — Emoji=Yes, text by default"),
        ("\u2388", "HELM SYMBOL — Extended_Pictographic, text by default"),
        ("\u2605", "BLACK STAR — Extended_Pictographic, no emoji presentation"),
        ("\U0001fc00", "unassigned, Extended_Pictographic by reservation"),
    ],
)
def test_a_presentation_selector_does_not_make_an_unnamed_symbol_an_emoji(
    ch: str, what: str
) -> None:
    """`U+FE0F` after a text-default symbol CLDR cannot name kept #990 alive.

    #990 stopped `★` alone reaching the unknown-emoji branch, and `★\ufe0f` still
    did: the branch accepted any base in `emoji_property.tsv` carrying the selector,
    and that table is `Emoji` OR `Extended_Pictographic`. So `a©\ufe0fb` became
    `a[?] b` standalone and `ab` in the pipeline, and `ml_normalize("Acme®\ufe0f")`
    lost the sign — both of which kept it before #990. The selector asks for emoji
    presentation; it does not supply a name, and an unnamed symbol is kept with the
    selector dropped, as it was.
    """
    assert demojize(f"a{ch}\ufe0fb") == f"a{ch}b", what
    assert TextPipeline(demojize=True)(f"a{ch}\ufe0fb") == f"a{ch}b", what
    assert get_pipeline("ml_corpus_normalize")(f"a{ch}\ufe0fb") == f"a{ch}b", what
    assert ml_normalize(f"Acme{ch}\ufe0f") == f"acme{ch}", what


def test_a_named_emoji_joined_to_an_unnamed_head_keeps_its_name() -> None:
    """The unnamed head took the whole ZWJ chain, `🔥` included."""
    out = demojize("a\u00a9\ufe0f\u200d\U0001f525b")
    assert "\u00a9" in out and "fire" in out and "[?]" not in out, out


def test_no_text_default_symbol_is_lost_to_its_selector() -> None:
    """Every base the old predicate let in, derived from the tables.

    Every code point in `emoji_property.tsv` that is not `Emoji_Presentation` and
    that CLDR does not name, followed by `U+FE0F`, must come back as itself. On the
    #990 build 2,141 did not; keycap bases are excluded because `1\ufe0f` never
    opened a sequence.
    """
    presentation = _presentation_ranges()
    casualties = [
        cp
        for lo, hi in RANGES
        for cp in range(lo, hi + 1)
        if not _has_emoji_property(cp, presentation)
        and cp not in ROWS
        and chr(cp) not in "0123456789#*"
        and demojize(f"a{chr(cp)}\ufe0fb") != f"a{chr(cp)}b"
    ]
    assert casualties == [], (
        f"{len(casualties)} text-default symbols are lost to U+FE0F, "
        f"first five: {[f'U+{c:04X}' for c in casualties[:5]]}"
    )


def test_the_branch_still_fires_for_an_emoji_cldr_does_not_name() -> None:
    """Narrowed, not disabled.

    A lone regional indicator is `Emoji_Presentation=Yes` and CLDR names no single
    one — a flag needs the pair — so it is exactly the shape `errors` exists for.
    """
    from disarm import TextPipeline

    lone = f"x{UNNAMED_EMOJI}y"
    assert demojize(lone, errors="replace", replace_with="[?]") == "x[?] y"
    assert demojize(lone, errors="ignore") == "xy"
    assert demojize(lone, errors="preserve") == "x\U0001f1e6 y"
    # The pipeline has no `errors` knob and drops what it cannot name, as it always
    # has. #990 narrowed what reaches this branch, not what happens in it.
    assert TextPipeline(demojize=True)(lone) == "xy"
