"""#807 — `sort_key` emitted a key its own detector called anomalous.

It was the one key builder with neither `strip_zalgo` nor `strip_accents`, so nothing
bounded combining marks. `search_key` and `catalog_key` are clean only as a side effect —
`strip_accents` removes the marks — and that route is not available here, because keeping
diacritics is what a sort key is *for*: `café` and `cafe` must not collide.

    sort_key("a" + U+0301 * 40 + "b")  ->  41 chars, kinds=['zalgo']

Two properties were wrong at once. The output was flagged by `has_anomalies`, and its
**length was set by the attacker**: 1,000 marks in produced 1,001 characters out, under a
function whose output a caller stores and indexes.

Capping rather than stripping fixes both and keeps the ordering. The cap is
`DEFAULT_MAX_MARKS`, which since #788 equals `is_zalgo`'s threshold — so this removes
exactly what the library already calls abuse and nothing it calls ordinary. That is why
#788 had to land first (R23 in #762): with the old cap of 2, a three-mark Bengali cluster
or a pointed Hebrew consonant would have been truncated by a key builder.

The step sits **after** transliteration, which is why it moves no key in the 22,963-row
corpus: `sort_key` romanises non-Latin text before reaching it, so the marks are already
gone. What remains for it to bound is a Latin-script stack, which is exactly where the
amplification lives.
"""

from __future__ import annotations

import unicodedata

import pytest

import disarm

ACUTE = "́"


def marks(text: str) -> int:
    return sum(1 for char in unicodedata.normalize("NFD", text) if unicodedata.combining(char))


@pytest.mark.parametrize("count", [10, 40, 200, 1000], ids=lambda n: f"{n}-marks")
def test_the_output_length_is_not_the_attackers_to_set(count: int) -> None:
    """The amplification: output length tracked input mark count 1:1.

    The bound is derived from the capped case rather than written as a number. A literal
    would encode no reason and would break on an unrelated formatting change; this says
    what the property is — the same input at the cap produces the same length as the same
    input far above it.
    """
    # The cap itself is not exported, and naming it here would only move the literal.
    # The property is what matters: above the threshold, the output stops growing — so
    # this compares against the smallest input that is already over it.
    over_the_threshold = disarm.sort_key("a" + ACUTE * 4 + "b")
    key = disarm.sort_key("a" + ACUTE * count + "b")
    assert len(key) == len(over_the_threshold), (
        f"{count} marks produced {len(key)} characters; 4 marks produces {len(over_the_threshold)}"
    )


def test_the_length_is_constant_across_mark_counts() -> None:
    """Stated as a property rather than a bound, since that is the actual claim."""
    lengths = {len(disarm.sort_key("a" + ACUTE * n + "b")) for n in (5, 50, 500, 5000)}
    assert len(lengths) == 1, f"length still varies with the attacker's input: {lengths}"


@pytest.mark.parametrize("count", [10, 40, 200], ids=lambda n: f"{n}-marks")
def test_the_key_is_no_longer_flagged_by_the_library_itself(count: int) -> None:
    """A key builder under a stability contract should not emit anomalous output."""
    key = disarm.sort_key("a" + ACUTE * count + "b")
    report = disarm.inspect_anomalies(key)
    assert not report.anomalous, f"sort_key output still reports {report.kinds}"


# ── what a sort key exists to preserve ───────────────────────────────────────


@pytest.mark.parametrize(
    ("accented", "plain"),
    [("café", "cafe"), ("Müller", "Muller"), ("naïve", "naive"), ("Việt", "Viet")],
    ids=["french", "german", "diaeresis", "vietnamese"],
)
def test_diacritics_still_distinguish(accented: str, plain: str) -> None:
    """Copying `search_key`'s step list would have destroyed the ordering.

    `strip_accents` is why the other two builders are clean, and it is the one thing a
    sort key cannot do.
    """
    assert disarm.sort_key(accented) != disarm.sort_key(plain)


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("Hebrew, three marks", "אָׁ֑"),
        ("Arabic, three marks", "بَّْ"),
        # Genuinely decomposed: e + dot below + circumflex. Written as escapes because
        # the precomposed and decomposed spellings are indistinguishable on the page, and
        # an earlier version of this row was precomposed while claiming to be NFD.
        ("Vietnamese NFD", "e\u0323\u0302"),
        ("cafe", "café"),
    ],
    ids=["hebrew", "arabic", "vietnamese", "french"],
)
def test_ordinary_text_at_the_threshold_is_untouched(name: str, text: str) -> None:
    """The #788 dependency, asserted rather than assumed.

    With the old cap of 2 this step would have cut a mark from ordinary Hebrew and Arabic
    — a key builder truncating real orthography, which is worse than the amplification it
    was added to fix.
    """
    assert not disarm.is_zalgo(text), f"{name} must be ordinary for this to mean anything"
    before = disarm.sort_key(text)
    assert before == disarm.sort_key(before), f"{name} is not a fixed point"


def test_it_is_still_a_fixed_point() -> None:
    """Adding a step to a key builder must not break idempotence (#467)."""
    for text in ("café", "a" + ACUTE * 40 + "b", "Việt Nam", "ইয়াং"):
        once = disarm.sort_key(text)
        assert disarm.sort_key(once) == once, text
