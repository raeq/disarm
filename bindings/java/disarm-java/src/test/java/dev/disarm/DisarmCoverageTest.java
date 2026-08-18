package dev.disarm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

/**
 * Exercises the remaining {@link Disarm} methods and overloads not covered by
 * {@link DisarmTest}, plus the null-argument guard branches — driving coverage of
 * the idiomatic layer to completeness.
 */
class DisarmCoverageTest {

    private static String astral(int codePoint) {
        return new String(Character.toChars(codePoint));
    }

    // ── Remaining cleaners (base 'a'/'b' preserved, special code point removed) ──

    @Test
    void stripBidi() {
        assertFalse(Disarm.stripBidi("a‮b").contains("‮")); // RLO
    }

    @Test
    void stripTags() {
        // U+E0041 (TAG LATIN CAPITAL A) is astral.
        assertEquals("ab", Disarm.stripTags("a" + astral(0xE0041) + "b"));
    }

    @Test
    void stripVariationSelectors() {
        assertEquals("ab", Disarm.stripVariationSelectors("a️b")); // VS16
    }

    @Test
    void stripNoncharacters() {
        assertEquals("ab", Disarm.stripNoncharacters("a￾b")); // U+FFFE noncharacter
    }

    @Test
    void stripPua() {
        assertEquals("ab", Disarm.stripPua("ab")); // Private Use Area
    }

    // ── Overloads with explicit optional arguments ──────────────────────────────

    @Test
    void demojizeStripModifiers() {
        assertFalse(Disarm.demojize("👍🏽", true).isBlank());
    }

    @Test
    void searchKeyWithLang() {
        assertFalse(Disarm.searchKey("Иван", "ru").isBlank()); // Иван
    }

    @Test
    void sortKeyOverloads() {
        assertFalse(Disarm.sortKey("Zürich").isBlank());
        assertFalse(Disarm.sortKey("Zürich", "de").isBlank());
    }

    @Test
    void catalogKeyOverloads() {
        assertFalse(Disarm.catalogKey("Dostoevsky").isBlank());
        assertFalse(Disarm.catalogKey("Достоевский", "ru").isBlank()); // Достоевский
        assertFalse(Disarm.catalogKey("Достоевский", "ru", true).isBlank());
    }

    @Test
    void widthOverloadsWithAmbiguous() {
        assertEquals(2, Disarm.graphemeWidth("世", true)); // 世 stays wide
        assertEquals(1, Disarm.graphemeWidth("a", false));
        assertEquals(2, Disarm.terminalWidth("ab", false));
    }

    // ── Null-argument guard branches ────────────────────────────────────────────

    @Test
    void nullArgumentsThrow() {
        assertThrows(NullPointerException.class, () -> Disarm.transliterate(null));
        assertThrows(NullPointerException.class, () -> Disarm.transliterate("x", null));
        assertThrows(NullPointerException.class, () -> Disarm.reverseTransliterate("x", null));
        assertThrows(NullPointerException.class, () -> Disarm.normalizeConfusables("x", null));
        assertThrows(NullPointerException.class, () -> Disarm.isConfusable("x", null));
        assertThrows(NullPointerException.class, () -> Disarm.normalize("x", null));
        assertThrows(NullPointerException.class, () -> Disarm.isNormalized("x", null));
        assertThrows(NullPointerException.class, () -> Disarm.isSuspiciousHostname(null));
        assertThrows(NullPointerException.class, () -> Disarm.graphemeWidth(null));
    }

    // ── A couple more happy paths for breadth ───────────────────────────────────

    @Test
    void transliterateWithSchemeOption() {
        String out = Disarm.transliterate(
                "Șoṣ",
                TransliterateOptions.builder()
                        .scheme(TransliterateOptions.Scheme.STRICT_ISO9)
                        .build());
        assertFalse(out.isBlank());
    }

    @Test
    void normalizeConfusablesToCyrillic() {
        assertTrue(Disarm.normalizeConfusables("abc", TargetScript.CYRILLIC) != null);
    }

    // ── Collection returns ──────────────────────────────────────────────────────

    @Test
    void graphemeSplitClusters() {
        assertEquals(List.of("a", "b", "c"), Disarm.graphemeSplit("abc"));
    }

    @Test
    void detectScriptsFindsBoth() {
        List<String> scripts = Disarm.detectScripts("aа"); // Latin a + Cyrillic а
        assertTrue(scripts.contains("Latin"), scripts.toString());
        assertTrue(scripts.contains("Cyrillic"), scripts.toString());
    }

    @Test
    void confusablesVersionIsADottedNumericVersion() {
        String v = Disarm.confusablesVersion();
        assertTrue(v.matches("\\d+(\\.\\d+)+"), v);
    }

    @Test
    void unmappedConfusablesReportsExposure() {
        List<String> unmapped = Disarm.unmappedConfusables(TargetScript.LATIN);
        assertTrue(unmapped.size() > 1000, String.valueOf(unmapped.size()));
        assertFalse(unmapped.contains("\u0430"), "Cyrillic a folds, so it is not exposure");
        assertTrue(unmapped.contains("m"), "TR39 skeleton source m->rn is not applied");
    }

    @Test
    void findUnmappedConfusablesAgreesWithTheFold() {
        assertEquals("paypal", Disarm.normalizeConfusables("p\u0430ypal", TargetScript.LATIN));
        assertTrue(Disarm.findUnmappedConfusables("p\u0430ypal").isEmpty());
        List<UnmappedConfusable> hits = Disarm.findUnmappedConfusables("am");
        assertEquals(1, hits.size());
        assertEquals("m", hits.get(0).character());
        assertEquals(1L, hits.get(0).offset());
    }

    @Test
    void listScriptsAndContextLangsNonEmpty() {
        assertTrue(Disarm.listScripts().contains("Latin"));
        assertFalse(Disarm.listContextLangs().isEmpty());
    }

    @Test
    void collectionNullArgsThrow() {
        assertThrows(NullPointerException.class, () -> Disarm.graphemeSplit(null));
        assertThrows(NullPointerException.class, () -> Disarm.detectScripts(null));
    }

    // ── Slugs & filenames ───────────────────────────────────────────────────────

    @Test
    void slugifyDefault() {
        assertEquals("hello-world", Disarm.slugify("Hello World"));
    }

    @Test
    void slugifyTransliteratesAndLowercases() {
        assertTrue(Disarm.slugify("Café Déjà").matches("[a-z0-9-]+"));
    }

    @Test
    void slugifyWithOptions() {
        String slug = Disarm.slugify(
                "Alpha Beta Gamma",
                SlugOptions.builder()
                        .separator("_")
                        .stopwords(List.of("beta"))
                        .maxLength(40)
                        .build());
        assertFalse(slug.contains("beta"), slug);
        assertTrue(slug.contains("_"), slug);
    }

    @Test
    void sanitizeFilenameDefault() {
        String name = Disarm.sanitizeFilename("my report.txt");
        assertFalse(name.contains(" "), name);
        assertTrue(name.endsWith(".txt"), name);
    }

    @Test
    void sanitizeFilenameWithOptions() {
        String name = Disarm.sanitizeFilename(
                "My Résumé.pdf",
                SanitizeFilenameOptions.builder()
                        .separator("-")
                        .platform(Platform.WINDOWS)
                        .maxLength(64)
                        .preserveExtension(true)
                        .build());
        assertFalse(name.isBlank());
        assertTrue(name.endsWith(".pdf"), name);
    }

    @Test
    void slugAndFilenameNullArgsThrow() {
        assertThrows(NullPointerException.class, () -> Disarm.slugify(null));
        assertThrows(NullPointerException.class, () -> Disarm.slugify("x", null));
        assertThrows(NullPointerException.class, () -> Disarm.sanitizeFilename(null));
        assertThrows(NullPointerException.class, () -> Disarm.sanitizeFilename("x", null));
    }
}
