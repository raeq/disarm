"""Adversarial property oracle for disarm.

Goal: FIND defects, not fix them. Every property below is provably correct from
disarm's own contract or from an eternal/internal reference, so a failure is a
real defect and never a curated-output disagreement (no ghosts):

  * determinism / idempotency / crash-freedom .... pure-function + fixed-point
        codomain contracts; internal, version-independent.
  * ASCII closure ................................ tables are ASCII-only
        (build.rs compile-time assertion) and default errors="replace",
        replace_with="[?]" is ASCII; no "preserve" leak. So transliterate /
        unidecode / slugify output must be all-ASCII.
  * grapheme split losslessness ................. any segmentation must
        concatenate back to the input; uses disarm's own split for the count.
  * normalize algebraic laws .................... NFC=NFC.NFD, NFD=NFD.NFC,
        NFKC=NFKC.NFKD, NFKD=NFKD.NFC, each idempotent. These hold for ANY
        correct normalizer regardless of Unicode version (internal).
  * is_ascii / is_normalized self-consistency ... is_ascii==str.isascii (ASCII
        is eternal); is_normalized(x,F)==(normalize(x,F)==x) (both disarm's own,
        so immune to CPython Unicode-version skew).
  * strip_log_injection closure ................. CR/LF must not survive.
  * percent_encode well-formedness .............. output ASCII, every '%' a %XX.
  * cache coherence ............................. a memoized transliterator must
        return the same value as the free function.

The one EXTERNAL reference check (normalize vs CPython unicodedata) is gated to
codepoints assigned in CPython's Unicode build, so version skew cannot ghost it.
"""

from __future__ import annotations

import os
import re
import time
import unicodedata
from datetime import timedelta

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

import disarm

# Dev-tier property suite: excluded from CI's fast lane, run with `pytest -m hypothesis`.
pytestmark = pytest.mark.hypothesis

# --- input space ----------------------------------------------------------
# Full Unicode scalar values incl. astral, excluding surrogates (Python str
# cannot carry lone surrogates through the C boundary anyway).
CP = st.characters(min_codepoint=0, max_codepoint=0x10FFFF, blacklist_categories=("Cs",))
TEXT = st.text(alphabet=CP, max_size=48)

# Deterministic adversarial corpus, exercised explicitly so the nasty inputs are
# always hit regardless of hypothesis sampling.
ADV = [
    "",  # empty
    " ",
    "   ",  # whitespace only
    ".",
    "..",
    "...",  # dot hygiene
    "‮",
    "a‮b‬",  # RTLO / Trojan-source
    "​‌‍",  # zero-width
    "e" + "́" * 200,  # zalgo / long combining run
    "\U000e0041\U000e0042",  # Unicode Tag chars
    "a️",
    "a\U000e0100",  # variation selectors
    "",
    "\U000f0000",
    "\U0010fffd",  # PUA (BMP + planes 15/16)
    "￾￿﷐\U0001fffe",  # noncharacters
    "﻿",  # BOM
    "ＣＯＮ",  # fullwidth CON
    "pаypаl",  # mixed-script homoglyph
    "a\nb\r\nc",
    "a\x00b",
    "a\tb",  # controls / CRLF / null
    "\U0001d54a\U0001d557",  # astral math letters
    "\U0001f1e9\U0001f1ea",  # regional indicator (flag)
    "처리",  # conjoining Hangul jamo (NFD)
    "กำ" * 50,  # Thai + SARA AM
    "\U000102a7",  # astral letter
    "café",
    "CAFÉ",
    "Ⅻ",
    "ﬀ",
    "²",
    "½",  # NF-relevant
]


# --- roster ----------------------------------------------------------------
def _g(name):
    return getattr(disarm, name, None)


# str -> str transforms callable as f(x) with all defaults.
TRANSFORM_NAMES = [
    "transliterate",
    "unidecode",
    "slugify",
    "normalize",
    "normalize_confusables",
    "sanitize_filename",
    "strip_accents",
    "fold_case",
    "collapse_whitespace",
    "canonicalize",
    "ml_normalize",
    "catalog_key",
    "strip_format",
    "search_key",
    "sort_key",
    "strip_bidi",
    "strip_tags",
    "strip_variation_selectors",
    "strip_noncharacters",
    "strip_pua",
    "canonicalize_strict",
    "strip_obfuscation",
    "security_clean",
    "display_clean",
    "normalize_user_input",
    "strip_zalgo",
    "escape_html",
    "strip_log_injection",
    "demojize",
]
TRANSFORMS = [(n, _g(n)) for n in TRANSFORM_NAMES if _g(n) is not None]

# Fixed-point-codomain functions: f(f(x)) == f(x) is required by their contract.
# Excluded: escape_html (double-escapes), percent_encode (double-encodes),
# demojize (emoji->:shortcode: is not a documented fixed point).
NON_IDEMPOTENT = {"escape_html", "demojize"}
IDEMPOTENT = [(n, f) for (n, f) in TRANSFORMS if n not in NON_IDEMPOTENT]

# Output must be all-ASCII (see module docstring).
ASCII_CLOSURE = [(n, _g(n)) for n in ("transliterate", "unidecode", "slugify") if _g(n)]

PREDICATE_NAMES = [
    "is_ascii",
    "is_normalized",
    "is_zalgo",
    "is_confusable",
    "is_mixed_script",
    "has_bidi_conflict",
    "has_anomalies",
]
PREDICATES = [(n, _g(n)) for n in PREDICATE_NAMES if _g(n) is not None]

FORMS = ("NFC", "NFD", "NFKC", "NFKD")

SETTINGS = settings(
    max_examples=int(os.environ.get("ORACLE_MAXEX", "2000")),
    deadline=timedelta(
        seconds=2
    ),  # speed-vs-adversary: a 48-char input taking >2s is a complexity defect
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)


# ===========================================================================
# correctness / robustness: nothing crashes
# ===========================================================================
@SETTINGS
@given(s=TEXT)
def test_transforms_never_crash(s):
    for name, f in TRANSFORMS:
        try:
            r = f(s)
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"{name}({s!r}) raised {type(e).__name__}: {e}")
        assert isinstance(r, str), f"{name} returned {type(r).__name__}"


@pytest.mark.parametrize("s", ADV)
def test_transforms_never_crash_adv(s):
    for name, f in TRANSFORMS:
        try:
            assert isinstance(f(s), str)
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"{name}({s!r}) raised {type(e).__name__}: {e}")


@SETTINGS
@given(s=TEXT)
def test_predicates_never_crash(s):
    for name, f in PREDICATES:
        try:
            f(s)
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"{name}({s!r}) raised {type(e).__name__}: {e}")


# ===========================================================================
# correctness: determinism
# ===========================================================================
@SETTINGS
@given(s=TEXT)
def test_determinism(s):
    for name, f in TRANSFORMS:
        assert f(s) == f(s), f"{name} nondeterministic on {s!r}"


# ===========================================================================
# correctness: idempotency (fixed-point codomain)
# ===========================================================================
@SETTINGS
@given(s=TEXT)
def test_idempotent(s):
    for name, f in IDEMPOTENT:
        once = f(s)
        twice = f(once)
        assert twice == once, f"{name} not idempotent: f({s!r})={once!r}, f(f)={twice!r}"


@pytest.mark.parametrize("s", ADV)
def test_idempotent_adv(s):
    for name, f in IDEMPOTENT:
        once = f(s)
        assert f(once) == once, f"{name} not idempotent on {s!r}: once={once!r} twice={f(once)!r}"


# ===========================================================================
# completeness: ASCII closure
# ===========================================================================
@SETTINGS
@given(s=TEXT)
def test_ascii_closure(s):
    for name, f in ASCII_CLOSURE:
        out = f(s)
        assert out.isascii(), f"{name}({s!r}) -> non-ASCII {out!r}"


@pytest.mark.parametrize("s", ADV)
def test_ascii_closure_adv(s):
    for name, f in ASCII_CLOSURE:
        out = f(s)
        assert out.isascii(), f"{name}({s!r}) -> non-ASCII {out!r}"


# ===========================================================================
# correctness: grapheme segmentation is lossless
# ===========================================================================
@SETTINGS
@given(s=TEXT)
def test_grapheme_split_lossless(s):
    parts = disarm.grapheme_split(s)
    assert "".join(parts) == s, f"grapheme_split lost data: {parts!r}"
    assert disarm.grapheme_len(s) == len(parts), "grapheme_len != len(split)"


@pytest.mark.parametrize("s", ADV)
def test_grapheme_split_lossless_adv(s):
    parts = disarm.grapheme_split(s)
    assert "".join(parts) == s
    assert disarm.grapheme_len(s) == len(parts)


@SETTINGS
@given(s=TEXT, n=st.integers(min_value=0, max_value=60))
def test_grapheme_truncate_is_prefix(s, n):
    out = disarm.grapheme_truncate(s, n)
    assert s.startswith(out), f"truncate not a prefix: {out!r} of {s!r}"
    assert disarm.grapheme_len(out) == min(n, disarm.grapheme_len(s)), (
        "wrong truncated cluster count"
    )


# ===========================================================================
# correctness: normalize algebraic laws + self-consistency (version-independent)
# ===========================================================================
@SETTINGS
@given(s=TEXT)
def test_normalize_idempotent_per_form(s):
    for F in FORMS:
        one = disarm.normalize(s, form=F)
        assert disarm.normalize(one, form=F) == one, f"normalize {F} not idempotent on {s!r}"


@SETTINGS
@given(s=TEXT)
def test_normalize_composition_laws(s):
    nfd = disarm.normalize(s, form="NFD")
    nfc = disarm.normalize(s, form="NFC")
    nfkd = disarm.normalize(s, form="NFKD")
    assert disarm.normalize(nfd, form="NFC") == nfc, "NFC != NFC.NFD"
    assert disarm.normalize(nfc, form="NFD") == nfd, "NFD != NFD.NFC"
    assert disarm.normalize(nfkd, form="NFKC") == disarm.normalize(s, form="NFKC"), (
        "NFKC != NFKC.NFKD"
    )


@SETTINGS
@given(s=TEXT)
def test_is_normalized_self_consistent(s):
    for F in FORMS:
        assert disarm.is_normalized(s, form=F) == (disarm.normalize(s, form=F) == s), (
            f"is_normalized({F}) disagrees with normalize on {s!r}"
        )


# ===========================================================================
# correctness: is_ascii matches the eternal definition
# ===========================================================================
@SETTINGS
@given(s=TEXT)
def test_is_ascii_matches_definition(s):
    assert disarm.is_ascii(s) == s.isascii(), f"is_ascii wrong on {s!r}"


@pytest.mark.parametrize("s", ADV)
def test_is_ascii_matches_definition_adv(s):
    assert disarm.is_ascii(s) == s.isascii()


# ===========================================================================
# external reference: normalize vs CPython unicodedata, gated on assigned cps
# ===========================================================================
ASSIGNED = st.text(
    alphabet=st.characters(
        min_codepoint=0, max_codepoint=0x2FFF, blacklist_categories=("Cs", "Cn")
    ),
    max_size=24,
)


@SETTINGS
@given(s=ASSIGNED)
def test_normalize_matches_unicodedata(s):
    # Only compare where every codepoint is assigned in CPython's Unicode build,
    # so disarm vs CPython Unicode-version skew cannot produce a false failure.
    assume(all(unicodedata.category(c) != "Cn" for c in s))
    for F in FORMS:
        assert disarm.normalize(s, form=F) == unicodedata.normalize(F, s), (
            f"normalize {F} != unicodedata on {s!r}"
        )


# ===========================================================================
# completeness: strip_log_injection removes CR/LF
# ===========================================================================
@SETTINGS
@given(s=TEXT)
def test_strip_log_injection_removes_crlf(s):
    out = disarm.strip_log_injection(s)
    assert "\n" not in out and "\r" not in out, f"CR/LF survived: {out!r}"


@pytest.mark.parametrize("s", ADV + ["log\nINJECT", "a\r\nb", "x y", "zw"])
def test_strip_log_injection_removes_crlf_adv(s):
    out = disarm.strip_log_injection(s)
    assert "\n" not in out and "\r" not in out


# ===========================================================================
# completeness: percent_encode is well-formed (ASCII + valid %XX)
# ===========================================================================
PCT = re.compile(r"%(?![0-9A-Fa-f]{2})")


@SETTINGS
@given(s=TEXT)
def test_percent_encode_wellformed(s):
    for comp in disarm.Component:
        out = disarm.percent_encode(s, component=comp)
        assert out.isascii(), f"percent_encode non-ASCII for {comp}: {out!r}"
        assert not PCT.search(out), f"malformed %-escape for {comp}: {out!r}"


# ===========================================================================
# correctness: cache coherence
# ===========================================================================
@SETTINGS
@given(s=TEXT)
def test_cache_coherence(s):
    cached = disarm.make_cached_transliterator()
    assert cached(s) == disarm.transliterate(s), f"cache != free on {s!r}"


@SETTINGS
@given(s=TEXT)
def test_dedup_batch_coherence(s):
    assert disarm.dedup_batch([s, s]) == [disarm.transliterate(s), disarm.transliterate(s)], (
        f"dedup_batch != transliterate on {s!r}"
    )


# ===========================================================================
# speed vs adversary: pathological inputs must not blow up
# ===========================================================================
PATHOLOGICAL = {
    "long_ascii": "a" * 20000,
    "long_combining": "e" + "́" * 8000,
    "long_thai": "กำ" * 4000,
    "long_astral": "\U0001f600" * 8000,
    "long_rtlo": "‮" * 8000,
}


@pytest.mark.parametrize("label,s", list(PATHOLOGICAL.items()))
def test_no_pathological_blowup(label, s):
    for name, f in TRANSFORMS:
        t0 = time.perf_counter()
        f(s)
        dt = time.perf_counter() - t0
        assert dt < 5.0, f"{name} took {dt:.2f}s on {label} ({len(s)} chars)"


# ===========================================================================
# completeness: sanitize_filename must never return a directory reference.
# Regression guard for #487/#489: sanitize_filename("_"+c) used to return "."
# for 112 dot-like codepoints (U+00B7, U+0387, ...) that transliterate to ".".
# A bare "." is the current directory, not a filename. Fixed in #489 (never
# return ""/"."/".."); these tests lock that fix against regression.
# ===========================================================================
@SETTINGS
@given(s=TEXT)
def test_sanitize_filename_never_dir_ref(s):
    out = disarm.sanitize_filename(s)
    assert out not in (".", ".."), f"sanitize_filename({s!r}) returned directory reference {out!r}"


_DOTLIKE = [".", "·", "˙", "·", "։", "׃", "٫", "۔", "܀", "।", "॰", "৽"]


@pytest.mark.parametrize("c", _DOTLIKE)
def test_sanitize_filename_sep_plus_dotlike(c):
    out = disarm.sanitize_filename("_" + c)
    assert out not in (".", ".."), (
        f"sanitize_filename('_'+U+{ord(c):04X}) -> {out!r} (directory reference)"
    )
