package dev.disarm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
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
        assertFalse(Disarm.stripBidi("a\u202eb").contains("\u202e")); // RLO
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

    @Test
    void findKeyCollisions() {
        List<KeyCollision> found =
                Disarm.findKeyCollisions(List.of("groß.txt", "gross.txt", "other.txt"), "fold_case");
        assertEquals(1, found.size());
        assertEquals("gross.txt", found.get(0).key());
        assertEquals(List.of("groß.txt", "gross.txt"), found.get(0).values());
        assertEquals(List.of(0L, 1L), found.get(0).indices());
        // The reducer is the policy: fold_case sees the eszett, canonicalize the homoglyph.
        assertEquals(
                List.of("admin", "аdmin"),
                Disarm.findKeyCollisions(List.of("admin", "аdmin"), "canonicalize").get(0).values());
        assertTrue(Disarm.findKeyCollisions(List.of("a.txt", "b.txt"), "fold_case").isEmpty());
        assertThrows(
                DisarmInvalidArgumentException.class,
                () -> Disarm.findKeyCollisions(List.of("a"), "lower"));
    }

    /**
     * #677 — the JVM carried neither half of the pair. {@code stripFormat} keeps the
     * script, {@code canonicalize} folds the same input to Latin; that contrast is why
     * the preset cannot be rebuilt from the universal {@code strip*} methods.
     */
    @Test
    void stripFormatAndCanonicalizeStrict() {
        String cyrillic = "\u0430\u0440\u200D\u0440";
        assertEquals("\u0430\u0440\u0440", Disarm.stripFormat(cyrillic));
        assertEquals("app", Disarm.canonicalize(cyrillic));
        assertEquals(Disarm.canonicalize("Hello"), Disarm.canonicalizeStrict("Hello"));
    }

    @Test
    void isCaseFoldStable() {
        assertTrue(Disarm.isCaseFoldStable("gross.txt"));
        assertFalse(Disarm.isCaseFoldStable("groß.txt")); // collides with gross.txt
        assertThrows(NullPointerException.class, () -> Disarm.isCaseFoldStable(null));
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
    void digitPolicyReachesTheKeyBuilders() {
        // U+0A66 GURMUKHI ZERO standing in for "o": a digit by default, the letter under tr39.
        String spoof = "g\u0A66ogle";
        assertEquals("g0ogle", Disarm.canonicalize(spoof));
        assertEquals(Disarm.canonicalize(spoof), Disarm.canonicalize(spoof, DigitPolicy.NUMERIC));
        assertEquals("google", Disarm.canonicalize(spoof, DigitPolicy.TR39));
        assertEquals("google", Disarm.catalogKey(spoof, null, false, DigitPolicy.TR39));
        assertEquals("google", Disarm.searchKey(spoof, null, DigitPolicy.TR39));
        // #949: preserve keeps a numeral where the builder owns a fold; transliteration romanizes it.
        String numeral = "amount-\u0661";
        assertEquals(numeral, Disarm.canonicalize(numeral, DigitPolicy.PRESERVE));
        assertEquals("amount-1", Disarm.searchKey(numeral, null, DigitPolicy.PRESERVE));
        assertThrows(NullPointerException.class, () -> Disarm.canonicalize("x", (DigitPolicy) null));
    }

    @Test
    void skeletonKeyEditDistanceAndNearestMatch() {
        assertEquals(Disarm.skeletonKey("paypal"), Disarm.skeletonKey("paypaI"));
        assertEquals(
                Disarm.skeletonKey("SKU-100", DigitPolicy.TR39),
                Disarm.skeletonKey("SKU-1O0", DigitPolicy.TR39));
        assertEquals(1L, Disarm.editDistance("paypa1", "paypal"));
        List<String> reserved = List.of("paypal", "stripe", "admin");
        assertEquals(new NearestMatch("paypal", 1L), Disarm.nearestMatch("paypa1", reserved));
        assertEquals(new NearestMatch("admin", 0L), Disarm.nearestMatch("admin", reserved));
        assertNull(Disarm.nearestMatch("something-else", reserved));
        assertEquals(new NearestMatch("paypal", 2L), Disarm.nearestMatch("paypa11", reserved, 2));
    }

    @Test
    void pipelineWithDigitPolicy() {
        String spoof = "g\u0A66ogle";
        try (Pipeline guard = Disarm.getPipeline("llm_guardrail");
                Pipeline tr39 = guard.withDigitPolicy(DigitPolicy.TR39)) {
            assertEquals("g0ogle", guard.process(spoof));
            assertEquals("google", tr39.process(spoof));
        }
        try (Pipeline rag = Disarm.getPipeline("rag_ingest")) {
            assertThrows(DisarmInvalidArgumentException.class, () -> rag.withDigitPolicy(DigitPolicy.TR39));
        }
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

    // #586: the fold iterates to a fixed point rather than stopping after one pass. Every
    // non-Python binding reaches the core through the same Rust entry point, so a single
    // pass made this call answer differently from Python for the same input.
    @Test
    void normalizeConfusablesReachesAFixedPoint() {
        // A fold exposes a composition: ¥ + U+0300 folds to Y + U+0300, composing to Ỳ.
        assertEquals("\u1EF2", Disarm.normalizeConfusables("\u00A5\u0300", TargetScript.LATIN));
        // A composition exposes a fold: Ҫ + U+0327 composes to Ç, a confusable, then C.
        assertEquals("C", Disarm.normalizeConfusables("\u04AA\u0327", TargetScript.LATIN));
    }

    @Test
    void normalizeConfusablesOutputIsNeverItselfConfusable() {
        for (String input : new String[] {"\u04AA\u0327", "\u00A5\u0300", "p\u0430ypal"}) {
            String folded = Disarm.normalizeConfusables(input, TargetScript.LATIN);
            assertFalse(Disarm.isConfusable(folded, TargetScript.LATIN), input);
        }
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
    void digitPolicySelectsTheDigitReading() {
        String spoof = "g\u0966\u0966gle";
        assertEquals("g00gle", Disarm.normalizeConfusables(spoof, TargetScript.LATIN));
        assertEquals(
                "google",
                Disarm.normalizeConfusables(spoof, TargetScript.LATIN, DigitPolicy.TR39));
        assertEquals(
                "paypal",
                Disarm.normalizeConfusables("p\u0430ypal", TargetScript.LATIN, DigitPolicy.TR39));
    }

    @Test
    void mlNormalizeFoldsCaseByDefault() {
        assertEquals("jose martinez", Disarm.mlNormalize("Jos\u00E9 Mart\u00EDnez"));
    }

    @Test
    void mlNormalizeCanKeepCase() {
        MlNormalizeOptions opts = MlNormalizeOptions.builder().foldCase(false).build();
        assertEquals("Jose Martinez", Disarm.mlNormalize("Jos\u00E9 Mart\u00EDnez", opts));
    }

    @Test
    void mlNormalizeHonoursLangAndEmoji() {
        MlNormalizeOptions de = MlNormalizeOptions.builder().lang("de").build();
        assertEquals("muenchen strasse", Disarm.mlNormalize("M\u00DCNCHEN Stra\u00DFe", de));
        MlNormalizeOptions none = MlNormalizeOptions.builder().emojiStyle("none").build();
        assertEquals("hi \uD83D\uDE00", Disarm.mlNormalize("Hi \uD83D\uDE00", none));
    }

    @Test
    void mlNormalizeRejectsBadEmojiStyle() {
        MlNormalizeOptions bad = MlNormalizeOptions.builder().emojiStyle("bogus").build();
        assertThrows(DisarmInvalidArgumentException.class, () -> Disarm.mlNormalize("x", bad));
    }

    @Test
    void hostnameContractionsAreOptIn() {
        assertEquals("arnazon.com", Disarm.analyzeHostname("arnazon.com").canonical());
        assertEquals("amazon.com", Disarm.analyzeHostname("arnazon.com", true).canonical());
        assertEquals("wv.com", Disarm.analyzeHostname("vvv.com", true).canonical());
        assertEquals("var.net", Disarm.analyzeHostname("var.net", true).canonical());
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
