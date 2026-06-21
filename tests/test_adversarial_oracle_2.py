"""Adversarial property oracle, round 2: stateful builders, batch, and
reversible/derived-quantity contracts. Every property is provable from disarm's
own contract (no ghosts):

  * builder == free function ........ Text(x).M().value must equal disarm.M(x);
        Text(x).P() must equal disarm.P(x). The fluent builder is documented as
        the same operation, so any divergence is a real defect. (internal)
  * batch == per-item .............. transliterate/normalize on a list must equal
        the element-wise free-function results. (internal)
  * slug variants idempotent ....... a slug of a slug is the slug. (fixed point)
  * escape_html closure ............ no raw '<' or '>' may survive an HTML escaper.
  * percent_encode round-trips ..... output must decode back to the input under a
        standard percent-decoder (reversibility is the whole contract).
  * terminal_width = sum of widths . terminal_width(x) must equal the sum of its
        grapheme-cluster widths, and be non-negative. (internal)
"""

from __future__ import annotations

import os
from datetime import timedelta
from urllib.parse import unquote, unquote_plus

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import disarm

# Dev-tier property suite: excluded from CI's fast lane, run with `pytest -m hypothesis`.
pytestmark = pytest.mark.hypothesis

CP = st.characters(min_codepoint=0, max_codepoint=0x10FFFF, blacklist_categories=("Cs",))
TEXT = st.text(alphabet=CP, max_size=48)
ADV = [
    "",
    " ",
    "..",
    "‮",
    "e" + "́" * 60,
    "\U000e0041",
    "a️",
    "",
    "￾",
    "ＣＯＮ",
    "pаypаl",
    "a\nb",
    "a\x00b",
    "\U0001f1e9\U0001f1ea",
    "처리",
    "café",
    "Ⅻ",
    "ﬀ",
    "a<b>&\"'",
    "x y/z?q=1",
    "%41%",
    "100%",
]
SETTINGS = settings(
    max_examples=int(os.environ.get("ORACLE_MAXEX", "2000")),
    deadline=timedelta(seconds=2),
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)

# transform methods present on BOTH Text and the module (str->str via .value)
_TEXT_M = {m for m in dir(disarm.Text) if not m.startswith("_")}
TRANSFORM_M = sorted(
    _TEXT_M
    & {
        "canonicalize",
        "canonicalize_strict",
        "catalog_key",
        "collapse_whitespace",
        "demojize",
        "fold_case",
        "ml_normalize",
        "normalize",
        "normalize_confusables",
        "sanitize_filename",
        "security_clean",
        "display_clean",
        "normalize_user_input",
        "slugify",
        "strip_accents",
        "strip_bidi",
        "strip_format",
        "strip_obfuscation",
        "transliterate",
    }
)
PREDICATE_M = sorted(
    _TEXT_M
    & {
        "is_ascii",
        "is_normalized",
        "is_confusable",
        "is_mixed_script",
        "has_bidi_conflict",
    }
)
SLUG_VARIANTS = [
    getattr(disarm, n)
    for n in (
        "slugify_url",
        "slugify_filename",
        "slugify_de",
        "slugify_el",
        "slugify_ru",
        "slugify_unicode",
    )
    if hasattr(disarm, n)
]


def _check_builder(s):
    for name in TRANSFORM_M:
        free = getattr(disarm, name)(s)
        built = getattr(disarm.Text(s), name)().value
        assert built == free, f"Text(s).{name}().value != {name}(s) on {s!r}: {built!r} vs {free!r}"
    for name in PREDICATE_M:
        free = getattr(disarm, name)(s)
        built = getattr(disarm.Text(s), name)()
        assert built == free, f"Text(s).{name}() != {name}(s) on {s!r}: {built!r} vs {free!r}"


@SETTINGS
@given(s=TEXT)
def test_builder_matches_free(s):
    _check_builder(s)


@pytest.mark.parametrize("s", ADV)
def test_builder_matches_free_adv(s):
    _check_builder(s)


@SETTINGS
@given(s=TEXT, t=TEXT)
def test_batch_matches_per_item(s, t):
    assert disarm.transliterate([s, t]) == [disarm.transliterate(s), disarm.transliterate(t)], (
        f"transliterate batch != per-item on {s!r},{t!r}"
    )
    for F in ("NFC", "NFD", "NFKC", "NFKD"):
        assert disarm.normalize([s, t], form=F) == [
            disarm.normalize(s, form=F),
            disarm.normalize(t, form=F),
        ], f"normalize[{F}] batch != per-item on {s!r},{t!r}"


@SETTINGS
@given(s=TEXT)
def test_slug_variants_idempotent(s):
    for f in SLUG_VARIANTS:
        once = f(s)
        assert f(once) == once, (
            f"{f.__name__} not idempotent on {s!r}: once={once!r} twice={f(once)!r}"
        )


@SETTINGS
@given(s=TEXT)
def test_escape_html_no_raw_angle_brackets(s):
    out = disarm.escape_html(s)
    assert "<" not in out and ">" not in out, (
        f"raw angle bracket survived escape_html({s!r}) -> {out!r}"
    )


@pytest.mark.parametrize("s", ADV)
def test_escape_html_no_raw_angle_brackets_adv(s):
    out = disarm.escape_html(s)
    assert "<" not in out and ">" not in out


@SETTINGS
@given(s=TEXT)
def test_percent_encode_round_trips(s):
    for comp in disarm.Component:
        out = disarm.percent_encode(s, component=comp)
        # Recoverable by a standard percent-decoder. The OR covers the space<->'+'
        # convention difference between components without assuming which is used.
        ok = (unquote(out, errors="strict") == s) or (unquote_plus(out, errors="strict") == s)
        assert ok, f"percent_encode({comp}) not reversible on {s!r} -> {out!r}"


@SETTINGS
@given(s=TEXT)
def test_terminal_width_is_sum_of_cluster_widths(s):
    total = disarm.terminal_width(s)
    parts = sum(disarm.grapheme_width(g) for g in disarm.grapheme_split(s))
    assert total == parts, f"terminal_width {total} != sum of cluster widths {parts} on {s!r}"
    assert total >= 0, f"negative width on {s!r}"
