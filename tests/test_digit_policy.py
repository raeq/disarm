"""#561 — selectable digit-mapping policy: prose numerals vs the TR39 skeleton.

disarm maps non-Latin digits to the ASCII digit. TR39 maps several of them to a Latin
*letter* — Devanagari zero to ``o``, Kannada zero to ``O``, Arabic-Indic one to ``l``.

Neither is wrong. disarm's reading is right for prose: a Devanagari zero in running text
is a zero, and turning it into a letter corrupts the number. TR39's is right for
identifier comparison, which is what the skeleton transform was built for — the skeleton
only has to make two confusable identifiers collide, and it does not care whether the
collision target reads sensibly.

The problem was that the divergence was fixed in the table with no way to select the other
behaviour, so it read as a defect to anyone scoring disarm against a TR39-derived
benchmark, and it cost points silently. This adds the selector.
"""

from __future__ import annotations

import pytest

import disarm

#: Rows the issue names explicitly, with disarm's numeric target and TR39's letter.
#: Derived from the tables, not transcribed — see ``test_the_override_set_is_generated``.
NAMED_IN_THE_ISSUE = [
    pytest.param("०", "0", "o", id="devanagari-zero"),
    pytest.param("০", "0", "o", id="bengali-zero"),
    pytest.param("೦", "0", "O", id="kannada-zero"),
    pytest.param("០", "0", "o", id="khmer-zero"),
]

#: The issue only lists zeros. The divergence is wider than that, which is worth pinning
#: because a reader who assumes "this is about zero" will under-test their own change.
BEYOND_ZERO = [
    pytest.param("١", "1", "l", id="arabic-indic-one"),
    pytest.param("٥", "5", "o", id="arabic-indic-five"),
    pytest.param("٧", "7", "V", id="arabic-indic-seven"),
    pytest.param("۱", "1", "l", id="ext-arabic-indic-one"),
]

ALL_DIVERGENT = NAMED_IN_THE_ISSUE + BEYOND_ZERO


# ── the default does not move ────────────────────────────────────────────────


@pytest.mark.parametrize(("source", "numeric", "_tr39"), ALL_DIVERGENT)
def test_default_is_numeric(source: str, numeric: str, _tr39: str) -> None:
    """No behaviour change for existing callers — the whole point of defaulting."""
    assert disarm.normalize_confusables(source) == numeric
    assert disarm.normalize_confusables(source, digit_policy="numeric") == numeric


def test_prose_numbers_survive_the_default() -> None:
    """Why numeric is the right default: the alternative corrupts running text.

    Arabic-Indic 5 and 0. The numeric policy reads them as the number 50; TR39 folds them
    to ``o.``, which is a perfectly good *skeleton* and complete nonsense as a quantity.

    Note only the digits TR39 actually lists as confusable are in the table at all —
    Devanagari has rows for zero and three but not for one or two — so a whole-numeral
    example has to be chosen from a script whose digits are covered, not assumed.
    """
    assert disarm.normalize_confusables("\u0665\u0660") == "50"
    assert disarm.normalize_confusables("\u0665\u0660", digit_policy="tr39") == "o."


# ── the tr39 policy ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(("source", "_numeric", "tr39"), ALL_DIVERGENT)
def test_tr39_policy_uses_the_upstream_target(source: str, _numeric: str, tr39: str) -> None:
    assert disarm.normalize_confusables(source, digit_policy="tr39") == tr39


def test_tr39_policy_makes_a_skeleton_collision_work() -> None:
    """The reason the policy exists.

    Under TR39's skeleton, a Devanagari zero and a Latin ``o`` collide — that is what lets
    two confusable identifiers compare equal. Under the numeric policy they do not, which
    is correct for prose and wrong for a skeleton benchmark.
    """
    spoofed = "g००gle"  # 'g' + two Devanagari zeros + 'gle'
    assert disarm.normalize_confusables(spoofed, digit_policy="tr39") == "google"
    assert disarm.normalize_confusables(spoofed) == "g00gle"


def test_policy_only_touches_the_divergent_rows() -> None:
    """Everything that is not a digit-policy row must map identically under both."""
    for text in ("pаypal", "Неllo Wоrld", "hello", "café", ""):
        assert disarm.normalize_confusables(text) == disarm.normalize_confusables(
            text, digit_policy="tr39"
        )


def test_ascii_digits_are_never_rewritten() -> None:
    """ASCII digits are the target, not a source — neither policy may touch them."""
    for policy in ("numeric", "tr39"):
        assert disarm.normalize_confusables("0123456789", digit_policy=policy) == "0123456789"


# ── contract ─────────────────────────────────────────────────────────────────


def test_unknown_policy_raises() -> None:
    with pytest.raises(disarm.InvalidArgumentError):
        disarm.normalize_confusables("x", digit_policy="skeleton")


@pytest.mark.parametrize("policy", ["numeric", "tr39"])
def test_idempotent_under_both_policies(policy: str) -> None:
    """A policy that is not a fixed point would break every preset built on the fold."""
    for text in ("०০೦", "g००gle", "pаypal", "١٥"):
        once = disarm.normalize_confusables(text, digit_policy=policy)
        assert disarm.normalize_confusables(once, digit_policy=policy) == once


def test_cyrillic_target_ignores_the_digit_policy() -> None:
    """Scope pin: the override set carries TR39's *Latin* targets.

    They are meaningless for a Cyrillic fold, so selecting ``tr39`` must not leak a Latin
    letter into a Cyrillic skeleton (``० → o``), and must not invent a fold for a source
    the Cyrillic table deliberately has no row for (``٠``, ``⁹``, ``𑣣`` all pass through).
    """
    for text in ("hello", "\u0966", "\u0660", "\u0668", "\u2079", "\U000118e3"):
        assert disarm.normalize_confusables(
            text, target_script="cyrillic"
        ) == disarm.normalize_confusables(text, target_script="cyrillic", digit_policy="tr39"), (
            f"digit policy changed the Cyrillic fold of {text!r}"
        )


def test_presets_are_unaffected() -> None:
    """Scope pin.

    The policy is a property of the `normalize_confusables` entry point, not of the
    presets. `canonicalize`, `catalog_key` and friends serve prose and keys, where numeric
    is unambiguously right, so they have no switch and must keep folding numerically.
    """
    assert disarm.canonicalize("०") == "0"
    assert disarm.catalog_key("०") == "0"


def test_is_confusable_is_unaffected() -> None:
    """Detection asks whether a row exists, not what it maps to.

    Both policies fold U+0966, so it is confusable either way; a purely ASCII string is
    confusable under neither. `is_confusable` therefore needs no policy parameter.
    """
    assert disarm.is_confusable("०") is True
    assert disarm.is_confusable("g००gle") is True
    assert disarm.is_confusable("google") is False


# ── the override set is generated, not hand-maintained ───────────────────────


def test_the_override_set_is_generated() -> None:
    """Acceptance criterion: the divergent rows are enumerated by the generator.

    ``scripts/gen_confusables.py`` already computes both sides — it makes this exact
    choice at generation time via ``enforce_digit_target`` (#439) — so the discarded
    alternative is emitted rather than thrown away. This asserts the artifact exists, is
    generated (its header says so), and that every row in it really is a disagreement:
    each source must fold to an ASCII digit under ``numeric`` and to something else under
    ``tr39``. A hand-edited row that agreed with the main table would fail here.
    """
    from pathlib import Path

    tsv = Path(__file__).resolve().parent.parent / "src/tables/data/confusables_digit_tr39.tsv"
    if not tsv.exists():  # pragma: no cover - source checkout only
        pytest.skip("source checkout only")

    lines = tsv.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("#") and "gen_confusables.py" in lines[0]

    rows = [line for line in lines[1:] if line.strip()]
    assert rows, "override set is empty"

    for row in rows:
        hex_cp, _ = row.split("\t", 1)
        source = chr(int(hex_cp, 16))
        numeric = disarm.normalize_confusables(source, digit_policy="numeric")
        tr39 = disarm.normalize_confusables(source, digit_policy="tr39")
        assert numeric.isdigit() and numeric.isascii(), (
            f"U+{hex_cp} is in the digit-policy override set but folds to {numeric!r} "
            f"under the numeric policy, which is not an ASCII digit"
        )
        assert tr39 != numeric, f"U+{hex_cp} is an override row but both policies agree"


def test_every_divergence_is_in_the_override_set() -> None:
    """The converse: no divergent row may be missing from the generated set.

    Scans the whole Latin table for sources that fold to an ASCII digit and checks the two
    policies disagree exactly where the override set says they do. Catches a generator
    change that starts dropping rows.
    """
    from pathlib import Path

    tsv = Path(__file__).resolve().parent.parent / "src/tables/data/confusables_digit_tr39.tsv"
    latin = Path(__file__).resolve().parent.parent / "src/tables/data/confusables_to_latin.tsv"
    if not tsv.exists() or not latin.exists():  # pragma: no cover
        pytest.skip("source checkout only")

    overrides = {
        int(line.split("\t", 1)[0], 16)
        for line in tsv.read_text(encoding="utf-8").splitlines()[1:]
        if line.strip()
    }
    for line in latin.read_text(encoding="utf-8").splitlines()[1:]:
        if not line.strip():
            continue
        hex_cp, value = line.split("\t", 1)
        if not (len(value) == 1 and value.isascii() and value.isdigit()):
            continue
        source = chr(int(hex_cp, 16))
        diverges = disarm.normalize_confusables(source, digit_policy="tr39") != value
        assert diverges == (int(hex_cp, 16) in overrides), (
            f"U+{hex_cp}: diverges={diverges} but in-override-set={int(hex_cp, 16) in overrides}"
        )


# ── #648: a third policy, because neither of the two keeps the script ─────────


def test_neither_existing_policy_keeps_the_script() -> None:
    """The premise of #648, asserted rather than described.

    ``numeric`` and ``tr39`` are not "keep the script" versus "fold to ASCII" — both
    rewrite the numeral, and both leave a *mixed-script* result, which is neither.
    """
    year = "२०२४"
    assert disarm.normalize_confusables(year, digit_policy="numeric") == "२0२४"
    assert disarm.normalize_confusables(year, digit_policy="tr39") == "२o२४"


@pytest.mark.parametrize(
    ("source", "numeric", "tr39"),
    [("०", "0", "o"), ("੦", "0", "o"), ("٥", "5", "o"), ("۰", "0", ".")],
)
def test_preserve_leaves_the_digit_alone(source: str, numeric: str, tr39: str) -> None:
    """The four rows #648 tabulates, checked against all three policies at once."""
    assert disarm.normalize_confusables(source, digit_policy="numeric") == numeric
    assert disarm.normalize_confusables(source, digit_policy="tr39") == tr39
    assert disarm.normalize_confusables(source, digit_policy="preserve") == source


def test_preserve_still_folds_letters() -> None:
    """It declines the digit rows, not the fold. A homoglyph attack is still neutralized."""
    assert disarm.normalize_confusables("раypal", digit_policy="preserve") == "paypal"
    assert disarm.normalize_confusables("२०२४ раypal", digit_policy="preserve") == "२०२४ paypal"


def test_preserve_applies_under_every_target_script() -> None:
    """Unlike ``tr39``, which is Latin-only because its override rows carry Latin targets.

    Declining to fold is not a Latin-specific act, and the two tables do not even agree on
    which sources are digit rows — 157 in the Latin map against 66 in the Cyrillic — so a
    Latin-only reading would leave the Cyrillic target with no way to express this at all.
    """
    for target in ("latin", "cyrillic"):
        assert (
            disarm.normalize_confusables("२०२४", target_script=target, digit_policy="preserve")
            == "२०२४"
        )


def test_preserve_is_a_fixed_point() -> None:
    """Trivially, since it makes no change to these rows — which is the point #648 makes
    about it being the only one of the three that cannot move on a second pass."""
    text = "२०२४ раypal ٥"
    once = disarm.normalize_confusables(text, digit_policy="preserve")
    assert disarm.normalize_confusables(once, digit_policy="preserve") == once
    assert once == "२०२४ paypal ٥"


def test_ascii_digits_are_untouched_under_preserve() -> None:
    """ASCII digits are not confusable sources, so there is nothing to decline."""
    assert disarm.normalize_confusables("2024", digit_policy="preserve") == "2024"
