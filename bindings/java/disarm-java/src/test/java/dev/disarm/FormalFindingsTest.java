package dev.disarm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

/** Regression tests for the bindings harness findings ({@code formal/bindings/README.md}). */
class FormalFindingsTest {

    /** J1: a Java String crosses the boundary as its UTF-16, lone surrogates as one U+FFFD. */
    @Nested
    class J1Surrogates {
        private static final String GRIN = "\uD83D\uDE00";
        private static final String LONE = "\uD800";

        @Test
        void aLoneSurrogateIsOneReplacementCharacter() {
            assertEquals("a[?]b", Disarm.transliterate("a" + LONE + "b"));
            assertEquals(3, Disarm.graphemeLen("a" + LONE + "b"));
            assertEquals("a\uFFFDb", Disarm.foldCase("a" + LONE + "b"));
            assertEquals("a\uFFFDb", Disarm.foldCase("a\uDC00b"));
        }

        @Test
        void aLoneSurrogateLeavesTheRestOfTheStringAlone() {
            assertEquals("xy\uFFFD", Disarm.replaceEmoji("x" + GRIN + "y" + LONE, ""));
            assertEquals("grinning face \uFFFD", Disarm.demojize(GRIN + " " + LONE));
            assertEquals(GRIN + "\uFFFD", Disarm.foldCase(GRIN + LONE));
        }

        @Test
        void wellFormedTextIsUnchanged() {
            assertEquals("xy", Disarm.replaceEmoji("x" + GRIN + "y", ""));
            assertEquals("a\u0000b", Disarm.foldCase("a\u0000b"));
            assertEquals("\uD835\uDCD7", Disarm.stripBidi("\uD835\uDCD7"));
            // Reversed pair: two lone surrogates.
            assertEquals("\uFFFD\uFFFD", Disarm.foldCase("\uDE00\uD83D"));
        }
    }

    /** J2: the arabic and hebrew confusable targets (#792). */
    @Test
    void j2ArabicAndHebrewTargets() {
        assertEquals("arabic", TargetScript.ARABIC.token());
        assertEquals("hebrew", TargetScript.HEBREW.token());
        assertTrue(Disarm.normalizeConfusables("x", TargetScript.ARABIC) != null);
        assertFalse(Disarm.isConfusable("x", TargetScript.HEBREW));
        assertFalse(Disarm.unmappedConfusables(TargetScript.ARABIC).isEmpty());
    }

    /** B2: an unknown lang is rejected, as the key builders always did. */
    @Test
    void b2UnknownLangIsInvalidArgument() {
        String kyiv = "\u041a\u0438\u0457\u0432";
        TransliterateOptions uk = TransliterateOptions.builder().lang("UK").build();
        assertThrows(DisarmInvalidArgumentException.class, () -> Disarm.transliterate(kyiv, uk));
        assertThrows(DisarmInvalidArgumentException.class, () -> Disarm.findUntranslatable(kyiv, uk));
        assertThrows(
                DisarmInvalidArgumentException.class,
                () -> Disarm.slugify("M\u00fcnchen", SlugOptions.builder().lang("dee").build()));
        assertEquals(
                "Kyiv", Disarm.transliterate(kyiv, TransliterateOptions.builder().lang("uk").build()));
        assertEquals(
                "muenchen", Disarm.slugify("M\u00fcnchen", SlugOptions.builder().lang("de").build()));
    }

    /** S1: strip_accents is per character. */
    @Test
    void s1SingletonDecompositionFolds() {
        assertEquals(";", Disarm.stripAccents("\u037e"));
        assertEquals(";e", Disarm.stripAccents("\u037ee\u0301"));
    }

    /** D1: an emoji CLDR cannot name is the [?] sentinel, as in Python. */
    @Test
    void d1UnnameableEmojiIsTheSentinel() {
        assertEquals("[?]", Disarm.demojize("\uD83C\uDDE6"));
    }
}
