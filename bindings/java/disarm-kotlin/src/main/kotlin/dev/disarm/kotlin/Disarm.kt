@file:JvmName("Disarm")

package dev.disarm.kotlin

import dev.disarm.AnomalyReport
import dev.disarm.AutoLangInspection
import dev.disarm.DigitPolicy
import dev.disarm.HostnameAnalysis
import dev.disarm.LangMeta
import dev.disarm.Lexicon
import dev.disarm.MlNormalizeOptions
import dev.disarm.NormalizationForm
import dev.disarm.Pipeline
import dev.disarm.Platform
import dev.disarm.SanitizeFilenameOptions
import dev.disarm.ScriptMeta
import dev.disarm.SlugOptions
import dev.disarm.TargetScript
import dev.disarm.TransliterateOptions
import dev.disarm.UnmappedConfusable
import dev.disarm.Untranslatable
import dev.disarm.Disarm as JDisarm

/**
 * Idiomatic Kotlin surface for disarm — thin extension functions over the Java
 * facade ([dev.disarm.Disarm]), which owns the JNI shim and native loader.
 *
 * Kotlin idioms over the Java API: transforms read as [String] extension functions
 * (`text.transliterate()`), option builders collapse into named/default arguments
 * (`text.slugify(separator = "_", maxLength = 40)`), nullable `lang: String?`
 * replaces overloads, and the [Pipeline]/[Lexicon] handles work with `use { }`.
 * Java enums/records/exceptions are reused as-is.
 */

/** Transliteration scheme (alias of the Java enum for concise call sites). */
typealias Scheme = TransliterateOptions.Scheme

// ── Transliteration ─────────────────────────────────────────────────────────────

/** Unicode → ASCII. With defaults this is the borrow-on-no-op fast path. */
fun String.transliterate(scheme: Scheme = Scheme.DEFAULT, lang: String? = null): String =
    if (scheme == Scheme.DEFAULT && lang == null) {
        JDisarm.transliterate(this)
    } else {
        JDisarm.transliterate(this, TransliterateOptions.builder().scheme(scheme).lang(lang).build())
    }

/** Reverse-transliterate Latin → native script. `lang` is `"el"`/`"ru"`/`"uk"`. */
fun String.reverseTransliterate(lang: String): String = JDisarm.reverseTransliterate(this, lang)

/** Characters with no romanization, in order. */
fun String.findUntranslatable(scheme: Scheme = Scheme.DEFAULT, lang: String? = null): List<Untranslatable> =
    JDisarm.findUntranslatable(this, TransliterateOptions.builder().scheme(scheme).lang(lang).build())

// ── Confusables ─────────────────────────────────────────────────────────────────

/**
 * Fold cross-script confusables toward [target]. [DigitPolicy.NUMERIC] is right for prose;
 * [DigitPolicy.TR39] is what an identifier skeleton wants, and applies to
 * [TargetScript.LATIN] only — with any other target it is a no-op.
 */
fun String.normalizeConfusables(
    target: TargetScript,
    digitPolicy: DigitPolicy = DigitPolicy.NUMERIC,
): String = JDisarm.normalizeConfusables(this, target, digitPolicy)

fun String.isConfusable(target: TargetScript): Boolean = JDisarm.isConfusable(this, target)

// ── Canonicalization primitives ─────────────────────────────────────────────────

fun String.stripAccents(): String = JDisarm.stripAccents(this)

fun String.foldCase(): String = JDisarm.foldCase(this)

fun String.demojize(stripModifiers: Boolean = false): String = JDisarm.demojize(this, stripModifiers)

// ── Normalization ───────────────────────────────────────────────────────────────

fun String.normalize(form: NormalizationForm): String = JDisarm.normalize(this, form)

fun String.isNormalized(form: NormalizationForm): Boolean = JDisarm.isNormalized(this, form)

// ── Text cleaning ───────────────────────────────────────────────────────────────

fun String.collapseWhitespace(): String = JDisarm.collapseWhitespace(this)

fun String.stripControlChars(): String = JDisarm.stripControlChars(this)

fun String.stripZeroWidthChars(): String = JDisarm.stripZeroWidthChars(this)

fun String.stripBidi(): String = JDisarm.stripBidi(this)

fun String.stripTags(): String = JDisarm.stripTags(this)

fun String.stripVariationSelectors(): String = JDisarm.stripVariationSelectors(this)

fun String.stripNoncharacters(): String = JDisarm.stripNoncharacters(this)

fun String.stripPua(): String = JDisarm.stripPua(this)

fun String.stripZalgo(maxMarks: Int): String = JDisarm.stripZalgo(this, maxMarks)

fun String.isZalgo(threshold: Int): Boolean = JDisarm.isZalgo(this, threshold)

// ── Deobfuscation & key derivation ──────────────────────────────────────────────

fun String.stripObfuscation(): String = JDisarm.stripObfuscation(this)

fun String.canonicalize(): String = JDisarm.canonicalize(this)

fun String.searchKey(lang: String? = null): String = JDisarm.searchKey(this, lang)

fun String.sortKey(lang: String? = null): String = JDisarm.sortKey(this, lang)

fun String.catalogKey(lang: String? = null, strictIso9: Boolean = false): String =
    JDisarm.catalogKey(this, lang, strictIso9)

// ── Slugs & filenames (option builders → default arguments) ─────────────────────

fun String.slugify(
    separator: String = "-",
    lowercase: Boolean = true,
    maxLength: Int = 0,
    wordBoundary: Boolean = false,
    saveOrder: Boolean = false,
    stopwords: List<String> = emptyList(),
    allowUnicode: Boolean = false,
    lang: String? = null,
    entities: Boolean = true,
    decimal: Boolean = true,
    hexadecimal: Boolean = true,
    safeChars: String = "",
): String =
    JDisarm.slugify(
        this,
        SlugOptions.builder()
            .separator(separator)
            .lowercase(lowercase)
            .maxLength(maxLength)
            .wordBoundary(wordBoundary)
            .saveOrder(saveOrder)
            .stopwords(stopwords)
            .allowUnicode(allowUnicode)
            .lang(lang)
            .entities(entities)
            .decimal(decimal)
            .hexadecimal(hexadecimal)
            .safeChars(safeChars)
            .build(),
    )

fun String.sanitizeFilename(
    separator: String = "_",
    maxLength: Int = 255,
    platform: Platform = Platform.UNIVERSAL,
    lang: String? = null,
    preserveExtension: Boolean = true,
): String =
    JDisarm.sanitizeFilename(
        this,
        SanitizeFilenameOptions.builder()
            .separator(separator)
            .maxLength(maxLength)
            .platform(platform)
            .lang(lang)
            .preserveExtension(preserveExtension)
            .build(),
    )

// ── Grapheme clusters ───────────────────────────────────────────────────────────

fun String.graphemeLen(): Long = JDisarm.graphemeLen(this)

fun String.graphemeSplit(): List<String> = JDisarm.graphemeSplit(this)

fun String.graphemeTruncate(maxGraphemes: Int): String = JDisarm.graphemeTruncate(this, maxGraphemes)

fun String.graphemeWidth(ambiguousWide: Boolean = false): Long = JDisarm.graphemeWidth(this, ambiguousWide)

fun String.terminalWidth(ambiguousWide: Boolean = false): Long = JDisarm.terminalWidth(this, ambiguousWide)

// ── Hostname / script analysis ──────────────────────────────────────────────────

fun String.isSuspiciousHostname(): Boolean = JDisarm.isSuspiciousHostname(this)

/** Full hostname homoglyph analysis (#549) — verdict + granular signals. */
fun String.analyzeHostname(contractions: Boolean = false): HostnameAnalysis =
    JDisarm.analyzeHostname(this, contractions)

fun String.isMixedScript(): Boolean = JDisarm.isMixedScript(this)

fun String.hasBidiConflict(): Boolean = JDisarm.hasBidiConflict(this)

fun String.detectScripts(): List<String> = JDisarm.detectScripts(this)

fun String.inspectAutoLang(): AutoLangInspection = JDisarm.inspectAutoLang(this)

// ── Anomalies (reusable Lexicon works with `use { }`) ───────────────────────────

fun String.hasAnomalies(words: List<String> = emptyList()): Boolean = JDisarm.hasAnomalies(this, words)

fun String.hasAnomalies(lexicon: Lexicon): Boolean = JDisarm.hasAnomalies(this, lexicon)

fun String.inspectAnomalies(words: List<String> = emptyList()): AnomalyReport =
    JDisarm.inspectAnomalies(this, words)

fun String.inspectAnomalies(lexicon: Lexicon): AnomalyReport = JDisarm.inspectAnomalies(this, lexicon)

// ── Handles & metadata (top-level functions) ────────────────────────────────────

/** Build a reusable [Pipeline] for a named policy profile; use with `use { }`. */
fun getPipeline(profile: String): Pipeline = JDisarm.getPipeline(profile)

fun langInfo(code: String): LangMeta = JDisarm.langInfo(code)

fun scriptInfo(name: String): ScriptMeta = JDisarm.scriptInfo(name)

/**
 * The Unicode `confusables.txt` release the bundled confusable tables were folded from.
 *
 * Not a library-wide Unicode version — see `docs/provenance.md`.
 */
fun confusablesVersion(): String = JDisarm.confusablesVersion()

/**
 * ML/NLP normalization: NFKC → emoji→text → transliterate → strip accents → [case fold]
 * → strip control → strip zero-width → collapse whitespace.
 *
 * [foldCase] defaults to true; pass false in front of a **cased** model. It restores
 * case, not diacritics — accents are still stripped. Folds no confusables, so it is not a
 * homoglyph defence at any setting.
 */
fun String.mlNormalize(
    lang: String? = null,
    emojiStyle: String = "cldr",
    foldCase: Boolean = true,
): String = JDisarm.mlNormalize(
    this,
    MlNormalizeOptions.builder().lang(lang).emojiStyle(emojiStyle).foldCase(foldCase).build(),
)

/** Every upstream confusable source the bundled [target] table does not fold (#563). */
fun unmappedConfusables(target: TargetScript = TargetScript.LATIN): List<String> =
    JDisarm.unmappedConfusables(target)

/** Confusable sources in this string the bundled [target] table does not fold (#563). */
fun String.findUnmappedConfusables(
    target: TargetScript = TargetScript.LATIN,
): List<UnmappedConfusable> = JDisarm.findUnmappedConfusables(this, target)

fun listScripts(): List<String> = JDisarm.listScripts()

fun listContextLangs(): List<String> = JDisarm.listContextLangs()
