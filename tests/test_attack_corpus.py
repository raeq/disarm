"""Deterministic adversarial-attack regression (CI-gating).

This vendors compact generators for the Boucher et al. / *Fire Extinguishers*
attack taxonomy (homoglyph, zalgo, invisible, bidi, combined) and asserts
disarm's defense pipelines recover the clean form, using the paper's
Exact Match Recovery (XMR) idea: for a defense pipeline ``P`` and a clean
string ``t``, ``P(attack(t)) == P(t)``.

Unlike ``test_security_invariants.py`` (Hypothesis, tier-2, worktree-only),
these are deterministic and run in the CI gate, so the security behavior is
guarded on every PR. Scope is intentionally the *bundled TR39* confusables;
out-of-scope classes (novel/non-TR39 homoglyphs, whole-script spoofs,
multi-character confusables) are documented in THREAT_MODEL.md and are not
asserted here.
"""

from __future__ import annotations

import pytest

import disarm
from disarm import (
    canonicalize,
    canonicalize_strict,
    has_anomalies,
    inspect_anomalies,
    strip_obfuscation,
)

# Clean ASCII targets an attacker would spoof.
CORPUS = [
    "paypal",
    "product",
    "admin",
    "password",
    "microsoft",
    "login",
    "secure",
    "account",
    "google",
    "support",
]

# Latin -> visually-identical confusable (all bundled TR39 pairs).
# Cyrillic look-alikes plus a couple of Greek ones.
HOMOGLYPHS = {
    "a": "а",  # Cyrillic а
    "c": "с",  # Cyrillic с
    "e": "е",  # Cyrillic е
    "o": "о",  # Cyrillic о
    "p": "р",  # Cyrillic р
    "x": "х",  # Cyrillic х
    "y": "у",  # Cyrillic у
    "s": "ѕ",  # Cyrillic ѕ
    "i": "і",  # Cyrillic і
    "j": "ј",  # Cyrillic ј
}

ZERO_WIDTH = ["\u200b", "\u200c", "\u200d", "\ufeff", "\u2060"]
BIDI = ["\u202e", "\u202d", "\u200e", "\u200f", "\u2066", "\u2069", "\u061c"]
COMBINING = ["́", "̀", "҉", "̵", "̶"]  # zalgo marks

DEFENSES = [strip_obfuscation, canonicalize, canonicalize_strict]

# Every top-level surface plus every profile. The three `DEFENSES` above are the pipelines
# with a documented recovery claim; a negative has to be asserted against everything, or
# it only says the class survives the three surfaces someone thought to check.
ALL_SURFACES = {
    name: getattr(disarm, name)
    for name in (
        "canonicalize",
        "canonicalize_strict",
        "strip_obfuscation",
        "search_key",
        "sort_key",
        "catalog_key",
        "ml_normalize",
    )
}
ALL_SURFACES.update(
    {f"profile:{name}": disarm.get_pipeline(name) for name in disarm.list_profiles()}
)


def homoglyph(t: str) -> str:
    return "".join(HOMOGLYPHS.get(ch, ch) for ch in t)


def invisible(t: str) -> str:
    # Insert a zero-width char between every character.
    out = []
    for i, ch in enumerate(t):
        out.append(ch)
        out.append(ZERO_WIDTH[i % len(ZERO_WIDTH)])
    return "".join(out)


def bidi(t: str) -> str:
    # Wrap in an RLO...PDF and sprinkle marks.
    mid = len(t) // 2
    return "\u202e" + t[:mid] + "\u200f" + t[mid:] + "\u202c"


def zalgo(t: str, marks: int = 3) -> str:
    out = []
    for ch in t:
        out.append(ch)
        if ch.isalpha():
            out.extend(COMBINING[:marks])
    return "".join(out)


def combined(t: str) -> str:
    return bidi(invisible(homoglyph(t)))


ATTACKS = {
    "homoglyph": homoglyph,
    "invisible": invisible,
    "bidi": bidi,
    "zalgo": zalgo,
    "combined": combined,
}


# Which attacks each pipeline is expected to fully recover, per its documented
# steps. Only strip_obfuscation strips zalgo completely (max_marks=0);
# canonicalize has no zalgo step and canonicalize_strict caps combining marks
# rather than removing them, so neither fully recovers heavy zalgo — by design.
# We assert only positive recovery, so a future improvement can't break this.
RECOVERS = {
    "strip_obfuscation": {"homoglyph", "invisible", "bidi", "zalgo", "combined"},
    "canonicalize": {"homoglyph", "invisible", "bidi", "combined"},
    "canonicalize_strict": {"homoglyph", "invisible", "bidi", "combined"},
}

_CASES = [(d, a) for d in DEFENSES for a in ATTACKS if a in RECOVERS[d.__name__]]


@pytest.mark.parametrize("defense,attack_name", _CASES, ids=lambda x: getattr(x, "__name__", x))
def test_pipeline_recovers_clean_word(defense, attack_name: str) -> None:
    """For ASCII targets, the expected pipeline maps the attacked form back to
    the clean word (XMR with P(clean) == clean)."""
    misses = []
    for word in CORPUS:
        attacked = ATTACKS[attack_name](word)
        if defense(attacked) != word:
            misses.append((word, attacked, defense(attacked)))
    assert not misses, (
        f"{defense.__name__} did not recover {attack_name} for: "
        f"{[(w, got) for w, _a, got in misses]}"
    )


def test_homoglyph_pairs_are_all_in_bundled_table() -> None:
    """Guard: every homoglyph in this corpus must actually be a bundled
    confusable, else the corpus silently stops testing recovery."""
    from disarm import normalize_confusables

    not_folded = [
        (latin, conf)
        for latin, conf in HOMOGLYPHS.items()
        if normalize_confusables(conf, target_script="latin") == conf
    ]
    assert not not_folded, f"homoglyphs not in bundled table: {not_folded}"


# --------------------------------------------------------------------------------------
# The deletion class (#739)
#
# Boucher et al. §IV-G names four classes of imperceptible perturbation: invisible
# characters, homoglyphs, reorderings, and **deletions** — "the backspace (BS) and delete
# (DEL) characters… there is also the carriage return (CR)". The generators above cover
# three. This is the fourth.
#
# Unlike the three above it is asserted as a NEGATIVE. disarm detects the whole class and
# resolves none of it, and that is a decision rather than a gap — see THREAT_MODEL.md
# under "Deletion controls". Resolving BS/DEL means reproducing one renderer's behaviour,
# and the paper says in the same section that the class is renderer-dependent ("most
# systems do not copy deleted text to the clipboard"); a browser drawing a control picture
# renders neither form, so resolution would *lose* text a reader can see. CR is folded to
# a space, which surfaces the overwritten prefix instead of hiding it — strictly safer for
# a moderation filter than reproducing the rendering.
#
# The RECOVERS map above asserts only positive recovery, by deliberate choice, "so a
# future improvement can't break this". That leaves an out-of-scope decision nowhere to
# live, which is what let this class sit unnamed. The negatives below are the other half:
# they pin what disarm does *not* do, so a change of policy has to be deliberate.
# --------------------------------------------------------------------------------------

BS, DEL, CR = "\x08", "\x7f", "\r"


def deletion_bs(t: str) -> str:
    """The paper's §VI-A construction: one non-control character, then BKSP."""
    return "".join(ch + "X" + BS for ch in t)


def deletion_del(t: str) -> str:
    return "".join(ch + "X" + DEL for ch in t)


def deletion_cr(t: str) -> str:
    """A prefix the carriage return paints over."""
    return "Z" * len(t) + CR + t


DELETIONS = {
    "deletion_bs": deletion_bs,
    "deletion_del": deletion_del,
    "deletion_cr": deletion_cr,
}


def render(text: str) -> str:
    """A terminal's reading of BS / DEL / CR, modelled independently of disarm.

    Deliberately not built from any disarm surface: the premise of this section is that
    the rendering and the code points disagree, and a premise checked with the code under
    test is not checked. The model is the paper's: BS and DEL erase the previous cell, CR
    returns the cursor to the start of the line and later text overwrites earlier text.
    """
    line: list[str] = []
    out: list[str] = []
    col = 0
    for ch in text:
        if ch in (BS, DEL):
            col = max(0, col - 1)
            del line[col:]
        elif ch == CR:
            col = 0
        elif ch == "\n":
            out.append("".join(line))
            line, col = [], 0
        else:
            if col < len(line):
                line[col] = ch
            else:
                line.append(ch)
            col += 1
    out.append("".join(line))
    return "\n".join(out)


def test_the_render_model_is_not_circular() -> None:
    """The model must be right about text disarm has no opinion on."""
    assert render("abc") == "abc"
    assert render("ab" + BS + "c") == "ac"
    assert render("abc" + CR + "xy") == "xyc"
    assert render("a\nb") == "a\nb"


@pytest.mark.parametrize("attack_name", sorted(DELETIONS))
def test_deletion_attacks_render_as_the_clean_word(attack_name: str) -> None:
    """The premise. Without this the negatives below pin nothing interesting."""
    attack = DELETIONS[attack_name]
    for word in CORPUS:
        assert render(attack(word)) == word, (attack_name, word)


@pytest.mark.parametrize("attack_name", sorted(DELETIONS))
def test_deletion_class_is_detected(attack_name: str) -> None:
    """Half one: every member of the class is reported.

    `deletion_cr` was reported by nothing before #739 — a lone CR is whitespace, so it
    splits the tokens either side of it and both halves are clean on their own. No
    per-token rule can see it, which is why the check is text-level.
    """
    attack = DELETIONS[attack_name]
    missed = [w for w in CORPUS if not has_anomalies(attack(w))]
    assert not missed, f"{attack_name} undetected for: {missed}"


@pytest.mark.parametrize("attack_name", sorted(DELETIONS))
def test_deletion_class_is_reported_with_a_locatable_kind(attack_name: str) -> None:
    """The kind names the treatment path, which is why the class spans two of them.

    BS and DEL are non-whitespace controls that `strip_control_chars` removes, so they are
    `control`. CR is whitespace-class and `collapse_whitespace` folds it to a space rather
    than deleting it, so it is `deletion`. Changing either would be a breaking change to a
    released kind, and this asserts nobody does it by accident.
    """
    expected = "deletion" if attack_name == "deletion_cr" else "control"
    for word in CORPUS:
        report = inspect_anomalies(DELETIONS[attack_name](word))
        assert expected in report.kinds, (attack_name, word, report.kinds)


def test_the_deletion_finding_names_what_was_erased() -> None:
    """#739 §2: `U+0008` alone does not say what vanished."""
    report = inspect_anomalies(deletion_bs("paypal"))
    assert "erases the preceding 'X'" in report.findings[0].reason

    report = inspect_anomalies(deletion_cr("paypal"))
    finding = report.findings[0]
    assert finding.kind == "deletion"
    assert finding.token == "Z" * len("paypal"), "the overwritten prefix is the span"
    assert "overwritten by what follows the carriage return" in finding.reason


@pytest.mark.parametrize("attack_name", sorted(DELETIONS))
def test_deletion_class_is_not_resolved_on_any_surface(attack_name: str) -> None:
    """Half two, and the negative pin: XMR is 0 everywhere, deliberately.

    If a future change starts recovering this class, this test fails and the policy in
    THREAT_MODEL.md has to be revisited in the same commit — which is the point. It is
    not asserting that recovery would be wrong; it is asserting that it is a decision.
    """
    attack = DELETIONS[attack_name]
    recovered = [
        (name, word)
        for name, surface in ALL_SURFACES.items()
        for word in CORPUS
        if surface(attack(word)) == surface(word)
    ]
    assert not recovered, f"{attack_name} is now recovered by: {sorted({n for n, _ in recovered})}"


def test_ordinary_uses_of_cr_are_spared() -> None:
    """The rule has three guards and each spares something ordinary.

    A detector that fired on every CRLF file would be turned off, which is the failure
    mode #612 drew the whitespace exclusion for in the first place.
    """
    assert not has_anomalies("line one\r\nline two\r\n"), "CRLF line endings"
    assert not has_anomalies("no newline at eof\r"), "trailing CR overwrites nothing"
    assert not has_anomalies("\rleading"), "nothing before it on the line"
    assert not has_anomalies("col1\tcol2\nrow1\trow2\n"), "ordinary multi-line text"


def test_the_known_false_positive_is_the_documented_one() -> None:
    """Classic Mac OS used a lone CR as its line ending until 2001.

    Pinned rather than fixed: the two are indistinguishable from the bytes, and the
    report is a technical fact the caller judges — the same stance `is_case_fold_stable`
    takes on `groß`. Documented in the `Deletion` kind's rustdoc and in the anomaly
    guide, so a reader meeting the false positive finds it named.
    """
    assert has_anomalies("line one\rline two"), "indistinguishable from an overwrite"
