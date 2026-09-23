"""Every public surface in scope, by name, for the library-only sweeps."""

from __future__ import annotations

import functools

import disarm


def _mk() -> dict:
    s = {}
    for pol in ("numeric", "tr39", "preserve"):
        sfx = "" if pol == "numeric" else "@" + pol
        for name in (
            "canonicalize",
            "canonicalize_strict",
            "strip_obfuscation",
            "search_key",
            "catalog_key",
            "sort_key",
            "skeleton_key",
        ):
            s[name + sfx] = functools.partial(getattr(disarm, name), digit_policy=pol)
    s["strip_format"] = disarm.strip_format
    s["ml_normalize"] = disarm.ml_normalize
    s["ml_normalize@nofold"] = functools.partial(disarm.ml_normalize, fold_case=False)
    s["ml_normalize@none"] = functools.partial(disarm.ml_normalize, emoji="none")
    s["sanitize_filename"] = disarm.sanitize_filename
    for p in disarm.list_profiles():
        s["profile:" + p] = disarm.get_pipeline(p)
    for p in ("llm_guardrail", "normalize_web_input", "library_catalog_key_eu"):
        s["profile:" + p + "@tr39"] = disarm.get_pipeline(p, digit_policy="tr39")
    return s


SURFACES = _mk()
