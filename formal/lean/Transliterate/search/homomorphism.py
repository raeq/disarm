"""Premise H (homomorphism): is  f(a + b) == f(a) + f(b)  for the real `transliterate`?

The lift in `docs/formal-verification.md` ("a character-wise map that emits ASCII
for every character is ASCII for every string") needs f to be a monoid
homomorphism over code points. This script searches for counterexamples over
exhaustive small domains (pairs, and triples where context spans three
characters) and large random samples, under every relevant option profile, and
classifies each counterexample by the mechanism that caused it.

For every pair or triple it also checks the string-level invariants directly:
I2 (ASCII output under errors='ignore') and I3 (f(f(s)) == f(s)).

Run:  python3 homomorphism.py [--quick] [--json out.json]
"""

from __future__ import annotations

import argparse
import itertools
import random
import time
import unicodedata
from dataclasses import replace

from common import Opts, Tally, block, dump, pairs, sample

# ── Domains ──────────────────────────────────────────────────────────────────

LATIN_BASES = [chr(c) for c in range(0x41, 0x5B)] + [chr(c) for c in range(0x61, 0x7B)]
LATIN_BASES += block(0x00C0, 0x00FF) + block(0x0100, 0x017F)
MARKS = block(0x0300, 0x036F)  # Combining Diacritical Marks
GREEK = block(0x0370, 0x03FF) + block(0x1F00, 0x1FFF)
CYRILLIC = block(0x0400, 0x04FF)
KANA = block(0x3040, 0x30FF) + block(0xFF65, 0xFF9F)
DEVANAGARI = block(0x0900, 0x097F)
BENGALI = block(0x0980, 0x09FF)
TAMIL = block(0x0B80, 0x0BFF)
THAI_LAO = block(0x0E00, 0x0EFF)
ARABIC = block(0x0600, 0x06FF)
HEBREW = block(0x0590, 0x05FF)
HANGUL_L = block(0x1100, 0x1112)
HANGUL_V = block(0x1161, 0x1175)
HANGUL_T = block(0x11A8, 0x11C2)
HANGUL_COMPAT = block(0x3131, 0x318E)
CJK = sample(block(0x4E00, 0x9FFF), 150, seed=1)
DIGITS = [c for c in map(chr, range(0x10000)) if unicodedata.category(c) == "Nd"]
ASCII_PRINT = [chr(c) for c in range(0x20, 0x7F)]
NFKC_SENSITIVE = [c for c in block(0x00A0, 0xFFFF) if unicodedata.normalize("NFKC", c) != c]
BMP_ASSIGNED = block(0x0080, 0xFFFF)


def indic_role_guess(c: str) -> str:
    """Coarse role from the UCD category (for classification only)."""
    name = unicodedata.name(c, "")
    if "VIRAMA" in name or "HALANT" in name or "AL-LAKUNA" in name:
        return "virama"
    if "VOWEL SIGN" in name:
        return "matra"
    if "LETTER" in name and unicodedata.category(c) == "Lo":
        return "letter"
    return "other"


def classify(opts: Opts, a: str, b: str, fab: str, fa: str, fb: str) -> str:
    """Name the mechanism behind f(a+b) != f(a)+f(b)."""
    cat = fa + fb
    if fab.replace(" ", "") == cat.replace(" ", "") and fab.count(" ") > cat.count(" "):
        return "cjk_spacing"
    if indic_role_guess(b[:1]) in ("virama", "matra") and fa.endswith("a") and fab == fa[:-1] + fb:
        return "indic_inherent_a"
    if opts.lang == "auto":
        plain = replace(opts, lang=None)
        if plain.f(a + b) == plain.f(a) + plain.f(b):
            return "auto_lang_detection"
    norm = unicodedata.normalize
    if norm("NFD", a + b) != norm("NFD", a) + norm("NFD", b):
        return "canonical_reordering"
    if len(norm("NFC", a + b)) < len(a + b) or norm("NFC", a) != a:
        return "composition"
    if unicodedata.category(b[:1]) in ("Mn", "Mc") and len(norm("NFD", b)) > 1:
        return "composition"  # a decomposing mark (U+0344 ...) recomposes with the base
    if unicodedata.category(b[:1]) in ("Mn", "Mc"):
        return "composition_widened"  # compose-at-lookup toward an excluded composite (#477)
    return "other"


# ── Checks ───────────────────────────────────────────────────────────────────


class Checker:
    def __init__(self) -> None:
        self.hom = Tally(keep=4)
        self.i2 = Tally(keep=4)
        self.i3 = Tally(keep=4)
        self.cache: dict[tuple[Opts, str], str] = {}

    def f(self, opts: Opts, s: str) -> str:
        key = (opts, s)
        r = self.cache.get(key)
        if r is None:
            r = opts.f(s)
            if len(s) <= 1:
                self.cache[key] = r
        return r

    def check(self, opts: Opts, parts: tuple[str, ...], domain: str) -> None:
        s = "".join(parts)
        fs = self.f(opts, s)
        images = [self.f(opts, p) for p in parts]
        cat = "".join(images)
        if fs == cat:
            self.hom.ok()
        else:
            if len(parts) == 2:
                why = classify(opts, parts[0], parts[1], fs, images[0], images[1])
            else:
                why = "triple"
            self.hom.fail(
                f"{domain} | {opts.label()} | {why}",
                {"input": s, "f(s)": fs, "concat f(c)": cat, "call": opts.call_repr(s)},
            )
        if opts.errors == "ignore":
            if fs.isascii():
                self.i2.ok()
            else:
                self.i2.fail(
                    f"{domain} | {opts.label()}",
                    {"input": s, "f(s)": fs, "call": opts.call_repr(s)},
                )
        ffs = opts.f(fs)
        if ffs == fs:
            self.i3.ok()
        else:
            self.i3.fail(
                f"{domain} | {opts.label()}",
                {"input": s, "f(s)": fs, "f(f(s))": ffs, "call": opts.call_repr(s)},
            )


def run(quick: bool) -> dict:
    ck = Checker()
    E = ("ignore",) if quick else ("ignore", "replace", "preserve")

    def P(*langs: str | None, iso: bool = False, tones: bool = False) -> list[Opts]:
        out = []
        for e in E:
            for lg in langs:
                out.append(Opts(lg, e, tones=tones))
            if iso:
                out.append(Opts(None, e, strict_iso9=True))
                out.append(Opts(None, e, gost7034=True))
        return out

    domains: list[tuple[str, list[Opts], object]] = [
        (
            "latin_base x mark",
            P(None, "auto", "de", "vi", "fr", "tr"),
            lambda: pairs(LATIN_BASES, MARKS),
        ),
        ("mark x mark", P(None), lambda: pairs(MARKS)),
        ("greek x greek", P(None, "auto", "el"), lambda: pairs(GREEK)),
        (
            "cyrillic x cyrillic",
            P(None, "auto", "ru", "uk", "bg", "sr", "mn", iso=True),
            lambda: pairs(CYRILLIC),
        ),
        ("cyrillic x mark", P(None, "ru", "uk", iso=True), lambda: pairs(CYRILLIC, MARKS)),
        ("kana x kana", P(None, "auto", "ja", "ja-kunrei"), lambda: pairs(KANA)),
        (
            "devanagari x devanagari",
            P(None, "auto", "hi", "mr", "ne", "sa"),
            lambda: pairs(DEVANAGARI),
        ),
        ("bengali x bengali", P(None, "bn", "as"), lambda: pairs(BENGALI)),
        ("tamil x tamil", P(None, "ta"), lambda: pairs(TAMIL)),
        ("thai/lao x thai/lao", P(None, "auto", "th", "lo"), lambda: pairs(THAI_LAO)),
        ("arabic x arabic", P(None, "auto", "ar", "fa"), lambda: pairs(ARABIC)),
        ("hebrew x hebrew", P(None, "auto", "he"), lambda: pairs(HEBREW)),
        ("hangul L x V", P(None, "ko"), lambda: pairs(HANGUL_L, HANGUL_V)),
        (
            "hangul L x V x T",
            P(None, "ko"),
            lambda: itertools.product(HANGUL_L, HANGUL_V, HANGUL_T),
        ),
        ("hangul compat x compat", P(None, "ko"), lambda: pairs(HANGUL_COMPAT)),
        (
            "cjk x cjk",
            P(None, "auto", "zh", "ja", tones=False) + P(None, tones=True),
            lambda: pairs(CJK),
        ),
        (
            "cjk x ascii",
            P(None, "zh") + P(None, tones=True),
            lambda: itertools.chain(pairs(CJK, ASCII_PRINT), pairs(ASCII_PRINT, CJK)),
        ),
        ("digit x digit", P(None, "auto", "ar", "fa", "hi", "bn", "th"), lambda: pairs(DIGITS)),
        ("nfkc-sensitive x mark", P(None), lambda: pairs(NFKC_SENSITIVE, MARKS[:16])),
        ("nfkc-sensitive x ascii", P(None), lambda: pairs(NFKC_SENSITIVE, list("a1 "))),
    ]
    rng = random.Random(7)
    n_random = 50_000 if quick else 400_000
    rand_pairs = [(rng.choice(BMP_ASSIGNED), rng.choice(BMP_ASSIGNED)) for _ in range(n_random)]
    domains.append(("random bmp pairs", P(None, "auto"), lambda: iter(rand_pairs)))
    domains.append(
        (
            "random bmp pairs",
            [Opts(None, "ignore", tones=True), Opts(None, "ignore", strict_iso9=True)],
            lambda: iter(rand_pairs),
        )
    )

    per_domain = {}
    for name, profs, gen in domains:
        t0 = time.time()
        before = ck.hom.checked
        for opts in profs:
            for parts in gen():  # type: ignore[operator]
                ck.check(opts, tuple(parts), name)
        per_domain[name] = per_domain.get(name, 0) + ck.hom.checked - before
        print(
            f"{name:28s} {ck.hom.checked - before:>10,d} checks  {time.time() - t0:6.1f}s",
            flush=True,
        )

    return {
        "per_domain_checks": per_domain,
        "homomorphism": ck.hom.to_json(),
        "I2_string_level": ck.i2.to_json(),
        "I3_string_level": ck.i3.to_json(),
    }


def summarize(res: dict) -> None:
    for key in ("homomorphism", "I2_string_level", "I3_string_level"):
        r = res[key]
        total_fail = sum(r["failures"].values())
        print(f"\n== {key}: {r['checked']:,} checked, {total_fail:,} counterexamples")
        by_cause: dict[str, int] = {}
        for k, v in r["failures"].items():
            cause = k.split(" | ")[-1] if key == "homomorphism" else k.split(" | ")[1]
            by_cause[cause] = by_cause.get(cause, 0) + v
        for cause, v in sorted(by_cause.items(), key=lambda kv: -kv[1])[:40]:
            print(f"   {v:>9,d}  {cause}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    res = run(a.quick)
    summarize(res)
    if a.json:
        dump(res, a.json)
