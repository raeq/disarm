package dev.disarm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

/** Covers the structured-report returns (records built across the JNI boundary). */
class StructuredReportsTest {

    @Test
    void langInfoReturnsMetadata() {
        LangMeta m = Disarm.langInfo("ru");
        assertFalse(m.name().isBlank());
        assertFalse(m.script().isBlank());
        assertFalse(m.context().isBlank());
    }

    @Test
    void langInfoUnknownCodeThrows() {
        assertThrows(DisarmInvalidArgumentException.class, () -> Disarm.langInfo("zz_not_a_lang"));
    }

    @Test
    void scriptInfoReturnsMetadata() {
        String name = Disarm.listScripts().get(0);
        ScriptMeta m = Disarm.scriptInfo(name);
        assertEquals(name, m.name());
        assertFalse(m.example().isBlank());
    }

    @Test
    void scriptInfoUnknownNameThrows() {
        assertThrows(DisarmInvalidArgumentException.class, () -> Disarm.scriptInfo("NoSuchScript"));
    }

    @Test
    void confusableCoverageReportsThePerScriptDenominator() {
        // Greek is the row the method exists for: no to-Greek table ships, so
        // unmappedConfusables would report almost the whole 6,565-source population.
        ConfusableCoverage greek = Disarm.confusableCoverage("Greek");
        assertEquals("Greek", greek.script());
        assertEquals(159, greek.sources());
        // Not zero, and not everything: the Latin table folds Greek letters that
        // look Latin, so 71 of the 159 are already reached.
        assertEquals(71, greek.folded());
    }

    @Test
    void confusableCoverageAnswersZeroOfZeroForAnUntargetedScript() {
        ConfusableCoverage thaana = Disarm.confusableCoverage("Thaana");
        assertEquals(0, thaana.sources());
        assertEquals(0, thaana.folded());
    }

    @Test
    void confusableCoverageReachesScriptsTheEnumDoesNotName() {
        // The grouping is the UCD's, so Yi is addressable here and nowhere else.
        assertEquals(12, Disarm.confusableCoverage("Yi").sources());
        assertThrows(DisarmInvalidArgumentException.class, () -> Disarm.scriptInfo("Yi"));
    }

    @Test
    void confusableCoverageUnknownScriptThrows() {
        assertThrows(
                DisarmInvalidArgumentException.class,
                () -> Disarm.confusableCoverage("NoSuchScript"));
    }

    @Test
    void inspectAutoLangExplainsChoice() {
        AutoLangInspection r = Disarm.inspectAutoLang("Москва"); // Москва
        assertNotNull(r.discriminatorsHit());
        assertFalse(r.reason().isBlank());
    }

    @Test
    void findUntranslatableEmptyForAscii() {
        assertTrue(Disarm.findUntranslatable("hello").isEmpty());
        // Non-null for arbitrary input (emoji may or may not be translatable).
        assertNotNull(Disarm.findUntranslatable("🎉"));
    }

    @Test
    void inspectAnomaliesViaWordList() {
        AnomalyReport r = Disarm.inspectAnomalies("hi\u200bthere", List.of()); // zero-width space
        assertTrue(r.anomalous());
        assertFalse(r.findings().isEmpty());
        assertTrue(r.kinds().contains("invisible"), r.kinds().toString());
        Finding f = r.findings().get(0);
        assertFalse(f.reason().isBlank());
        assertFalse(f.kind().isBlank());
    }

    @Test
    void inspectAnomaliesCleanTextIsNotAnomalous() {
        AnomalyReport r = Disarm.inspectAnomalies("hello world", List.of());
        assertFalse(r.anomalous());
        assertTrue(r.findings().isEmpty());
    }

    @Test
    void analyzeHostnameReturnsFullAnalysis() {
        HostnameAnalysis clean = Disarm.analyzeHostname("example.com");
        assertFalse(clean.suspicious());
        assertEquals(List.of("Latin"), clean.scripts());
        // List<List<String>> and List<Boolean> marshalled across the JNI boundary.
        assertEquals(List.of(List.of("Latin"), List.of("Latin")), clean.labelScripts());
        assertFalse(clean.wholeScriptConfusable());
        assertEquals(List.of(false, false), clean.labelWholeScriptConfusable());
        assertEquals("example.com", clean.canonical());
    }

    @Test
    void analyzeHostnameFlagsWholeScriptSpoof() {
        // All-Cyrillic label аррӏе skeletoning to the Latin brand "apple" (#545).
        HostnameAnalysis spoof = Disarm.analyzeHostname("аррӏе.com");
        assertTrue(spoof.wholeScriptConfusable());
        assertEquals(List.of(true, false), spoof.labelWholeScriptConfusable());
        assertEquals("apple.com", spoof.canonical());
    }

    @Test
    void inspectAnomaliesViaReusableLexicon() {
        try (Lexicon lex = new Lexicon(List.of("free"))) {
            AnomalyReport r = Disarm.inspectAnomalies("hi\u200bthere", lex);
            assertTrue(r.anomalous());
        }
    }

    @Test
    void structuredNullArgsThrow() {
        assertThrows(NullPointerException.class, () -> Disarm.langInfo(null));
        assertThrows(NullPointerException.class, () -> Disarm.scriptInfo(null));
        assertThrows(NullPointerException.class, () -> Disarm.inspectAutoLang(null));
        assertThrows(NullPointerException.class, () -> Disarm.findUntranslatable(null));
        assertThrows(NullPointerException.class, () -> Disarm.inspectAnomalies("x", (List<String>) null));
        assertThrows(NullPointerException.class, () -> Disarm.inspectAnomalies("x", (Lexicon) null));
    }
}
