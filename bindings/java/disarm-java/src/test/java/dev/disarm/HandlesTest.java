package dev.disarm;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

/** Covers the reusable {@link Pipeline} / {@link Lexicon} handles and anomaly detection. */
class HandlesTest {

    private static final String PROFILE = "normalize_web_input";

    @Test
    void pipelineProcessesInTryWithResources() {
        try (Pipeline p = Disarm.getPipeline(PROFILE)) {
            assertFalse(p.process("Ｈello").isBlank());
            // Reuse the compiled handle across calls.
            assertFalse(p.process("café").isBlank());
        }
    }

    @Test
    void pipelineDoubleCloseIsIdempotentAndUseAfterCloseThrows() {
        Pipeline p = Disarm.getPipeline(PROFILE);
        p.close();
        p.close(); // idempotent
        assertThrows(IllegalStateException.class, () -> p.process("x"));
    }

    @Test
    void unknownProfileThrowsInvalidArgument() {
        assertThrows(
                DisarmInvalidArgumentException.class,
                () -> Disarm.getPipeline("no_such_profile"));
    }

    @Test
    void pipelineNullProfileThrows() {
        assertThrows(NullPointerException.class, () -> Disarm.getPipeline(null));
    }

    @Test
    void anomaliesViaInlineWordList() {
        // A zero-width space is an "invisible" anomaly, independent of the lexicon.
        assertTrue(Disarm.hasAnomalies("hi​there", List.of()));
        assertFalse(Disarm.hasAnomalies("hello world", List.of()));
    }

    @Test
    void anomaliesViaReusableLexicon() {
        try (Lexicon lex = new Lexicon(List.of("free", "winner"))) {
            assertTrue(Disarm.hasAnomalies("hi​there", lex));
            assertFalse(Disarm.hasAnomalies("hello world", lex));
        }
    }

    @Test
    void lexiconUseAfterCloseThrows() {
        Lexicon lex = new Lexicon(List.of("free"));
        lex.close();
        lex.close(); // idempotent
        assertThrows(IllegalStateException.class, () -> Disarm.hasAnomalies("x", lex));
    }

    @Test
    void handleNullArgsThrow() {
        assertThrows(NullPointerException.class, () -> Disarm.hasAnomalies(null, List.of()));
        assertThrows(NullPointerException.class, () -> Disarm.hasAnomalies("x", (List<String>) null));
        assertThrows(NullPointerException.class, () -> Disarm.hasAnomalies("x", (Lexicon) null));
        assertThrows(NullPointerException.class, () -> new Lexicon(null));
    }
}
