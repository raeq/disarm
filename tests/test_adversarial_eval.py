"""Offline unit tests for the adversarial-eval metric math (#49).

The harness itself is an out-of-CI benchmark (it pulls large external corpora),
but its metric logic is pure and worth guarding. These tests use synthetic
records and ``processes=1`` (inline) — no network, no ``datasets``.
"""

from __future__ import annotations

from benchmarks.adversarial_eval.corpora import Record
from benchmarks.adversarial_eval.metrics import (
    _word_recovery,
    evaluate,
    load_uts39_sources,
)


def test_word_recovery_multiset_overlap() -> None:
    assert _word_recovery("a b c", "a b c") == 1.0
    assert _word_recovery("a c", "a b c") == 2 / 3
    assert _word_recovery("", "a b") == 0.0
    assert _word_recovery("x", "") == 0.0


def test_load_uts39_sources_contains_known_confusable() -> None:
    sources = load_uts39_sources()
    assert len(sources) > 1000
    assert 0x0430 in sources  # Cyrillic 'а', a canonical Latin confusable


def test_labeled_recovery_on_confusable_pairs() -> None:
    # strip_obfuscation folds the Cyrillic look-alikes back to the clean ASCII,
    # so both pairs recover exactly.
    records = [
        Record(text="paypal", clean="paypal"),
        Record(text="pаypаl", clean="paypal"),  # Cyrillic а ×2
    ]
    res = evaluate(records, corpus="t", labeled=True, processes=1)
    assert res.n_rows == 2
    assert res.xmr == 1.0
    assert res.line_exact == 1.0
    assert res.word_recovery == 1.0
    # The perturbed row had 2 non-ASCII codepoints, both folded away.
    assert res.nonascii_before == 2
    assert res.nonascii_after == 0
    assert res.folded_fraction == 1.0
    assert res.rows_with_nonascii == 1


def test_word_recovery_uses_canonicalized_clean() -> None:
    # Regression for PR #225 review: word-level recovery compares the recovered
    # text against the *canonicalized* clean (strip_obfuscation(clean)), to stay
    # consistent with XMR. Here the clean side itself carries a Cyrillic 'а'; both
    # sides canonicalize to "paypal", so recovery is 1.0 (it would be 0.0 against
    # the raw clean "pаypal").
    res = evaluate([Record(text="paypal", clean="pаypal")], corpus="t", labeled=True, processes=1)
    assert res.word_recovery == 1.0
    assert res.xmr == 1.0


def test_unlabeled_skips_recovery_metrics() -> None:
    res = evaluate([Record(text="hello world")], corpus="t", labeled=False, processes=1)
    assert res.xmr is None and res.word_recovery is None and res.line_exact is None
    assert res.perturbation_bearing_rate == 0.0  # pure ASCII


def test_miss_mining_accounts_every_surviving_codepoint() -> None:
    # Box-drawing/control-picture chars survive strip_obfuscation; whatever
    # survives must be classified into exactly one bucket per row.
    sources = load_uts39_sources()
    res = evaluate([Record(text="abc █┃ def")], corpus="t", labeled=False, processes=1)
    total_missed = sum(res.missed_principled.values()) + sum(res.missed_novel.values())
    assert total_missed == res.nonascii_after
    # principled = in UTS#39, novel = not — partitions are disjoint by construction
    for cp in res.missed_principled:
        assert cp in sources
    for cp in res.missed_novel:
        assert cp not in sources


def test_miss_mining_counts_every_occurrence_not_distinct() -> None:
    # Regression for PR #225 review: misses are reported as "occurrences" and
    # must reconcile with nonascii_after, so a codepoint repeated within a row is
    # counted once per occurrence — not once per row. '█' (U+2588) survives
    # strip_obfuscation and is a UTS#39 source.
    res = evaluate([Record(text="a█b█c")], corpus="t", labeled=False, processes=1)
    assert res.nonascii_after == 2  # two '█'
    total_missed = sum(res.missed_principled.values()) + sum(res.missed_novel.values())
    assert total_missed == res.nonascii_after  # every occurrence counted
    combined = res.missed_principled + res.missed_novel
    assert combined[ord("█")] == 2  # repeated char counted twice, not deduped to 1
