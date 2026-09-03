"""#650 — the TR39 prototype classes disarm's table deliberately keeps apart.

TR39 puts `I`, `l` and `1` in one equivalence class and `O`/`0` in another. disarm's
table stops short of both: every member of the capital-I family folds to `I` and stops
there, so `paypaI` survives every shipped surface intact.

`skeleton_key` closes it, as a separate builder rather than a flag, for one measured
reason. Over the 235,976 entries of `/usr/share/dict/words`:

| the class applied | new collision groups |
|---|---|
| before case folding (`I ≡ l`) | **6** |
| after case folding (`i ≡ l`) | **264** |

A factor of 44. The six are `i`/`l`, `ian`/`lan`, `io`/`lo`, `ione`/`lone`, `iowa`/`lowa`,
`iowan`/`lowan` — five proper nouns and one ordinary merge. The 264 are ordinary
vocabulary: `boiling`/`bolling`, `doit`/`dolt`, `ail`/`all`.

No existing key builder offers the earlier position. `catalog_key` folds case at step 3
and reaches its confusable step at step 6, and the two cannot be swapped —
fold-before-transliterate is required for idempotency (#419).
"""

from __future__ import annotations

import pytest

import disarm

#: Builders that existed before this one. None of them can reach the class.
EXISTING_KEY_BUILDERS = [disarm.catalog_key, disarm.search_key, disarm.sort_key]


def test_the_class_the_other_builders_cannot_reach() -> None:
    """Both halves: this one collides them and the pre-existing three do not."""
    assert disarm.skeleton_key("paypaI") == disarm.skeleton_key("paypal")
    for builder in EXISTING_KEY_BUILDERS:
        assert builder("paypaI") != builder("paypal"), builder.__name__


@pytest.mark.parametrize(
    ("cp", "name"),
    [
        (0xFF29, "FULLWIDTH CAPITAL I"),
        (0x1D4D8, "MATHEMATICAL BOLD SCRIPT CAPITAL I"),
        (0x0406, "CYRILLIC CAPITAL BYELORUSSIAN-UKRAINIAN I"),
        (0x0399, "GREEK CAPITAL IOTA"),
        (0x13A5, "CHEROKEE LETTER V"),
    ],
)
def test_the_whole_capital_i_family_reaches_the_prototype(cp: int, name: str) -> None:
    """The table brings each to `I`; this step takes `I` the last step to `l`."""
    assert disarm.normalize_confusables(chr(cp)) == "I", f"{name} no longer folds to I"
    assert disarm.skeleton_key(f"paypa{chr(cp)}") == "paypal", name


def test_it_runs_before_the_case_fold_and_this_is_how_you_can_tell() -> None:
    """The step-order argument, as a behavioural assertion rather than a comment.

    `Ione`/`lone` is one of the six merges the class costs at this position.
    `boiling`/`bolling` is one of the 264 it would cost one step later, when `I ≡ l` has
    become `i ≡ l`. If the prototype fold ever moves after `Step::FoldCase`, the second
    assertion fails — which is the whole cost argument for a separate builder.
    """
    assert disarm.skeleton_key("Ione") == disarm.skeleton_key("lone"), "the intended merge"
    assert disarm.skeleton_key("boiling") != disarm.skeleton_key("bolling"), (
        "the prototype fold has moved after the case fold — that is the 264-collision "
        "version of this class, and the reason this builder exists"
    )
    assert disarm.skeleton_key("doit") != disarm.skeleton_key("dolt")
    assert disarm.skeleton_key("ail") != disarm.skeleton_key("all")


def test_lowercase_o_is_not_in_the_o_class() -> None:
    """Same argument on the other class: `O ≡ 0`, never `o ≡ 0` pre-fold."""
    assert disarm.skeleton_key("book") == "book"
    assert disarm.skeleton_key("b0ok", digit_policy="tr39") == "book"


class TestTheDigitHalfIsOptIn:
    """#650: the letter half is nearly free, the digit half destroys identifier fields."""

    IDENTIFIER_GROUPS = [
        ["SKU-100", "SKU-1O0", "SKU-IOO", "SKU-l00"],
        ["B01", "BOI", "BOl", "B0I"],
        ["v1.0.1", "vI.O.I", "vl.o.l"],
        ["Flat 10", "Flat IO", "Flat lO"],
    ]

    @pytest.mark.parametrize("policy", ["numeric", "preserve"])
    def test_digits_stay_apart_by_default(self, policy: str) -> None:
        for group in self.IDENTIFIER_GROUPS:
            keys = {disarm.skeleton_key(s, digit_policy=policy) for s in group}
            assert len(keys) > 1, f"{policy} collapsed {group}"

    def test_tr39_collapses_them_completely_which_is_the_point_and_the_cost(self) -> None:
        """Asserted, not warned about: this is what the caller opts into."""
        for group in self.IDENTIFIER_GROUPS:
            keys = {disarm.skeleton_key(s, digit_policy="tr39") for s in group}
            assert len(keys) == 1, f"tr39 did not collapse {group}: {keys}"

    def test_the_letter_half_applies_under_every_policy(self) -> None:
        for policy in ["numeric", "tr39", "preserve"]:
            assert disarm.skeleton_key("paypaI", digit_policy=policy) == "paypal", policy


def test_cross_script_spoofs_collide() -> None:
    """The ordinary confusable job still happens; this builder only adds to it."""
    for spoof in ("раураӏ", "pаypаl", "ｐａｙｐａｌ"):
        assert disarm.skeleton_key(spoof) == "paypal", spoof


def test_the_invisible_channels_cannot_vary_the_key() -> None:
    """A key exists so two spellings of one identity compare equal (#805)."""
    # Escapes, never literals: a literal invisible in a source file is unreviewable,
    # and a literal bidi control reorders the diff around it (#802).
    for hidden in ("\u200b", "\ufeff", "\u202e", "\U000e0041", "\ufffe", "\U000f0000"):
        assert disarm.skeleton_key(f"pay{hidden}pal") == "paypal", repr(hidden)


@pytest.mark.parametrize("policy", ["numeric", "tr39", "preserve"])
def test_it_is_idempotent(policy: str) -> None:
    """Including base+mark pairs — a single-code-point sweep misses those (#835)."""
    probes = [
        "paypaI",
        "SKU-1O0",
        "раураӏ",
        "Ｉ",
        "á",
        "é́",
        "İ",  # LATIN CAPITAL I WITH DOT ABOVE — decomposes under NFKC
        "İ",
        "Ω",
        "",
    ]
    for probe in probes:
        once = disarm.skeleton_key(probe, digit_policy=policy)
        assert disarm.skeleton_key(once, digit_policy=policy) == once, repr(probe)


def test_an_unknown_digit_policy_is_rejected() -> None:
    with pytest.raises(disarm.DisarmError) as excinfo:
        disarm.skeleton_key("x", digit_policy="nope")
    assert "nope" in str(excinfo.value)


def test_it_is_not_for_display() -> None:
    """More destructive than any preset that forwards text, by design.

    The same split `canonicalize` and `canonicalize_strict` already make: the more
    aggressive rule lives in the entry point whose contract says so.
    """
    assert disarm.canonicalize("paypaI") == "paypaI", "canonicalize preserves it"
    assert disarm.skeleton_key("paypaI") == "paypal", "the key does not"


def test_the_empty_key_problem_is_not_made_worse() -> None:
    """#728's territory: this builder must not add a new way to reach `""`."""
    assert disarm.skeleton_key("") == ""
    assert disarm.skeleton_key("paypaI") != ""
    assert disarm.skeleton_key("100", digit_policy="tr39") != ""
