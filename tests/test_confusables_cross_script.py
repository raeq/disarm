"""Cross-script confusable folding — #341, #342, #343 (all carved from #336).

These three close the cross-script gaps where ``normalize_confusables`` either
left non-ASCII residue (#341) or returned the source unchanged so a spoof never
collided with its target (#342/#343):

- #341  TR39 folds ~140 sources onto a non-ASCII Latin-extended prototype
        (ĸ/ꞓ/ß/…). We fold those to basic ASCII so a Greek κ collides with k.
- #342  Seven additive Greek/Cyrillic pairs gain a shared latin/cyrillic fold.
- #343  The bare Greek iota ι is re-pointed from the i-class to the l /
        vertical-bar class so {ι, ӏ, ا} unify.

Inputs use the literal glyphs (the codepoint is named in comments) so a reviewer
can see the visual confusable under test.
"""

from __future__ import annotations

import pytest

from disarm import normalize_confusables as nc


def _nc(c: str, target: str = "latin") -> str:
    return nc(c, target_script=target)


# ---------------------------------------------------------------------------
# #341 — non-ASCII Latin-extended prototypes fold to basic ASCII
# ---------------------------------------------------------------------------


class TestAsciiFold341:
    @pytest.mark.parametrize(
        ("src", "expected"),
        [
            ("κ", "k"),  # κ kappa  (was ĸ U+0138 kra)
            ("ε", "e"),  # ε epsilon (was ꞓ U+A793 c-with-bar; #336 → e)
            ("β", "b"),  # β beta    (was ß U+00DF sharp s; #336 → b)
            ("ɛ", "e"),  # ɛ latin open e
            ("є", "e"),  # є cyrillic ukrainian ie
        ],
    )
    def test_source_folds_to_ascii(self, src: str, expected: str) -> None:
        out = _nc(src)
        assert out == expected, f"{src!r} → {out!r}, expected {expected!r}"
        assert out.isascii(), f"{src!r} → {out!r} is not ASCII"

    def test_greek_latin_collision(self) -> None:
        # The whole point of #341: a Greek spoof collides with its ASCII twin.
        assert _nc("κ") == _nc("k") == "k"  # κ == k
        assert _nc("ε") == _nc("e") == "e"  # ε == e
        assert _nc("β") == _nc("b") == "b"  # β == b

    def test_idempotent(self) -> None:
        for c in ("κ", "ε", "β", "ɛ"):
            once = _nc(c)
            assert _nc(once) == once

    def test_sigma_folds_to_s(self) -> None:
        # esh is no longer residue (#341): TR39's sigma/summation skeleton (esh)
        # folds to ASCII. Capital Σ → S (see TestGreekSigmaFoldsToS).
        out = _nc("Σ")
        assert out == "S" and out.isascii(), f"Σ → {out!r}"


# ---------------------------------------------------------------------------
# #342 — seven additive Greek/Cyrillic pairs collide on a shared representative
# ---------------------------------------------------------------------------

# (A, B, shared latin) — A is the gap that #342 fills; B already folded there.
PAIRS_342 = [
    ("ί", "і", "i"),  # ί / і  (pair 1)
    ("п", "η", "n"),  # п / η  (pair 5)
    ("χ", "х", "x"),  # χ / х  (pair 8)
    ("ω", "ѡ", "w"),  # ω / ѡ  (pair 9)
    ("ό", "о", "o"),  # ό / о  (pair 11)
    ("ѻ", "ο", "o"),  # ѻ / ο  (pair 13)
]


class TestAdditivePairs342:
    @pytest.mark.parametrize(("a", "b", "shared"), PAIRS_342)
    def test_latin_closure(self, a: str, b: str, shared: str) -> None:
        assert _nc(a) == shared, f"{a!r} → {_nc(a)!r}, want {shared!r}"
        assert _nc(b) == shared, f"{b!r} → {_nc(b)!r}, want {shared!r}"
        assert shared.isascii()

    def test_iota_dialytika_pair_10(self) -> None:
        # Pair 10: ϊ (U+03CA) and ї (U+0457) were both pass-through; #342 maps
        # both to i so the pair collides.
        assert _nc("ϊ") == "i"
        assert _nc("ї") == "i"

    def test_eta_pe_pi_transitive_class(self) -> None:
        # Transitive closure {η, п, π} → n (π added so the class stays consistent).
        assert _nc("η") == "n"  # η
        assert _nc("п") == "n"  # п
        assert _nc("π") == "n"  # π

    def test_pair2_beta_ve_collision(self) -> None:
        # Pair 2: β (via #341 ß→b) and в (via #342) both reach b → they collide.
        assert _nc("β") == "b"  # β
        assert _nc("в") == "b"  # в
        assert _nc("β") == _nc("в")

    @pytest.mark.parametrize(
        ("a", "b"),
        [
            ("ί", "і"),  # ί / і
            ("χ", "х"),  # χ / х
            ("ϊ", "ї"),  # ϊ / ї
            ("ό", "о"),  # ό / о
            ("ѻ", "ο"),  # ѻ / ο
        ],
    )
    def test_cyrillic_closure(self, a: str, b: str) -> None:
        assert _nc(a, "cyrillic") == _nc(b, "cyrillic")

    def test_cyrillic_additions(self) -> None:
        assert _nc("β", "cyrillic") == "в"  # β → в
        assert _nc("η", "cyrillic") == "п"  # η → п
        assert _nc("ѡ", "cyrillic") == "ꙍ"  # ѡ → ꙍ (matches ω→ꙍ)

    def test_idempotent(self) -> None:
        for a, *_ in PAIRS_342:
            for t in ("latin", "cyrillic"):
                once = _nc(a, t)
                assert _nc(once, t) == once


# ---------------------------------------------------------------------------
# #343 — unify the vertical-bar class ι / ӏ / ا on l (latin) / ӏ (cyrillic)
# ---------------------------------------------------------------------------


class TestVerticalBarClass343:
    BAR = ["ι", "ӏ", "ا"]  # ι (iota), ӏ (palochka), ا (alef)

    @pytest.mark.parametrize("c", BAR)
    def test_latin_l(self, c: str) -> None:
        assert _nc(c) == "l"

    @pytest.mark.parametrize("c", BAR)
    def test_cyrillic_palochka(self, c: str) -> None:
        assert _nc(c, "cyrillic") == "ӏ"  # ӏ

    def test_accented_iotas_still_i(self) -> None:
        # The #342 boundary: the diacritic'd iotas read as i, only the *bare*
        # stroke ι re-points to l. Different codepoints, deliberate split.
        assert _nc("ί") == "i"  # ί iota+tonos
        assert _nc("ϊ") == "i"  # ϊ iota+dialytika

    def test_idempotent(self) -> None:
        for c in self.BAR:
            assert _nc(_nc(c)) == _nc(c)
            assert _nc(_nc(c, "cyrillic"), "cyrillic") == _nc(c, "cyrillic")
