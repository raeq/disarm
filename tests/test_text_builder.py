"""Tests for the fluent Text builder API."""

import disarm
from disarm import Text
from disarm._enums import Script


class TestTextConstruction:
    """Construction, extraction, and dunder methods."""

    def test_from_string(self) -> None:
        t = Text("hello")
        assert t.value == "hello"

    def test_str_extraction(self) -> None:
        assert str(Text("hello")) == "hello"

    def test_repr_short(self) -> None:
        assert repr(Text("hi")) == "Text('hi')"

    def test_repr_truncation(self) -> None:
        long = "a" * 60
        r = repr(Text(long))
        assert "..." in r
        assert len(r) < 60

    def test_eq_text(self) -> None:
        assert Text("abc") == Text("abc")
        assert Text("abc") != Text("xyz")

    def test_eq_str(self) -> None:
        assert Text("abc") == "abc"
        assert Text("abc") != "xyz"

    def test_eq_other_type(self) -> None:
        assert Text("123") != 123

    def test_hash(self) -> None:
        """Text with same value should hash the same (usable in sets/dicts)."""
        assert hash(Text("abc")) == hash(Text("abc"))
        s = {Text("a"), Text("a"), Text("b")}
        assert len(s) == 2

    def test_len(self) -> None:
        assert len(Text("hello")) == 5
        assert len(Text("")) == 0
        assert len(Text("café")) == 4

    def test_bool(self) -> None:
        assert bool(Text("x"))
        assert not bool(Text(""))

    def test_empty_string(self) -> None:
        t = Text("")
        assert t.value == ""
        assert str(t) == ""
        assert len(t) == 0


class TestChainableTransforms:
    """Each transform method returns a new Text and produces correct output."""

    def test_normalize(self) -> None:
        # e + combining acute → é
        t = Text("caf\u0065\u0301").normalize(form="NFC")
        assert t.value == "caf\u00e9"

    def test_normalize_nfkc(self) -> None:
        # ﬁ ligature → fi
        assert Text("\ufb01").normalize(form="NFKC").value == "fi"

    def test_normalize_confusables(self) -> None:
        # Cyrillic а → Latin a
        assert Text("\u0430").normalize_confusables().value == "a"

    def test_strip_accents(self) -> None:
        assert Text("café").strip_accents().value == "cafe"
        assert Text("naïve").strip_accents().value == "naive"

    def test_transliterate(self) -> None:
        assert Text("café").transliterate().value == "cafe"
        assert Text("Москва").transliterate().value == "Moskva"

    def test_transliterate_with_lang(self) -> None:
        assert Text("München").transliterate(lang="de").value == "Muenchen"
        assert Text("Київ").transliterate(lang="uk").value == "Kyiv"

    def test_transliterate_errors_ignore(self) -> None:
        # U+20000 (CJK Extension B) has no mapping in our tables
        result = Text("\U00020000").transliterate(errors="ignore").value
        assert "\U00020000" not in result

    def test_transliterate_errors_preserve(self) -> None:
        # U+20000 (CJK Extension B) has no mapping in our tables
        result = Text("\U00020000").transliterate(errors="preserve").value
        assert "\U00020000" in result

    def test_fold_case(self) -> None:
        assert Text("Straße").fold_case().value == "strasse"
        assert Text("HELLO").fold_case().value == "hello"

    def test_collapse_whitespace(self) -> None:
        assert Text("hello   world").collapse_whitespace().value == "hello world"
        assert Text("  a  b  ").collapse_whitespace().value == "a b"

    def test_slugify(self) -> None:
        result = Text("Hello World").slugify().value
        assert result == "hello-world"

    def test_slugify_with_options(self) -> None:
        result = Text("Hello World").slugify(separator="_", lowercase=False).value
        assert result == "Hello_World"

    def test_sanitize_filename(self) -> None:
        result = Text("hello/world: test").sanitize_filename().value
        assert "/" not in result
        assert ":" not in result


class TestChaining:
    """Multi-step chains and ordering."""

    def test_two_step_chain(self) -> None:
        result = Text("café").normalize(form="NFC").transliterate().value
        assert result == "cafe"

    def test_three_step_chain(self) -> None:
        result = Text("  Héllo   Wörld  ").transliterate().fold_case().collapse_whitespace().value
        assert result == "hello world"

    def test_full_pipeline_chain(self) -> None:
        result = (
            Text("  Héllo   Straße  ")
            .normalize(form="NFKC")
            .transliterate(lang="de")
            .fold_case()
            .collapse_whitespace()
            .value
        )
        assert result == "hello strasse"

    def test_confusables_then_transliterate(self) -> None:
        # Cyrillic а (U+0430) → Latin a, then transliterate is a no-op
        result = Text("\u0430bc").normalize_confusables().transliterate().value
        assert result == "abc"

    def test_normalize_then_strip_accents(self) -> None:
        # NFD decomposes, strip_accents removes combining marks
        result = Text("café").normalize(form="NFD").strip_accents().value
        assert result == "cafe"

    def test_chain_to_slug(self) -> None:
        result = Text("Héllo Wörld").transliterate().slugify().value
        assert result == "hello-world"


class TestImmutability:
    """Each method returns a NEW Text; the original is unchanged."""

    def test_transliterate_does_not_mutate(self) -> None:
        original = Text("café")
        transliterated = original.transliterate()
        assert original.value == "café"
        assert transliterated.value == "cafe"

    def test_fold_case_does_not_mutate(self) -> None:
        original = Text("HELLO")
        folded = original.fold_case()
        assert original.value == "HELLO"
        assert folded.value == "hello"

    def test_branching(self) -> None:
        """Two chains from the same base produce independent results."""
        base = Text("Héllo").normalize(form="NFC")
        branch_a = base.transliterate().value
        branch_b = base.fold_case().value
        assert branch_a == "Hello"
        assert branch_b == "héllo"
        assert base.value == "Héllo"


class TestPredicates:
    """Non-chaining predicate methods."""

    def test_is_ascii(self) -> None:
        assert Text("hello").is_ascii()
        assert not Text("café").is_ascii()

    def test_is_normalized_nfc(self) -> None:
        assert Text("café").is_normalized(form="NFC")
        assert not Text("caf\u0065\u0301").is_normalized(form="NFC")

    def test_is_confusable(self) -> None:
        assert Text("\u0430").is_confusable()  # Cyrillic а
        assert not Text("hello").is_confusable()

    def test_is_mixed_script(self) -> None:
        assert Text("hello мир").is_mixed_script()
        assert not Text("hello world").is_mixed_script()

    def test_detect_scripts(self) -> None:
        scripts = Text("hello Москва").detect_scripts()
        assert Script.LATIN in scripts
        assert Script.CYRILLIC in scripts

    def test_detect_scripts_empty(self) -> None:
        assert Text("").detect_scripts() == []

    def test_predicates_after_chain(self) -> None:
        """Predicates work on the transformed text, not the original."""
        t = Text("café").transliterate()
        assert t.is_ascii()
        assert not Text("café").is_ascii()


class TestEdgeCases:
    """Edge cases and special inputs."""

    def test_ascii_passthrough(self) -> None:
        assert Text("hello world").transliterate().value == "hello world"

    def test_empty_through_all_transforms(self) -> None:
        result = (
            Text("")
            .normalize(form="NFC")
            .strip_accents()
            .transliterate()
            .fold_case()
            .collapse_whitespace()
            .value
        )
        assert result == ""

    def test_pure_digits(self) -> None:
        assert Text("12345").transliterate().value == "12345"

    def test_mixed_unicode(self) -> None:
        result = Text("hello café мир").transliterate().value
        assert "cafe" in result
        assert "hello" in result

    def test_coerce_non_string(self) -> None:
        """Text() should accept anything with __str__."""
        t = Text(42)  # type: ignore[arg-type]
        assert t.value == "42"


class TestPipelineMethods:
    """Tests for precompiled pipeline convenience methods."""

    def test_strip_bidi(self) -> None:
        # U+200E = LRM
        assert Text("he\u200ello").strip_bidi().value == "hello"

    def test_security_clean(self) -> None:
        # Fullwidth Ａ → A, collapse whitespace
        result = Text("\uff21  hello").canonicalize().value
        assert "A" in result
        assert "  " not in result

    def test_ml_normalize(self) -> None:
        result = Text("Café").ml_normalize().value
        assert result == "cafe"

    def test_ml_normalize_with_lang(self) -> None:
        result = Text("Straße").ml_normalize(lang="de").value
        assert "strasse" in result

    def test_display_clean(self) -> None:
        result = Text("hello\x00  world").strip_format().value
        assert "\x00" not in result
        assert "  " not in result

    def test_canonicalize_strict(self) -> None:
        # Strips zalgo (excess marks) while preserving the script; matches the
        # module-level preset (parity).
        zalgo = "hé́́́llo"
        assert Text(zalgo).canonicalize_strict().value == disarm.canonicalize_strict(zalgo)
        # Homoglyph folded, bidi removed.
        assert Text("pаypal").canonicalize_strict().value == "paypal"

    def test_strip_obfuscation(self) -> None:
        # Strips accents + homoglyphs, preserves case; matches the module preset.
        assert Text("Cáfé").strip_obfuscation().value == disarm.strip_obfuscation("Cáfé")
        assert Text("Cáfé").strip_obfuscation().value == "Cafe"

    def test_strip_obfuscation_chain(self) -> None:
        # A pipeline method can be followed by further transforms.
        assert Text("Cáfé").strip_obfuscation().fold_case().value == "cafe"

    def test_grapheme_len(self) -> None:
        # Family emoji = 1 grapheme
        family = "\U0001f469\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466"
        assert Text(family).grapheme_len() == 1
        assert Text("hello").grapheme_len() == 5

    def test_pipeline_methods_chain(self) -> None:
        """Pipeline methods can be chained with other transforms."""
        result = Text("  Héllo  ").strip_format().transliterate().value
        assert result == "Hello"

    def test_security_clean_chain(self) -> None:
        """canonicalize can be followed by further transforms."""
        result = Text("\uff21bc").canonicalize().fold_case().value
        assert result == "abc"

    def test_grapheme_split(self) -> None:
        assert Text("café").grapheme_split() == ["c", "a", "f", "é"]

    def test_grapheme_truncate(self) -> None:
        assert Text("Hello World").grapheme_truncate(5).value == "Hello"

    def test_grapheme_truncate_returns_text(self) -> None:
        """grapheme_truncate returns Text, allowing further chaining."""
        result = Text("café résumé").grapheme_truncate(4).transliterate().value
        assert result == "cafe"

    def test_catalog_key(self) -> None:
        result = Text("  Café  RÉSUMÉ  ").catalog_key().value
        assert result == "cafe resume"

    def test_catalog_key_with_lang(self) -> None:
        result = Text("Москва").catalog_key(lang="ru").value
        assert result  # non-empty transliteration produced
        assert result == result.lower()  # catalog_key folds case

    def test_demojize(self) -> None:
        result = Text("🐍").demojize().value
        assert "snake" in result.lower()
