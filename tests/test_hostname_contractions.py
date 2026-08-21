"""#562 — multi-codepoint confusable sources (contraction), scoped to hostnames.

``confusables_to_latin.tsv`` has 248 rows that map one codepoint to *several* — `0271`
→ ``rn`` — so **expansion** works. **Contraction** — recognising that ``rn`` may stand in
for ``m`` — did not, and not by omission: the source column of both tables is a single hex
codepoint in every data row, so the file format could not express it. This was a schema
change before it was a data change.

Scope is deliberately narrow. Unconditional contraction is worse than none: ``rn`` → ``m``
is right for ``arnazon`` and wrong for ``earnings``, ``turnip`` and ``born``. So it lives
on the hostname path, where the threat model justifies the false positives and there is no
running prose to corrupt, and it is off by default everywhere.
"""

from __future__ import annotations

import pytest

import disarm

# ── off by default ───────────────────────────────────────────────────────────


def test_contraction_changes_canonical_not_the_verdict() -> None:
    """The option is a canonicalization signal, not a verdict.

    `arnazon.com` is all-ASCII Latin — no mixed script, no cross-script confusable — so
    there is no evidence for a suspicious verdict, and disarm does not know `amazon` is a
    brand. A caller branching on the boolean sees nothing change; the signal is in
    `canonical`, to compare against their own allow list. Pinned because it is the most
    likely way to misuse the flag.
    """
    suspicious, analysis = disarm.is_suspicious_hostname("arnazon.com", contractions=True)
    assert suspicious is False
    assert analysis.canonical == "amazon.com"


def test_off_by_default() -> None:
    """The whole safety argument rests on this."""
    _suspicious, analysis = disarm.is_suspicious_hostname("arnazon.com")
    assert "amazon" not in analysis.canonical


def test_prose_words_are_never_corrupted_by_default() -> None:
    """`rn` → `m` unconditionally would break real words. The default must not."""
    for word in ("earnings", "turnip", "born", "modern", "government"):
        assert disarm.normalize_confusables(word) == word
        _s, analysis = disarm.is_suspicious_hostname(f"{word}.com")
        assert word in analysis.canonical


def test_the_general_fold_never_contracts() -> None:
    """Contraction is not reachable from `normalize_confusables` at all.

    The issue is explicit that a general-text contraction mode, if it ever lands, is a
    separate issue with its own disambiguation story. This pins that boundary.
    """
    assert disarm.normalize_confusables("arnazon") == "arnazon"
    with pytest.raises(TypeError):
        disarm.normalize_confusables("arnazon", contractions=True)  # type: ignore[call-arg]


# ── the feature ──────────────────────────────────────────────────────────────


def test_contraction_recovers_the_canonical_spoof() -> None:
    _suspicious, analysis = disarm.is_suspicious_hostname("arnazon.com", contractions=True)
    assert analysis.canonical == "amazon.com"


@pytest.mark.parametrize(
    ("spoof", "recovered"),
    [
        pytest.param("arnazon.com", "amazon.com", id="rn-to-m"),
        pytest.param("vvikipedia.org", "wikipedia.org", id="vv-to-w"),
        pytest.param("clropbox.com", "dropbox.com", id="cl-to-d"),
    ],
)
def test_each_rule_recovers_its_spoof(spoof: str, recovered: str) -> None:
    _s, analysis = disarm.is_suspicious_hostname(spoof, contractions=True)
    assert analysis.canonical == recovered


def test_contraction_composes_with_cross_script_folding() -> None:
    """A hostname can carry both an ASCII digraph and a Cyrillic homoglyph."""
    # Cyrillic а (U+0430) plus the rn digraph.
    _s, analysis = disarm.is_suspicious_hostname("аrnazon.com", contractions=True)
    assert analysis.canonical == "amazon.com"


# ── leftmost-longest ─────────────────────────────────────────────────────────


def test_leftmost_longest_semantics() -> None:
    """Overlapping candidates resolve leftmost-longest, not leftmost-first.

    ``rnn`` contains ``rn`` at offset 0 and ``nn`` would not match; but ``vvv`` contains
    ``vv`` at 0 and at 1. Leftmost wins, so ``vvv`` → ``wv``, never ``vw``.
    """
    _s, a = disarm.is_suspicious_hostname("vvv.com", contractions=True)
    assert a.canonical == "wv.com"


def test_non_overlapping_repeats_all_contract() -> None:
    _s, a = disarm.is_suspicious_hostname("vvvv.com", contractions=True)
    assert a.canonical == "ww.com"


def test_adjacent_distinct_rules() -> None:
    _s, a = disarm.is_suspicious_hostname("rnvv.com", contractions=True)
    assert a.canonical == "mw.com"


# ── invariants the schema change puts at risk ────────────────────────────────


@pytest.mark.parametrize("contractions", [False, True])
def test_idempotent(contractions: bool) -> None:
    """A source span longer than one codepoint makes the fixed point non-obvious.

    ``vvvv`` → ``ww`` must not then become ``w``: the second pass sees ``ww``, which is
    not a rule. But a rule set where one rule's output feeds another's input would loop,
    so this is the guard.
    """
    for host in ("arnazon.com", "vvvv.com", "rnrn.com", "example.com", "clcl.com"):
        _s1, a1 = disarm.is_suspicious_hostname(host, contractions=contractions)
        _s2, a2 = disarm.is_suspicious_hostname(a1.canonical, contractions=contractions)
        assert a2.canonical == a1.canonical, f"{host!r}: {a1.canonical!r} -> {a2.canonical!r}"


def test_label_structure_survives() -> None:
    """Contraction must not merge or drop labels."""
    _s, a = disarm.is_suspicious_hostname("arnazon.co.uk", contractions=True)
    assert a.canonical.count(".") == 2
    assert len(a.label_scripts) == 3


def test_no_contraction_across_a_label_boundary() -> None:
    """``r`` ending one label and ``n`` starting the next must not contract."""
    _s, a = disarm.is_suspicious_hostname("var.net", contractions=True)
    assert a.canonical == "var.net"


def test_empty_and_degenerate_inputs() -> None:
    for host in ("", ".", "a", "rn", "..", "a..b"):
        _s, a = disarm.is_suspicious_hostname(host, contractions=True)
        assert isinstance(a.canonical, str)


# ── the flag reaches the surface ─────────────────────────────────────────────


def test_flag_is_keyword_only() -> None:
    with pytest.raises(TypeError):
        disarm.is_suspicious_hostname("x.com", True)  # type: ignore[misc]


def test_other_analysis_fields_still_populated() -> None:
    _s, a = disarm.is_suspicious_hostname("arnazon.com", contractions=True)
    assert a.scripts == ["Latin"]
    assert isinstance(a.mixed_script, bool)
    assert isinstance(a.label_whole_script_confusable, list)
