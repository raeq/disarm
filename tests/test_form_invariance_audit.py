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
