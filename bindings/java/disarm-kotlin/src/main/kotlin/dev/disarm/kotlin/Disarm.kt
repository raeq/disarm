@file:JvmName("Disarm")

package dev.disarm.kotlin

import dev.disarm.AnomalyReport
import dev.disarm.AutoLangInspection
import dev.disarm.ConfusableCoverage
import dev.disarm.DigitPolicy
import dev.disarm.HostnameAnalysis
import dev.disarm.KeyCollision
import dev.disarm.NearestMatch
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
@JvmOverloads
fun String.transliterate(scheme: Scheme = Scheme.DEFAULT, lang: String? = null): String =
    if (scheme == Scheme.DEFAULT && lang == null) {
        JDisarm.transliterate(this)
    } else {
        JDisarm.transliterate(this, TransliterateOptions.builder().scheme(scheme).lang(lang).build())
    }

/** Reverse-transliterate Latin → native script. `lang` is `"el"`/`"ru"`/`"uk"`. */
fun String.reverseTransliterate(lang: String): String = JDisarm.reverseTransliterate(this, lang)

/** Characters with no romanization, in order. */
@JvmOverloads
fun String.findUntranslatable(scheme: Scheme = Scheme.DEFAULT, lang: String? = null): List<Untranslatable> =
    JDisarm.findUntranslatable(this, TransliterateOptions.builder().scheme(scheme).lang(lang).build())

// ── Confusables ─────────────────────────────────────────────────────────────────

/**
 * Fold cross-script confusables toward [target]. [DigitPolicy.NUMERIC] is right for prose;
 * [DigitPolicy.TR39] is what an identifier skeleton wants, and applies to
 * [TargetScript.LATIN] only — with any other target it is a no-op.
 */
@JvmOverloads
fun String.normalizeConfusables(
    target: TargetScript,
    digitPolicy: DigitPolicy = DigitPolicy.NUMERIC,
): String = JDisarm.normalizeConfusables(this, target, digitPolicy)

fun String.isConfusable(target: TargetScript): Boolean = JDisarm.isConfusable(this, target)

// ── Canonicalization primitives ─────────────────────────────────────────────────

fun String.stripAccents(): String = JDisarm.stripAccents(this)

fun String.foldCase(): String = JDisarm.foldCase(this)

/**
 * Whether this value is a stable identity key under case folding — whether [foldCase]
 * and `lowercase()` agree on it. `false` means some other string folds to the same
 * value, the collision node-tar hit in CVE-2026-23950. A fact about the string, not
 * suspicion: `groß` is an ordinary German word.
 */
fun String.isCaseFoldStable(): Boolean = JDisarm.isCaseFoldStable(this)

/**
 * Which of these values are the same name under [key].
 *
 * A collision is not a property of a single string — `groß.txt` is an ordinary German
 * filename, and `аdmin` is only a problem next to `admin`. This is the set-shaped question
 * node-tar's `PathReservations` guard failed to ask (CVE-2026-23950).
 *
 * [key] is one of `fold_case`, `search_key`, `catalog_key`, `canonicalize`,
 * `canonicalize_strict`, `normalize_confusables`. There is no default: a stronger key finds
 * more collisions, including ones nobody attacked, so the choice is the policy.
 */
@JvmOverloads
fun List<String>.findKeyCollisions(key: String, lang: String? = null): List<KeyCollision> =
    JDisarm.findKeyCollisions(this, key, lang)

@JvmOverloads
fun String.demojize(stripModifiers: Boolean = false): String = JDisarm.demojize(this, stripModifiers)

/**
 * Replace every emoji with [replacement], verbatim (#972).
 *
 * The counterpart to [demojize]: that names a character from the CLDR table, which is
 * wider than the emoji, and this replaces what the UCD calls an emoji and nothing else.
 * [replacement] is inserted exactly as given — `""` closes an intra-word split and `" "`
 * keeps two words apart, and no rule serves both.
 */
@JvmOverloads
fun String.replaceEmoji(replacement: String = ""): String = JDisarm.replaceEmoji(this, replacement)

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

@JvmOverloads
fun String.stripObfuscation(digitPolicy: DigitPolicy = DigitPolicy.NUMERIC): String =
    JDisarm.stripObfuscation(this, digitPolicy)

@JvmOverloads
fun String.canonicalize(digitPolicy: DigitPolicy = DigitPolicy.NUMERIC): String =
    JDisarm.canonicalize(this, digitPolicy)

/**
 * Whether this value is already its own canonical form under [preset] (#730) — the
 * verification path, where the presets are the generation path. `hasAnomalies` is not this
 * predicate.
 */
@JvmOverloads
fun String.isCanonical(preset: String = "canonicalize"): Boolean =
    JDisarm.isCanonical(this, preset)

/**
 * Canonicalize, but throw rather than silently normalize a structural difference away —
 * the half of the pair that lets a caller reject input instead of comparing a value the
 * sender never wrote.
 */
@JvmOverloads
fun String.canonicalizeStrict(digitPolicy: DigitPolicy = DigitPolicy.NUMERIC): String =
    JDisarm.canonicalizeStrict(this, digitPolicy)

/**
 * Strip the non-interchange and invisible classes while keeping the script. Folds no
 * confusables, so non-Latin text survives as itself. Not composable from the universal
 * `strip*` extensions, and the difference runs both ways: this keeps the private-use area
 * and the VS15/VS16 presentation selectors after a base, and it collapses TAB/LF.
 */
fun String.stripFormat(): String = JDisarm.stripFormat(this)

@JvmOverloads
fun String.searchKey(lang: String? = null, digitPolicy: DigitPolicy = DigitPolicy.NUMERIC): String =
    JDisarm.searchKey(this, lang, digitPolicy)

@JvmOverloads
fun String.sortKey(lang: String? = null, digitPolicy: DigitPolicy = DigitPolicy.NUMERIC): String =
    JDisarm.sortKey(this, lang, digitPolicy)

@JvmOverloads
fun String.catalogKey(
    lang: String? = null,
    strictIso9: Boolean = false,
    digitPolicy: DigitPolicy = DigitPolicy.NUMERIC,
): String = JDisarm.catalogKey(this, lang, strictIso9, digitPolicy)

/**
 * The TR39 identifier skeleton plus the two prototype classes disarm keeps apart (#650). A
 * spoof key: never for display. [DigitPolicy.TR39] adds `1 ≡ l` and `0 ≡ O`.
 */
@JvmOverloads
fun String.skeletonKey(digitPolicy: DigitPolicy = DigitPolicy.NUMERIC): String =
    JDisarm.skeletonKey(this, digitPolicy)

/** Levenshtein edit distance to [other], in characters (#894). */
fun String.editDistance(other: String): Long = JDisarm.editDistance(this, other)

/**
 * The candidate closest to this value with its distance, or `null` beyond [maxDistance]
 * (#894). An exact match is reported with distance 0.
 */
@JvmOverloads
fun String.nearestMatch(candidates: List<String>, maxDistance: Long = 1): NearestMatch? =
    JDisarm.nearestMatch(this, candidates, maxDistance)

// ── Slugs & filenames (option builders → default arguments) ─────────────────────

@JvmOverloads
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

@JvmOverloads
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

@JvmOverloads
fun String.graphemeWidth(ambiguousWide: Boolean = false): Long = JDisarm.graphemeWidth(this, ambiguousWide)

@JvmOverloads
fun String.terminalWidth(ambiguousWide: Boolean = false): Long = JDisarm.terminalWidth(this, ambiguousWide)

// ── Hostname / script analysis ──────────────────────────────────────────────────

fun String.isSuspiciousHostname(): Boolean = JDisarm.isSuspiciousHostname(this)

/** Full hostname homoglyph analysis (#549) — verdict + granular signals. */
@JvmOverloads
fun String.analyzeHostname(contractions: Boolean = false): HostnameAnalysis =
    JDisarm.analyzeHostname(this, contractions)

fun String.isMixedScript(): Boolean = JDisarm.isMixedScript(this)

fun String.hasBidiConflict(): Boolean = JDisarm.hasBidiConflict(this)

/**
 * All twelve UAX #9 explicit formatting characters, uncontexted. Disjoint from
 * [hasBidiConflict], which reads strong-direction letters.
 */
fun String.hasBidiControl(): Boolean = JDisarm.hasBidiControl(this)

fun String.detectScripts(): List<String> = JDisarm.detectScripts(this)

fun String.inspectAutoLang(): AutoLangInspection = JDisarm.inspectAutoLang(this)

// ── Anomalies (reusable Lexicon works with `use { }`) ───────────────────────────

@JvmOverloads
fun String.hasAnomalies(words: List<String> = emptyList()): Boolean = JDisarm.hasAnomalies(this, words)

fun String.hasAnomalies(lexicon: Lexicon): Boolean = JDisarm.hasAnomalies(this, lexicon)

@JvmOverloads
fun String.inspectAnomalies(words: List<String> = emptyList()): AnomalyReport =
    JDisarm.inspectAnomalies(this, words)

fun String.inspectAnomalies(lexicon: Lexicon): AnomalyReport = JDisarm.inspectAnomalies(this, lexicon)

// ── Handles & metadata (top-level functions) ────────────────────────────────────

/** Build a reusable [Pipeline] for a named policy profile; use with `use { }`. */
fun getPipeline(profile: String): Pipeline = JDisarm.getPipeline(profile)

fun langInfo(code: String): LangMeta = JDisarm.langInfo(code)

fun scriptInfo(name: String): ScriptMeta = JDisarm.scriptInfo(name)

/**
 * TR39 sources whose prototype is in [script], and how many of those disarm folds (#963).
 *
 * The denominator [unmappedConfusables] does not have: that measures one bundled table
 * against the whole 6,565-source population, so a script disarm ships no table for
 * reports a number determined by that absence. `folded` counts sources any bundled table
 * reaches, not sources folded *toward* this script — Greek is 71 of 159, because the
 * Latin table folds Greek letters that look Latin.
 */
fun confusableCoverage(script: String): ConfusableCoverage = JDisarm.confusableCoverage(script)

/**
 * The Unicode `confusables.txt` release the bundled confusable tables were folded from.
 *
 * Not a library-wide Unicode version — see `docs/provenance.md`.
 */
fun confusablesVersion(): String = JDisarm.confusablesVersion()

/**
 * The UCD release disarm's normalizer implements. Not a library-wide Unicode version —
 * the bundled tables track different releases.
 */
fun unicodeVersion(): String = JDisarm.unicodeVersion()

/**
 * Whether a key stored under an earlier release still compares equal. A monotonic
 * counter, not a version; meaningless in isolation, by design.
 */
fun keySchemaVersion(): Int = JDisarm.keySchemaVersion()

/**
 * ML/NLP normalization: NFKC → emoji→text → transliterate → strip accents → [case fold]
 * → strip control → strip zero-width → collapse whitespace.
 *
 * [foldCase] defaults to true; pass false in front of a **cased** model. It restores
 * case, not diacritics — accents are still stripped. Folds no confusables, so it is not a
 * homoglyph defence at any setting.
 */
@JvmOverloads
fun String.mlNormalize(
    lang: String? = null,
    emojiStyle: String = "cldr",
    foldCase: Boolean = true,
): String = JDisarm.mlNormalize(
    this,
    MlNormalizeOptions.builder().lang(lang).emojiStyle(emojiStyle).foldCase(foldCase).build(),
)

/** Every upstream confusable source the bundled [target] table does not fold (#563). */
@JvmOverloads
fun unmappedConfusables(target: TargetScript = TargetScript.LATIN): List<String> =
    JDisarm.unmappedConfusables(target)

/** Confusable sources in this string the bundled [target] table does not fold (#563). */
@JvmOverloads
fun String.findUnmappedConfusables(
    target: TargetScript = TargetScript.LATIN,
): List<UnmappedConfusable> = JDisarm.findUnmappedConfusables(this, target)

fun listScripts(): List<String> = JDisarm.listScripts()

fun listContextLangs(): List<String> = JDisarm.listContextLangs()
