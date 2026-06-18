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

from disarm import canonicalize, canonicalize_strict, strip_obfuscation

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

ZERO_WIDTH = ["​", "‌", "‍", "﻿", "⁠"]
BIDI = ["‮", "‭", "‎", "‏", "⁦", "⁩", "؜"]
COMBINING = ["́", "̀", "҉", "̵", "̶"]  # zalgo marks

DEFENSES = [strip_obfuscation, canonicalize, canonicalize_strict]


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
    return "‮" + t[:mid] + "‏" + t[mid:] + "‬"


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
