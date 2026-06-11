"""Bug: strip_obfuscation() should not fold case.

Case is not deception — it's information (proper nouns, acronyms,
sentence boundaries). strip_obfuscation removes obfuscation techniques
(homoglyphs, zalgo, invisible chars) but should preserve case.
Callers who want lowercased output chain fold_case() explicitly.
"""

from __future__ import annotations

from disarm import strip_obfuscation


class TestStripObfuscationPreservesCase:
    def test_preserves_proper_noun(self):
        assert strip_obfuscation("PayPal") == "PayPal"

    def test_preserves_uppercase(self):
        assert strip_obfuscation("HELLO WORLD") == "HELLO WORLD"

    def test_preserves_mixed_case(self):
        assert strip_obfuscation("iPhone MacBook") == "iPhone MacBook"

    def test_preserves_acronym(self):
        assert strip_obfuscation("NASA CEO") == "NASA CEO"

    def test_homoglyph_preserves_case(self):
        # Cyrillic а (U+0430) → Latin a (lowercase preserved)
        result = strip_obfuscation("P\u0430yP\u0430l")
        assert result == "PayPal"

    def test_ligature_decomposed_case_preserved(self):
        # NFKC: ﬁ → fi (ligature decomposed, but not case-folded)
        result = strip_obfuscation("ﬁle")
        assert result == "file"
