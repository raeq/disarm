package dev.disarm.kotlin

import dev.disarm.DigitPolicy
import dev.disarm.DisarmInvalidArgumentException
import dev.disarm.Lexicon
import dev.disarm.NormalizationForm
import dev.disarm.Platform
import dev.disarm.TargetScript
import kotlin.test.Test
import kotlin.test.assertContains
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** Exercises the idiomatic Kotlin surface (extension functions + default args). */
class DisarmKtTest {

    @Test
    fun transliterationIdioms() {
        assertEquals("Hello", "Ｈéllo".transliterate())
        assertEquals("Moskva", "Москва".transliterate(lang = "ru"))
        assertFalse("Șoṣ".transliterate(scheme = Scheme.STRICT_ISO9).isBlank())
        assertFalse("Moskva".reverseTransliterate("ru").isBlank())
        assertTrue("hello".findUntranslatable().isEmpty())
    }

    @Test
    fun confusables() {
        assertEquals("apple", "аpple".normalizeConfusables(TargetScript.LATIN)) // Cyrillic а
        assertTrue("аpple".isConfusable(TargetScript.LATIN))
    }

    // #586: the fold iterates to a fixed point rather than stopping after one pass. Every
    // non-Python binding reaches the core through the same Rust entry point, so a single
    // pass made this call answer differently from Python for the same input.
    @Test
    fun confusablesReachAFixedPoint() {
        // A fold exposes a composition: ¥ + U+0300 folds to Y + U+0300, composing to Ỳ.
        assertEquals("\u1EF2", "\u00A5\u0300".normalizeConfusables(TargetScript.LATIN))
        // A composition exposes a fold: Ҫ + U+0327 composes to Ç, a confusable, then C.
        assertEquals("C", "\u04AA\u0327".normalizeConfusables(TargetScript.LATIN))
    }

    @Test
    fun confusableFoldOutputIsNeverItselfConfusable() {
        for (input in listOf("\u04AA\u0327", "\u00A5\u0300", "p\u0430ypal")) {
            assertFalse(input.normalizeConfusables(TargetScript.LATIN).isConfusable(TargetScript.LATIN))
        }
    }

    @Test
    fun canonicalizationPrimitives() {
        assertEquals("cafe", "café".stripAccents())
        assertEquals("hello", "Hello".foldCase())
        assertTrue("gross.txt".isCaseFoldStable())
        assertFalse("groß.txt".isCaseFoldStable())
        val found = listOf("groß.txt", "gross.txt", "other.txt").findKeyCollisions("fold_case")
        assertEquals(1, found.size)
        assertEquals(listOf("groß.txt", "gross.txt"), found[0].values())
        assertEquals(listOf(0L, 1L), found[0].indices())
        assertFalse("😀".demojize().isBlank())
        assertFalse("👍🏽".demojize(stripModifiers = true).isBlank())
    }

    @Test
    fun normalization() {
        assertEquals("é", "é".normalize(NormalizationForm.NFC))
        assertTrue("é".isNormalized(NormalizationForm.NFC))
        assertFalse("é".isNormalized(NormalizationForm.NFC))
    }

    @Test
    fun textCleaning() {
        assertEquals("a b", "a   b".collapseWhitespace())
        assertEquals("ab", "a\u0000b".stripControlChars())
        assertEquals("ab", "a​b".stripZeroWidthChars())
        assertFalse("a‮b".stripBidi().contains('‮'))
        assertEquals("ab", ("a" + String(Character.toChars(0xE0041)) + "b").stripTags())
        assertEquals("ab", "a️b".stripVariationSelectors())
        assertEquals("ab", "a￾b".stripNoncharacters())
        assertEquals("ab", "ab".stripPua())
        val zalgo = "à́̂̃̄̅"
        assertTrue(zalgo.stripZalgo(1).length < zalgo.length)
        assertTrue(zalgo.isZalgo(2))
    }

    @Test
    fun deobfuscationAndKeys() {
        assertFalse("h​e​llo".stripObfuscation().isBlank())
        assertFalse("Ｈello".canonicalize().isBlank())
        // #677: both halves of the pair reach Kotlin. stripFormat keeps the script;
        // canonicalize folds the same input to Latin.
        assertEquals("\u0430\u0440\u0440", "\u0430\u0440\u200D\u0440".stripFormat())
        assertEquals("app", "\u0430\u0440\u200D\u0440".canonicalize())
        assertEquals("Hello".canonicalize(), "Hello".canonicalizeStrict())
        assertEquals("café".searchKey(), "CAFE".searchKey())
        assertFalse("Zürich".searchKey("de").isBlank())
        assertFalse("Zürich".sortKey().isBlank())
        assertFalse("Zürich".sortKey("de").isBlank())
        assertFalse("Dostoevsky".catalogKey().isBlank())
        assertFalse("Достоевский".catalogKey("ru").isBlank())
        assertFalse("Достоевский".catalogKey("ru", strictIso9 = true).isBlank())
    }

    @Test
    fun slugsAndFilenames() {
        assertEquals("hello-world", "Hello World".slugify())
        val slug = "Alpha Beta Gamma".slugify(separator = "_", stopwords = listOf("beta"), maxLength = 40)
        assertFalse(slug.contains("beta"))
        assertTrue(slug.contains("_")) // "alpha_gamma"
        assertTrue("my file.txt".sanitizeFilename().endsWith(".txt"))
        assertFalse(
            "My Résumé.pdf"
                .sanitizeFilename(separator = "-", platform = Platform.WINDOWS, maxLength = 64)
                .isBlank(),
        )
    }

    @Test
    fun graphemes() {
        assertEquals(3, "abc".graphemeLen())
        assertEquals(listOf("a", "b", "c"), "abc".graphemeSplit())
        assertEquals("abc", "abcdef".graphemeTruncate(3))
        assertEquals(2, "世".graphemeWidth())
        assertEquals(2, "世".graphemeWidth(ambiguousWide = true))
        assertEquals(4, "世界".terminalWidth())
        assertEquals(2, "ab".terminalWidth(ambiguousWide = false))
    }

    @Test
    fun hostnameAndScript() {
        assertTrue("аpple.com".isSuspiciousHostname())
        assertFalse("apple.com".isSuspiciousHostname())
        assertTrue("аa".isMixedScript())
        assertFalse("abc".isMixedScript())
        assertTrue("aא".hasBidiConflict())
        assertFalse("abc".hasBidiConflict())
        val scripts = "aа".detectScripts()
        assertContains(scripts, "Latin")
        assertContains(scripts, "Cyrillic")
        assertFalse("Москва".inspectAutoLang().reason().isBlank())
    }

    @Test
    fun anomalies() {
        assertTrue("hi​there".hasAnomalies())
        assertFalse("hello world".hasAnomalies())
        assertTrue("hi​there".inspectAnomalies().anomalous())
        Lexicon(listOf("free")).use { lex ->
            assertTrue("hi​there".hasAnomalies(lex))
            assertTrue("hi​there".inspectAnomalies(lex).anomalous())
        }
    }

    @Test
    fun handlesAndMetadata() {
        getPipeline("normalize_web_input").use { p ->
            assertFalse(p.process("Ｈello").isBlank())
        }
        assertFalse(langInfo("ru").name().isBlank())
        val name = listScripts().first()
        assertEquals(name, scriptInfo(name).name())
        assertFalse(listContextLangs().isEmpty())
    }

    @Test
    fun hostnameAnalysis() {
        val clean = "example.com".analyzeHostname()
        assertFalse(clean.suspicious)
        assertEquals(listOf("Latin"), clean.scripts)
        assertEquals(listOf(listOf("Latin"), listOf("Latin")), clean.labelScripts)
        assertFalse(clean.wholeScriptConfusable)
        assertEquals(listOf(false, false), clean.labelWholeScriptConfusable)

        // All-Cyrillic label аррӏе skeletoning to the Latin brand "apple" (#545/#549).
        val spoof = "аррӏе.com".analyzeHostname()
        assertTrue(spoof.wholeScriptConfusable)
        assertEquals("apple.com", spoof.canonical)

        // Bidi control character (#603): flagged, and stripped from the canonical
        // form so a caller rendering that field cannot render the spoof.
        val rlo = "paypal\u202Emoc.evil.com".analyzeHostname()
        assertTrue(rlo.suspicious)
        assertTrue(rlo.bidiControl)
        assertFalse(rlo.bidiConflict) // disjoint signals
        assertEquals("paypalmoc.evil.com", rlo.canonical)
        assertFalse(clean.bidiControl)

        // Zero-width / invisible-format character (#605): flagged, and removed before
        // any other field is computed, so it reaches neither scripts nor canonical.
        val zwsp = "paypal\u200B.evil.com".analyzeHostname()
        assertTrue(zwsp.suspicious)
        assertTrue(zwsp.hasInvisible)
        assertFalse(zwsp.bidiControl) // disjoint signals
        assertEquals("paypal.evil.com", zwsp.canonical)

        // U+FEFF lives in the Arabic Presentation Forms block; it must not be read
        // as evidence the host contains Arabic.
        val bom = "paypal\uFEFF.evil.com".analyzeHostname()
        assertTrue(bom.hasInvisible)
        assertEquals(listOf("Latin"), bom.scripts)
        assertFalse(bom.mixedScript)

        assertFalse(clean.hasInvisible)

        // Compatibility form (#709): read off the RAW input, before the normalization
        // every other field needs. hasConfusables is correctly false — by the time it
        // runs the label is already "google".
        val fw = "\uFF47oogle.com".analyzeHostname()
        assertTrue(fw.suspicious)
        assertTrue(fw.compatFold)
        assertFalse(fw.hasConfusables)
        assertEquals("google.com", fw.canonical)
        assertFalse(clean.compatFold)

        // UTS #46 maps every label, not only the xn-- ones (#714): the two spellings
        // of one registered domain are one input.
        assertEquals(
            "\uAB70\uAB70.com".analyzeHostname().canonical,
            "xn--58da.com".analyzeHostname().canonical,
        )
    }

    @Test
    fun confusablesVersionIsADottedNumericVersion() {
        val v = confusablesVersion()
        assertTrue(Regex("\\d+(\\.\\d+)+").matches(v), v)
    }

    @Test
    fun digitPolicy() {
        assertEquals("g00gle", "g\u0966\u0966gle".normalizeConfusables(TargetScript.LATIN))
        assertEquals(
            "google",
            "g\u0966\u0966gle".normalizeConfusables(TargetScript.LATIN, DigitPolicy.TR39),
        )
    }

    @Test
    fun mlNormalizeDefaultsFoldCase() {
        assertEquals("jose martinez", "José Martínez".mlNormalize())
        assertEquals("cafe resume", "Café RÉSUMÉ".mlNormalize())
    }

    @Test
    fun mlNormalizeCanKeepCase() {
        // foldCase=false restores case, NOT diacritics — stripAccents still runs.
        assertEquals("Jose Martinez", "José Martínez".mlNormalize(foldCase = false))
    }

    @Test
    fun mlNormalizeHonoursLangAndEmojiStyle() {
        assertEquals("muenchen strasse", "MÜNCHEN Straße".mlNormalize(lang = "de"))
        // emojiStyle controls expansion only; the fold is independent of it.
        assertEquals("hi \uD83D\uDE00", "Hi \uD83D\uDE00".mlNormalize(emojiStyle = "none"))
        assertEquals(
            "Hi \uD83D\uDE00",
            "Hi \uD83D\uDE00".mlNormalize(emojiStyle = "none", foldCase = false),
        )
    }

    @Test
    fun mlNormalizeIsNotAHomoglyphDefence() {
        // No TR39 step in the pipeline, so the Cyrillic С survives at either setting.
        val spoof = "fu\u0421k"
        assertEquals(spoof, spoof.mlNormalize(foldCase = false))
        assertEquals("fuCk", spoof.normalizeConfusables(TargetScript.LATIN))
    }

    @Test
    fun errorsPropagate() {
        assertFailsWith<DisarmInvalidArgumentException> { langInfo("zz_nope") }
        assertFailsWith<DisarmInvalidArgumentException> { "x".stripZalgo(-1) }
    }
}
