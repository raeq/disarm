"""#477: the boundary-normalization invariant, enforced by a self-guarding audit.

Invariant: every public ``str -> str`` **recovery / canonicalization** entrypoint
normalizes its input at the boundary, so its output is invariant to the input's
normal form — ``f(NFC(x)) == f(NFD(x)) == f(NFKD(x))``. A security library must not
let an attacker change behavior by decomposing input.

`normalize_confusables` was the first instance (#475). This module generalizes it:
the audit **enumerates** the public ``str -> str`` entrypoints from ``disarm.__all__``
(it does not hardcode a list, mirroring the #469 surrogate dynamic-wrap audit) and
asserts form-invariance for each, so a *future* entrypoint that forgets to normalize
fails here, not in production.

Decision (b) — the form-*preserving* primitives (case fold, the targeted strips,
whitespace collapse, HTML escape, log-injection scrub, demojize) deliberately
preserve composition: their contract is a targeted transform, not canonicalization,
so they diverge NFC vs NFD by design and are an explicit, documented allowlist the
audit skips. `FORM_PRESERVING` is reviewed so a new recovery entrypoint defaults to
*in*-scope (a new name is audited unless it is added here on purpose).

Until `transliterate` normalizes at the boundary, the audit FAILS on the family it
roots: `transliterate`, `unidecode`, and every `slugify*` (nine entrypoints).
"""

from __future__ import annotations

import inspect
import unicodedata
import warnings

import pytest

import disarm

# Homoglyph / accented letters whose NFD differs from NFC (base + combining mark).
SAMPLE = [chr(c) for c in (0x0457, 0x00E7, 0x03AF, 0x0625, 0x00EF, 0x00E9, 0x0107, 0x00FC)]
FORMS = ("NFC", "NFD", "NFKD")

# Decision (b): form-PRESERVING str->str entrypoints — a targeted strip/fold, not
# canonicalization, so form-variance is by design. Explicit so the audit stays an
# allowlist (a new entrypoint is in-scope unless deliberately added here).
FORM_PRESERVING = {
    "fold_case",
    "casefold",
    "strip_bidi",
    "strip_tags",
    "strip_pua",
    "strip_variation_selectors",
    "strip_noncharacters",
    "collapse_whitespace",
    "escape_html",
    "strip_log_injection",
    "demojize",
    "strip_format",
    "display_clean",
}


def _str_to_str_entrypoints() -> list[tuple[str, object]]:
    """Public callables: first param ``text``, callable with text alone, returning
    ``str``. Enumerated from ``disarm.__all__`` so new entrypoints are covered."""
    out = []
    for name in disarm.__all__:
        obj = getattr(disarm, name)
        if inspect.isclass(obj) or not callable(obj):
            continue
        try:
            sig = inspect.signature(obj)
        except (TypeError, ValueError):
            continue
        params = list(sig.parameters.values())
        if not params or params[0].name != "text":
            continue
        if any(
            p.default is inspect.Parameter.empty
            and p.kind in (p.POSITIONAL_OR_KEYWORD, p.POSITIONAL_ONLY, p.KEYWORD_ONLY)
            for p in params[1:]
        ):
            continue
        if sig.return_annotation not in ("str", str):
            continue
        out.append((name, obj))
    return out


_AUDITED = [(n, f) for (n, f) in _str_to_str_entrypoints() if n not in FORM_PRESERVING]


@pytest.mark.parametrize("name,fn", _AUDITED, ids=[n for n, _ in _AUDITED])
def test_recovery_entrypoint_is_form_invariant(name: str, fn: object) -> None:
    """Every public str->str recovery entrypoint (not on the allowlist) is invariant
    to its input's normal form. Self-guarding: a new one is audited automatically."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        for ch in SAMPLE:
            outs = {fn(unicodedata.normalize(f, ch)) for f in FORMS}
            assert len(outs) == 1, f"{name} not form-invariant on {ch!r}: {outs}"


def test_allowlist_members_exist_and_are_str_to_str() -> None:
    """Guard the allowlist: every name on it is a real public str->str entrypoint, so
    it can't silently exempt a recovery entrypoint by typo or drift."""
    names = {n for n, _ in _str_to_str_entrypoints()}
    missing = FORM_PRESERVING - names
    assert not missing, f"FORM_PRESERVING names not public str->str entrypoints: {missing}"


# ── Family-wide regression on the transliterate root (#477) ──
#
# `transliterate` composes each base + combining-mark cluster at the boundary, and
# `unidecode` / every `slugify*` funnel through it (the Unicode-preserving
# `slugify_unicode` composes on its own path). The oracle below is the one the #477
# review named: for every member and a broad input set, lookup(NFC) == lookup(NFD),
# over (a) the canonical-divergence sweep across the BMP recovery range and (b) a
# multi-mark generator that a single base+mark shortcut would miss.

TRANSLIT_FAMILY = ["transliterate", "unidecode", "slugify", "slugify_unicode", "slugify_url"]

# Precomposed scalars whose NFD is a base + *two or more* combining marks — the case a
# one-mark compose stops short on. Vietnamese (dot-below + circumflex/horn) and
# polytonic Greek (breathing/iota-subscript + tonos) exercise full-cluster composition.
MULTI_MARK = [
    "ệ",  # U+1EC7 e + ◌̣ (U+0323) + ◌̂ (U+0302)
    "ộ",  # U+1ED9
    "ự",  # U+1EF1 u + ◌̣ + horn
    "ặ",  # U+1EB7
    "ᾷ",  # U+1FB7 α + ◌͂ (U+0342) + ◌ͅ (U+0345)
    "ῷ",  # U+1FF7 ω + perispomeni + ypogegrammeni
    "ᾅ",  # U+1F85
    "ῇ",  # U+1FC7
]


def _nfc_nfd(ch: str) -> tuple[str, str]:
    return unicodedata.normalize("NFC", ch), unicodedata.normalize("NFD", ch)


@pytest.mark.parametrize("name", TRANSLIT_FAMILY)
def test_transliterate_family_multimark_form_invariant(name: str) -> None:
    """Full-cluster composition: a base + two marks must reach the precomposed scalar,
    so NFC and NFD agree on Vietnamese and polytonic-Greek multi-mark letters."""
    fn = getattr(disarm, name)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        for ch in ["ї", *MULTI_MARK]:
            nfc, nfd = _nfc_nfd(ch)
            assert fn(nfc) == fn(nfd), f"{name} diverges NFC vs NFD on {ch!r} (U+{ord(ch):04X})"


@pytest.mark.parametrize("name", ["transliterate", "unidecode", "slugify", "slugify_unicode"])
def test_transliterate_family_divergence_sweep(name: str) -> None:
    """Breadth oracle: across the BMP recovery range, every code point whose NFC and
    NFD differ must transliterate/slugify identically — the compose-at-lookup boundary
    leaves no canonical-divergence gap (the same sweep that pins `normalize_confusables`
    in test_confusables_form_invariance, now extended to the family transliterate roots)."""
    fn = getattr(disarm, name)
    diverging = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        for cp in range(0x80, 0x2500):
            ch = chr(cp)
            nfc, nfd = _nfc_nfd(ch)
            if nfc == nfd:
                continue
            if fn(nfc) != fn(nfd):
                diverging.append(cp)
    assert diverging == [], f"{name}: {len(diverging)} code points diverge NFC vs NFD"


# ── #481: the raw-vs-normalized residual, now CLOSED via build-time tables ──
#
# #480 made the blind spot visible: the audit above compares the normal forms against
# each other and never against the raw precomposed input, so a composition-excluded
# singleton (raw क़ U+0958 -> "qa"; every normal form KA+nukta -> "ka") passed green.
# #481 closes it with two build-time tables and no runtime canonicalization pass:
#   * base+mark composition exclusions -> the compose-at-lookup widening map (KA+nukta ->
#     QA, shin+sin-dot -> U+FB2B, Tibetan, the Hebrew presentation forms);
#   * the two real confusable singletons U+1F77 / U+1F79 (Greek oxia) -> fold rows.
# So f(raw) == f(NFC) == f(NFD) == f(NFKD) now holds for the transliterate family and for
# confusable detection, modulo a small, characterized, deliberately-accepted tail.


def _all_forms(ch: str) -> list[str]:
    return [unicodedata.normalize(f, ch) for f in FORMS] + [ch]  # NFC, NFD, NFKD, raw


def _excluded_singletons(hi: int = 0x110000) -> list[str]:
    """Composition-excluded code points: NFC differs from the raw scalar (a singleton or
    excluded canonical decomposition NFC does not recompose). Full range by default so the
    closure assertions also cover the SMP (e.g. musical symbols)."""
    return [
        chr(c) for c in range(0x20, hi) if (ch := chr(c)) and unicodedata.normalize("NFC", ch) != ch
    ]


# The accepted transliterate tail: two Greek accent-PUNCTUATION code points, not letters
# or homoglyphs. U+1FEE GREEK DIALYTIKA AND OXIA has an irreducible NFC-vs-NFKD
# *compatibility* split (its target U+0385 itself NFKD-decomposes to space+marks). U+1FFD
# GREEK OXIA carries a curated "x" placeholder row in translit_default.tsv that we honor
# rather than override; it is recoverable by correcting that one row.
TRANSLIT_TAIL = frozenset({0x1FEE, 0x1FFD})


# The ASCII-output romanizers: these collapse a singleton and its canonical target to
# the same ASCII, so raw-vs-normalized closure is byte-exact. `slugify_unicode` is NOT
# here — it *preserves* Unicode, so it re-encodes the ~1,027 benign passthrough singletons
# (U+1F71 vs U+03AC, the same Greek letter) exactly like the confusables fold; it is
# covered by the canonical-equivalence test below, not byte equality.
ASCII_ROMANIZERS = ["transliterate", "unidecode", "slugify", "slugify_url"]


@pytest.mark.parametrize("name", ASCII_ROMANIZERS)
def test_transliterate_family_raw_vs_normalized_closed(name: str) -> None:
    """Raw-inclusive closure: f(raw) == f(NFC) == f(NFD) == f(NFKD) for every excluded
    singleton, except the two documented Greek-punctuation tail code points. A regression
    that reopens the gap (or degrades a new code point) fails here."""
    fn = getattr(disarm, name)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        residual = {
            ord(c) for c in _excluded_singletons() if len({fn(f) for f in _all_forms(c)}) != 1
        }
    # The transliterate engine roots the family, so its tail is the family tail; the slug
    # variants may collapse the punctuation further (subset), never add to it.
    assert residual <= set(TRANSLIT_TAIL), (
        f"{name} reopened the gap: {sorted(hex(cp) for cp in residual - TRANSLIT_TAIL)}"
    )


# `slugify_unicode` preserves Unicode, so on top of the transliterate tail it strips a
# few raw Greek accent/question marks differently from their normalized form (U+037E ;,
# U+1FEF grave, U+1FEE, U+1FFD) — all punctuation, not letters. Pinned as the slug tail.
SLUGIFY_UNICODE_TAIL = frozenset({0x037E, 0x1FEE, 0x1FEF, 0x1FFD})


def test_slugify_unicode_raw_vs_normalized_canonically_equivalent() -> None:
    """`slugify_unicode` preserves Unicode, so a singleton and its canonical target slug
    to different *bytes* but the same abstract text. Assert the slug is form-invariant up
    to canonical equivalence (NFC of the outputs agrees) over every excluded singleton,
    except the documented punctuation tail."""
    residual = {
        ord(c)
        for c in _excluded_singletons()
        if len({unicodedata.normalize("NFC", disarm.slugify_unicode(f)) for f in _all_forms(c)})
        != 1
    }
    assert residual == set(SLUGIFY_UNICODE_TAIL), (
        f"slugify_unicode tail changed: added {sorted(hex(cp) for cp in residual - SLUGIFY_UNICODE_TAIL)}, "
        f"removed {sorted(hex(cp) for cp in SLUGIFY_UNICODE_TAIL - residual)}"
    )


def test_transliterate_excluded_singleton_now_recovers() -> None:
    """The headline case is closed: Devanagari QA and Hebrew shin-with-sin-dot recover
    identically across raw and every normal form (KA+nukta -> "qa", not the old "ka")."""
    for ch, want in (("क़", "qa"), ("שׂ", "s")):  # QA, SHIN WITH SIN DOT
        assert ch != unicodedata.normalize("NFD", ch), f"{ch!r} must decompose"
        outs = {disarm.transliterate(f) for f in _all_forms(ch)}
        assert outs == {want}, f"{ch!r} not form-invariant: {outs}"


# The accepted detection tail: is_confusable is form-invariant except where the raw
# precomposed character *is itself* the spoof and normalization resolves it to the genuine
# character — Kelvin U+212A -> "K", Greek question mark U+037E -> ";" (raw=True,
# normalized=False) — plus U+1FFD, whose NFKD compatibility split (-> space+acute) is not
# a confusable. These cannot be "fixed" without un-detecting the raw spoof.
IS_CONFUSABLE_DETECTION_TAIL = frozenset({0x037E, 0x212A, 0x1FFD})


def test_is_confusable_detection_form_invariant() -> None:
    """Detection is the load-bearing confusables property (a fold of look-alikes, not a
    normalizer): is_confusable must not depend on normal form, except the documented
    spoof-resolution tail. The raw=False->normalized=True evasions #480 pinned (Greek oxia,
    Hebrew presentation forms) are now closed by the widening map and the U+1F77/U+1F79
    fold rows."""
    flips = {
        ord(c)
        for c in _excluded_singletons()
        if len({disarm.is_confusable(f) for f in _all_forms(c)}) != 1
    }
    assert flips == set(IS_CONFUSABLE_DETECTION_TAIL), (
        f"is_confusable flips changed: added {sorted(hex(c) for c in flips - IS_CONFUSABLE_DETECTION_TAIL)}, "
        f"removed {sorted(hex(c) for c in IS_CONFUSABLE_DETECTION_TAIL - flips)}"
    )


def test_normalize_confusables_fold_is_form_invariant() -> None:
    """The fold is form-invariant where it matters. normalize_confusables is a targeted
    fold, not a normalizer, so a non-confusable re-encodes freely (U+1F71 alpha-with-oxia
    vs U+03AC alpha-with-tonos — the ~1,027 benign passthroughs, neither a Latin
    confusable). The guard is therefore on detection + fold: where a code point IS a
    confusable in some form, its folded output must agree across forms up to canonical
    equivalence — except the documented spoof-resolution tail."""
    for c in _excluded_singletons():
        if ord(c) in IS_CONFUSABLE_DETECTION_TAIL:
            continue  # spoof-resolution: detection itself diverges, asserted above
        forms = _all_forms(c)
        if not any(disarm.is_confusable(f) for f in forms):
            continue  # benign passthrough — not a confusable in any form, may re-encode
        nfc_outs = {unicodedata.normalize("NFC", disarm.normalize_confusables(f)) for f in forms}
        assert len(nfc_outs) == 1, f"confusable fold diverges by form on U+{ord(c):04X}: {nfc_outs}"
