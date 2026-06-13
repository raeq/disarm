"""Performance integrity claims relocated from docs/performance.md (#322).

``docs/performance.md`` presents its numbers as comparison tables only. The
executable proof that used to back those tables — the conservative ratio floors
and the fast-path guarantees — lives here, so the claims still self-verify in CI
instead of rotting in prose. The page carried these as on-page Sybil doc-test
blocks under #291; #322 makes the page tables-only and relocates the assertions here.

Two kinds of check, mirroring exactly what the doc-test blocks did:

* **Behavioural** (always run, disarm-only): the borrowed-``Cow`` ASCII identity
  fast path, ``batch == loop`` equivalence, and the documented example outputs.
  These ran unconditionally in the doc-test gate and keep doing so here.
* **Ratio floors** (run only where the pinned comparators from
  ``requirements/bench.txt`` are installed — ``perf-gate.yml`` and a local
  ``pip install -e .[bench]`` — and ``skip`` cleanly otherwise, exactly as the
  old blocks did via ``pytest.skip`` on ``ImportError``). The asserted floors are
  deliberately far looser than the published figures (~13–38×): a loose floor
  proves *direction and order of magnitude* on unknown, possibly loaded CI
  hardware without flaking, while the precise numbers live on the page and the
  ``perf-results`` branch.
"""

from __future__ import annotations

import statistics
import time

import pytest

from disarm import (
    fold_case,
    sanitize_filename,
    slugify,
    strip_accents,
    transliterate,
)

# ---------------------------------------------------------------------------
# Interleaved timing helper — fresh-string regime (see benchmarks/bench_ratio.py)
# ---------------------------------------------------------------------------

INNER = 4000
REPS = 5


def _fresh_copies(text, n):
    """``n`` distinct ``str`` objects with identical content.

    Honours the fresh-string regime (``regime: fresh-string/v2``, #303): every
    timed call must receive a newly constructed object, so disarm cannot reuse
    CPython's per-object UTF-8 cache (which the pure-Python comparators never
    touch and which would otherwise inflate the ratio). ``s + ""``, full slices
    and ``"".join((s,))`` all return the *same* object, so — as in
    ``benchmarks/bench_ratio.py`` — force a fresh allocation with ``(s + " ")[:-1]``.
    """
    return [(text + " ")[:-1] for _ in range(n)]


def _timed(fn, objs):
    """Wall-clock seconds for one call of ``fn`` over each object in ``objs``."""
    start = time.perf_counter()
    for obj in objs:
        fn(obj)
    return time.perf_counter() - start


def _speed_ratio(translit_fn, other_fn, arg, inner=INNER, reps=REPS):
    """Median interleaved ``other / disarm`` ratio over fresh strings; >1 = disarm faster.

    Fresh objects are built outside the timed region. Interleaving the two
    functions per round and taking the median across ``reps`` rounds cancels
    transient scheduler load; the residual ``perf_counter`` overhead is added to
    both sides, which only *deflates* the ratio — so the floors are conservative.
    """
    ratios = []
    for _ in range(reps):
        t = _timed(translit_fn, _fresh_copies(arg, inner))
        o = _timed(other_fn, _fresh_copies(arg, inner))
        ratios.append(o / t)
    return statistics.median(ratios)


# ---------------------------------------------------------------------------
# Behavioural guarantees — always run (disarm only)
# ---------------------------------------------------------------------------


def test_ascii_passthrough_returns_same_object():
    """Already-ASCII input returns the *same* str object (borrowed Cow, #277)."""
    s = "plain ascii text 12345"
    assert transliterate(s) is s  # identity, not just an equal copy


def test_batch_matches_loop():
    """The list (batch) path is value-identical to a per-item loop."""
    items = ["Café", "Москва", "Ελληνικά", "naïve", "Straße"] * 20  # 100 strings
    assert transliterate(items) == [transliterate(x) for x in items]


def test_documented_example_outputs():
    """The exact outputs shown alongside the speed claims on the page."""
    assert slugify("Crème Brûlée") == "creme-brulee"
    assert sanitize_filename("my<illegal>:name?.txt") == "my_illegal_name.txt"
    assert fold_case("Straße") == "strasse"
    assert strip_accents("café résumé") == "cafe resume"


# ---------------------------------------------------------------------------
# Ratio floors — need the pinned comparators; skip cleanly otherwise
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_short_string_faster_than_unidecode():
    """Per-call, short mixed-script field. Published ~13–17×; floor 4×."""
    unidecode = pytest.importorskip(
        "unidecode", reason="Unidecode not installed; see requirements/bench.txt"
    ).unidecode
    short = "Ärger café Москва Ελληνικά"  # Latin diacritics, Cyrillic, Greek
    ratio = _speed_ratio(transliterate, unidecode, short)
    assert ratio > 4, f"short-string vs Unidecode: {ratio:.1f}x (floor 4x)"


@pytest.mark.slow
def test_document_scale_faster_than_unidecode():
    """Document scale (~3 KB). Published ~38× Latin / ~15× Cyrillic; floor 6×."""
    unidecode = pytest.importorskip(
        "unidecode", reason="Unidecode not installed; see requirements/bench.txt"
    ).unidecode
    document = (
        "Schöne Grüße aus München. Café au lait. Здравствуйте, мир. Ελληνικά κείμενα. "
    ) * 40
    ratio = _speed_ratio(transliterate, unidecode, document, inner=400, reps=5)
    assert ratio > 6, f"document-scale vs Unidecode: {ratio:.1f}x (floor 6x)"


@pytest.mark.slow
def test_slugify_faster_than_python_slugify():
    """Published ~10–24× vs python-slugify; floor 3×."""
    py_slugify = pytest.importorskip(
        "slugify", reason="python-slugify not installed; see requirements/bench.txt"
    ).slugify
    title = "Hello, World! Crème Brûlée & Café — a Long-ish Title for Slugging"
    ratio = _speed_ratio(slugify, py_slugify, title)
    assert ratio > 3, f"slugify vs python-slugify: {ratio:.1f}x (floor 3x)"


@pytest.mark.slow
def test_sanitize_filename_faster_than_pathvalidate():
    """Published ~10–16× vs pathvalidate; floor 3×."""
    pv_sanitize = pytest.importorskip(
        "pathvalidate", reason="pathvalidate not installed; see requirements/bench.txt"
    ).sanitize_filename
    name = "my<illegal>:name?.txt"
    ratio = _speed_ratio(sanitize_filename, pv_sanitize, name)
    assert ratio > 3, f"sanitize_filename vs pathvalidate: {ratio:.1f}x (floor 3x)"
