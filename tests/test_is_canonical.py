"""#730 — a verification-path predicate, because `has_anomalies` is not one.

Every normalization surface in disarm is generation path: text in, normalized text out.
There was no counterpart answering *"is this string already its own canonical form?"*, and
the detector that looks like one is a strict under-approximation of it.

Measured over every assigned code point (excluding `Cn`/`Cs`), UCD 16.0.0:

| | count |
|---|---|
| `has_anomalies(x) is False` **and** `canonicalize(x) != x` | **142,760** (5,292 excluding PUA) |
| `has_anomalies(x) is True` **and** `canonicalize(x) == x` | **0** |

One-way. A caller writing the obvious accept gate — reject if `has_anomalies`, else take
the bytes as given — admits 5,292 non-PUA code points that are not their own canonical
form, `ｐａｙｐａｌ` and `ｅｘａｍｐｌｅ.ｃｏｍ` among them.

`is_canonical` is the predicate for that gate. It is **not** a change to the detector:
making `has_anomalies` fire on fullwidth would reopen #633 and #907, since `ＮＨＫ` is
ordinary text. Two questions, two answers.

The caller could already write `canonicalize(text) != text`, and that is correct. This
exists because it is not discoverable among 190 names, because it allocates and returns a
full copy across the FFI boundary to answer a boolean, and because the `Guard::Inert` fast
path can answer the common case without running the pipeline at all.

The exact census above is a measurement at one UCD version, so it is not asserted as a
number — CI's interpreter knows a different set of assigned code points. What *is* asserted
is the direction, which no UCD version may change.
"""

from __future__ import annotations

import unicodedata as ud

import pytest

import disarm

#: Clean under `has_anomalies` and not canonical — the gap the predicate closes.
#: Each row was measured, not assumed: `Ⅻ` and `ﬁle` look like they belong here and do
#: not, because the `compat_fold` branch already fires on them.
CLEAN_BUT_NOT_CANONICAL = [
    "ＡＢＣ",
    "ｐａｙｐａｌ",
    "ＮＨＫ",
    "ｅｘａｍｐｌｅ.ｃｏｍ",
    'a"b',
    "µF",
    "㈱",
    "℠",
    "㎏",
]

#: Canonical under `canonicalize`, so the predicate must say so.
ALREADY_CANONICAL = ["abc", "hello world", "paypal.com", "", "123"]


@pytest.mark.parametrize("text", ALREADY_CANONICAL)
def test_canonical_text_is_reported_canonical(text: str) -> None:
    assert disarm.is_canonical(text) is True


@pytest.mark.parametrize("text", CLEAN_BUT_NOT_CANONICAL)
def test_non_canonical_text_is_reported_non_canonical(text: str) -> None:
    assert disarm.is_canonical(text) is False


@pytest.mark.parametrize("text", CLEAN_BUT_NOT_CANONICAL)
def test_these_are_exactly_the_rows_the_detector_calls_clean(text: str) -> None:
    """Both halves. The predicate is only interesting where the detector is silent."""
    assert disarm.has_anomalies(text) is False, "row no longer demonstrates the gap"
    assert disarm.canonicalize(text) != text


#: The classes the docstrings and `docs/api/predicates.md` name as living in the gap.
#: Named in prose, so gated here. `Ⅻ`, `ﬁ`, `①` and `𝐀` all look like they belong and do
#: not, because the detector's `compat_fold` branch already fires on them.
NAMED_GAP_CLASSES = {
    "CJK compatibility ideograph": "\uf900",
    "Arabic presentation form": "\ufef5",
    "Kangxi radical": "\u2f00",
    "fullwidth": "\uff21",
    "halfwidth": "\uff71",
}


@pytest.mark.parametrize(("label", "ch"), NAMED_GAP_CLASSES.items())
def test_the_classes_the_docs_name_are_in_the_gap(label: str, ch: str) -> None:
    assert disarm.has_anomalies(ch) is False, f"{label} now fires the detector"
    assert disarm.is_canonical(ch) is False, f"{label} is now canonical"


def test_it_agrees_with_the_expression_it_replaces() -> None:
    """`is_canonical(x)` must equal `canonicalize(x) == x` — that is the definition."""
    for text in CLEAN_BUT_NOT_CANONICAL + ALREADY_CANONICAL + ["Ｈello", "Ⅻ", "ﬁle"]:
        assert disarm.is_canonical(text) == (disarm.canonicalize(text) == text), text


def test_the_definition_holds_across_the_whole_codespace() -> None:
    """The predicate is a pure restatement of the preset, for every code point."""
    for cp in range(0x110000):
        ch = chr(cp)
        if ud.category(ch) in ("Cn", "Cs"):
            continue
        assert disarm.is_canonical(ch) == (disarm.canonicalize(ch) == ch), f"U+{cp:04X}"


def test_the_detector_never_fires_on_canonical_text() -> None:
    """The one-way direction, over the full codespace.

    A row that is flagged AND already canonical would be the detector reporting something
    the canonicalizer would not change — a false positive by construction, and the failure
    mode #907 was filed about. Zero of them today.

    Asserted as a direction, not a census: CI's interpreter carries a different UCD
    version, so the exact gap count moves while this must not.
    """
    offenders = [
        f"U+{cp:04X}"
        for cp in range(0x110000)
        if ud.category(chr(cp)) not in ("Cn", "Cs")
        and disarm.has_anomalies(chr(cp))
        and disarm.is_canonical(chr(cp))
    ]
    assert offenders == [], f"flagged but already canonical: {offenders[:20]}"


def test_the_gap_is_large_enough_to_be_worth_a_predicate() -> None:
    """The premise of #730: the two questions differ on a substantial population.

    A floor, not the census — if this ever fell to zero, `has_anomalies` would have become
    a canonicity predicate and this function would be redundant.
    """
    gap = sum(
        1
        for cp in range(0x110000)
        if ud.category(chr(cp)) not in ("Cn", "Cs", "Co")
        and not disarm.has_anomalies(chr(cp))
        and not disarm.is_canonical(chr(cp))
    )
    assert gap > 4000, f"only {gap} non-PUA code points separate the two questions"


#: The 0.11 renames. `PRESETS` still documents them as valid keys, so `preset=` must
#: take them — but calling the Python aliases emits `DeprecationWarning`, so the target
#: is named here rather than resolved through `getattr`.
DEPRECATED_ALIASES = {
    "security_clean": "canonicalize",
    "display_clean": "strip_format",
    "normalize_user_input": "canonicalize_strict",
}

#: Everything in `PRESETS` that is not an alias.
PRIMARY_PRESETS = sorted(set(disarm.PRESETS) - set(DEPRECATED_ALIASES))


def test_the_primary_preset_list_here_matches_the_registry() -> None:
    """Anchored on `PRESETS`, so a new preset joins the sweep below without an edit."""
    assert set(PRIMARY_PRESETS) | set(DEPRECATED_ALIASES) == set(disarm.PRESETS)


@pytest.mark.parametrize("preset", PRIMARY_PRESETS)
def test_every_preset_is_addressable(preset: str) -> None:
    """#730 §1: the predicate answers for the preset registry, not just one function."""
    fn = getattr(disarm, preset)
    for text in ("abc", "ＡＢＣ", "Ⅻ", "hello world"):
        assert disarm.is_canonical(text, preset=preset) == (fn(text) == text), (preset, text)


@pytest.mark.parametrize(("alias", "target"), DEPRECATED_ALIASES.items())
def test_the_deprecated_aliases_are_still_accepted(alias: str, target: str) -> None:
    """`PRESETS` documents them, so the string dispatch has to take them.

    Before this test they fell through to the profile lookup and raised
    `UnknownProfile`, which made the registry claim in the docstring false. The name is
    a lookup key, not a call to the deprecated function, so no warning is expected.
    """
    for text in ("abc", "ＡＢＣ", "café", "Ⅻ"):
        assert disarm.is_canonical(text, preset=alias) == disarm.is_canonical(
            text, preset=target
        ), (alias, text)


def test_a_profile_is_addressable_too() -> None:
    for profile in disarm.list_profiles():
        pipeline = disarm.get_pipeline(profile)
        for text in ("abc", "ＡＢＣ"):
            assert disarm.is_canonical(text, preset=profile) == (pipeline(text) == text), profile


def test_an_unknown_preset_is_rejected() -> None:
    with pytest.raises(disarm.DisarmError) as excinfo:
        disarm.is_canonical("abc", preset="not_a_preset")
    assert "not_a_preset" in str(excinfo.value)


def test_the_detector_docstrings_disclaim_canonicity() -> None:
    """#730 §4: a clean result is not a claim of canonicity, and must say so."""
    for fn in (disarm.has_anomalies, disarm.inspect_anomalies):
        doc = fn.__doc__ or ""
        assert "is_canonical" in doc, f"{fn.__name__} does not point at the accept gate"
