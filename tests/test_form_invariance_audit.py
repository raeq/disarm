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


# ── The raw-vs-normalized blind spot (residual of compose-only design) ──
#
# The audit above compares the normal forms against EACH OTHER and never against the
# raw, un-normalized precomposed input. For a composition-excluded singleton that gap
# is real: the raw scalar carries information its canonical decomposition loses, so the
# raw form recovers differently from EVERY normal form — and the normal forms all agree
# with one another, so the form-invariance audit stays green and cannot see it.
#
# Devanagari QA (U+0958) is the canonical example: raw `क़` transliterates "qa", but its
# decomposition KA (U+0915) + nukta (U+093C) is composition-excluded, so every normal
# form is KA + nukta and degrades to "ka". This is ACCEPTED, not a bug to fix: composing
# an excluded singleton back from its decomposition is exactly the Hebrew `שׂ` U+FB2B
# regression (#477) in another script. The tests below make the residual visible and pin
# it, so it cannot silently grow, and so a regression that degrades a *non-excluded*
# code point (which would be a real bug) fails here.


def _excluded_singletons(hi: int = 0x10000) -> list[str]:
    """Composition-excluded code points: those whose NFC differs from the raw scalar
    (a singleton/excluded canonical decomposition that NFC does not recompose). All the
    residual sets below live in the BMP, so the default range captures them."""
    return [
        chr(c) for c in range(0x20, hi) if (ch := chr(c)) and unicodedata.normalize("NFC", ch) != ch
    ]


# Excluded singletons whose precomposed romanization is richer than their canonical
# decomposition, so raw recovers differently from every normal form: Indic nukta letters
# (Devanagari/Bengali/Gurmukhi/Oriya QA/ZA/FA/RRA…), Tibetan, Greek oxia, and Hebrew
# presentation forms. Pinned exactly (these blocks are long-stable) so the set is a
# precise regression guard, not a moving count.
TRANSLIT_RAW_RESIDUAL = frozenset(
    {
        0x0958,
        0x095B,
        0x095E,
        0x09DC,
        0x09DD,
        0x0A36,
        0x0A5B,
        0x0A5E,
        0x0F43,
        0x0F4D,
        0x0F52,
        0x0F57,
        0x0F5C,
        0x0F69,
        0x0F73,
        0x0F75,
        0x0F76,
        0x0F78,
        0x0F81,
        0x0F93,
        0x0F9D,
        0x0FA2,
        0x0FA7,
        0x0FAC,
        0x0FB9,
        0x1FEE,
        0x1FFD,
        0xFB1D,
        0xFB1F,
        0xFB2B,
        0xFB2D,
        0xFB2E,
        0xFB2F,
        0xFB30,
        0xFB31,
        0xFB35,
        0xFB3A,
        0xFB3B,
        0xFB43,
        0xFB44,
        0xFB4B,
    }
)


def test_transliterate_raw_vs_normalized_residual_is_pinned() -> None:
    """The raw-vs-normalized blind spot the form-invariance audit cannot see: pin the
    exact set of excluded singletons that transliterate differently raw vs normalized."""
    residual = {
        ord(c)
        for c in _excluded_singletons()
        if disarm.transliterate(c) != disarm.transliterate(unicodedata.normalize("NFC", c))
    }
    # Every member must be a composition-excluded singleton — a divergence anywhere else
    # would be a real form-invariance regression, not the accepted residual.
    assert all(unicodedata.normalize("NFC", chr(cp)) != chr(cp) for cp in residual)
    assert residual == set(TRANSLIT_RAW_RESIDUAL), (
        f"transliterate raw-vs-normalized residual changed: "
        f"added {sorted(residual - TRANSLIT_RAW_RESIDUAL)}, "
        f"removed {sorted(TRANSLIT_RAW_RESIDUAL - residual)}"
    )


def test_transliterate_excluded_singleton_representative() -> None:
    """Spell the phenomenon out on Devanagari QA: raw recovers the precomposed letter,
    every normal form decomposes and degrades, and the normal forms agree (so the
    form-invariance audit is green on it)."""
    qa = "क़"  # क़ DEVANAGARI LETTER QA
    assert disarm.transliterate(qa) == "qa"
    assert qa != unicodedata.normalize("NFC", qa), "QA must actually decompose under NFC"
    degraded = {disarm.transliterate(unicodedata.normalize(f, qa)) for f in FORMS}
    assert degraded == {"ka"}, f"every normal form should degrade QA to 'ka', got {degraded}"


# `is_confusable` is also non-invariant raw-vs-NFC for these excluded singletons. Two
# directions, both pinned:
#   raw=True  -> NFC=False  (Kelvin U+212A -> "K", Greek question mark U+037E -> ";"):
#     normalization RESOLVES the look-alike to the genuine character; flagging the raw
#     spoof and not its resolved real form is correct.
#   raw=False -> NFC=True   (Greek oxia, Hebrew presentation forms): the raw precomposed
#     singleton is absent from the TR39 table, but its NFC base is a confusable, so the
#     raw form evades detection. Narrow and low-relevance, and mitigated because the
#     security presets normalize (NFKC) before any confusable check — but real, so pin
#     it rather than let the audit's NFC==NFD==NFKD hide it.
IS_CONFUSABLE_RAW_FLIPS = frozenset(
    {
        0x037E,
        0x1F77,
        0x1F79,
        0x212A,
        0xFB1D,
        0xFB1F,
        0xFB35,
        0xFB38,
        0xFB39,
        0xFB41,
        0xFB4B,
    }
)


def test_is_confusable_raw_vs_normalized_flips_are_pinned() -> None:
    flips = {
        ord(c)
        for c in _excluded_singletons()
        if disarm.is_confusable(c) != disarm.is_confusable(unicodedata.normalize("NFC", c))
    }
    assert all(unicodedata.normalize("NFC", chr(cp)) != chr(cp) for cp in flips)
    assert flips == set(IS_CONFUSABLE_RAW_FLIPS), (
        f"is_confusable raw-vs-NFC flips changed: "
        f"added {sorted(flips - IS_CONFUSABLE_RAW_FLIPS)}, "
        f"removed {sorted(IS_CONFUSABLE_RAW_FLIPS - flips)}"
    )


def test_normalize_confusables_raw_divergence_is_bounded_to_excluded_singletons() -> None:
    """`normalize_confusables` output also differs raw-vs-NFC (~1,114 code points over
    the full range), but it is a *targeted fold*, not a normalizer: it leaves a
    non-confusable in whatever form it arrived, so raw `क़` U+0958 stays U+0958 while NFC
    is KA + nukta — different bytes, neither a fold. The security-relevant subset is the
    detection flips pinned above. Assert here that every raw-vs-NFC output divergence is
    confined to composition-excluded singletons, so no *non-excluded* code point folds
    form-dependently (which would be a real evasion)."""
    divergent = [
        c
        for c in _excluded_singletons()
        if disarm.normalize_confusables(c)
        != disarm.normalize_confusables(unicodedata.normalize("NFC", c))
    ]
    assert divergent, "expected a non-empty residual — the blind spot is real"
    assert all(unicodedata.normalize("NFC", c) != c for c in divergent)
