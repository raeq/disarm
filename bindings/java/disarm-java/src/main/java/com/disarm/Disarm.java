package com.disarm;

import com.disarm.internal.Native;
import java.util.List;
import java.util.Objects;

/**
 * Idiomatic Java entry point for disarm — Unicode confusable / text-security
 * building blocks backed by a native Rust core.
 *
 * <p>The Rust mechanism is transparent: add the dependency and call the static
 * methods; the native library loads itself on first use (see
 * {@code com.disarm.internal.NativeLoader}). Enums stand in for the core's string
 * tokens, and nullable {@code lang} arguments are modelled as overloads.
 *
 * <pre>{@code
 * String ascii = Disarm.transliterate("Ｈéllo");            // "Hello"
 * String ru    = Disarm.transliterate("Москва",
 *                    TransliterateOptions.builder().lang("ru").build());
 * boolean spoof = Disarm.isSuspiciousHostname("аpple.com");  // Cyrillic 'а'
 * }</pre>
 */
public final class Disarm {

    private Disarm() {}

    private static String req(String text) {
        return Objects.requireNonNull(text, "text");
    }

    // ── Transliteration ────────────────────────────────────────────────────────

    /** Unicode → ASCII with the default scheme. */
    public static String transliterate(String text) {
        return Native.transliterate(req(text));
    }

    /** Unicode → ASCII with an explicit scheme and/or language profile. */
    public static String transliterate(String text, TransliterateOptions options) {
        req(text);
        Objects.requireNonNull(options, "options");
        return Native.transliterateOpts(text, options.scheme(), options.lang());
    }

    /** Reverse-transliterate Latin → native script. {@code lang} is {@code "el"|"ru"|"uk"}. */
    public static String reverseTransliterate(String text, String lang) {
        req(text);
        Objects.requireNonNull(lang, "lang");
        return Native.reverseTransliterate(text, lang);
    }

    // ── Confusables ────────────────────────────────────────────────────────────

    /** Fold cross-script confusables toward {@code target}. */
    public static String normalizeConfusables(String text, TargetScript target) {
        req(text);
        Objects.requireNonNull(target, "target");
        return Native.normalizeConfusables(text, target.token());
    }

    /** Whether {@code text} contains a character confusable with {@code target}. */
    public static boolean isConfusable(String text, TargetScript target) {
        req(text);
        Objects.requireNonNull(target, "target");
        return Native.isConfusable(text, target.token());
    }

    // ── Canonicalization primitives ────────────────────────────────────────────

    public static String stripAccents(String text) {
        return Native.stripAccents(req(text));
    }

    public static String foldCase(String text) {
        return Native.foldCase(req(text));
    }

    /** Replace emoji with their plain names (skin-tone modifiers preserved). */
    public static String demojize(String text) {
        return demojize(text, false);
    }

    /** Replace emoji with their plain names; {@code stripModifiers} drops skin-tone marks. */
    public static String demojize(String text, boolean stripModifiers) {
        return Native.demojize(req(text), stripModifiers);
    }

    // ── Normalization ──────────────────────────────────────────────────────────

    public static String normalize(String text, NormalizationForm form) {
        req(text);
        Objects.requireNonNull(form, "form");
        return Native.normalize(text, form.token());
    }

    public static boolean isNormalized(String text, NormalizationForm form) {
        req(text);
        Objects.requireNonNull(form, "form");
        return Native.isNormalized(text, form.token());
    }

    // ── Text cleaning ──────────────────────────────────────────────────────────

    public static String collapseWhitespace(String text) {
        return Native.collapseWhitespace(req(text));
    }

    public static String stripControlChars(String text) {
        return Native.stripControlChars(req(text));
    }

    public static String stripZeroWidthChars(String text) {
        return Native.stripZeroWidthChars(req(text));
    }

    public static String stripBidi(String text) {
        return Native.stripBidi(req(text));
    }

    /** Strip the Unicode Tags block (U+E0000–U+E007F), preserving valid emoji flags. */
    public static String stripTags(String text) {
        return Native.stripTags(req(text));
    }

    /** Strip every variation selector (VS1–VS256). */
    public static String stripVariationSelectors(String text) {
        return Native.stripVariationSelectors(req(text));
    }

    /** Strip every Unicode noncharacter. */
    public static String stripNoncharacters(String text) {
        return Native.stripNoncharacters(req(text));
    }

    /** Strip every Private Use Area code point. */
    public static String stripPua(String text) {
        return Native.stripPua(req(text));
    }

    /** Collapse runs of combining marks to at most {@code maxMarks} per base ("de-zalgo"). */
    public static String stripZalgo(String text, int maxMarks) {
        return Native.stripZalgo(req(text), maxMarks);
    }

    /** Whether {@code text} carries more than {@code threshold} combining marks on any base. */
    public static boolean isZalgo(String text, int threshold) {
        return Native.isZalgo(req(text), threshold);
    }

    // ── Slugs & filenames ──────────────────────────────────────────────────────

    /** Generate a URL-safe slug with default options. */
    public static String slugify(String text) {
        return slugify(text, SlugOptions.builder().build());
    }

    /** Generate a URL-safe slug with explicit options. */
    public static String slugify(String text, SlugOptions options) {
        req(text);
        Objects.requireNonNull(options, "options");
        return Native.slugify(
                text,
                options.separator(),
                options.lowercase(),
                options.maxLength(),
                options.wordBoundary(),
                options.saveOrder(),
                options.stopwords(),
                options.allowUnicode(),
                options.lang(),
                options.entities(),
                options.decimal(),
                options.hexadecimal(),
                options.safeChars());
    }

    /** Turn arbitrary text into a filesystem-safe filename with default options. */
    public static String sanitizeFilename(String text) {
        return sanitizeFilename(text, SanitizeFilenameOptions.builder().build());
    }

    /** Turn arbitrary text into a filesystem-safe filename with explicit options. */
    public static String sanitizeFilename(String text, SanitizeFilenameOptions options) {
        req(text);
        Objects.requireNonNull(options, "options");
        return Native.sanitizeFilename(
                text,
                options.separator(),
                options.maxLength(),
                options.platform().token(),
                options.lang(),
                options.preserveExtension());
    }

    // ── Deobfuscation & security presets ───────────────────────────────────────

    public static String stripObfuscation(String text) {
        return Native.stripObfuscation(req(text));
    }

    public static String canonicalize(String text) {
        return Native.canonicalize(req(text));
    }

    /** Case/accent/script-insensitive search lookup key. */
    public static String searchKey(String text) {
        return searchKey(text, null);
    }

    /** Search key with a transliteration language profile ({@code null} for none). */
    public static String searchKey(String text, String lang) {
        return Native.searchKey(req(text), lang);
    }

    /** Collation sort key (preserves base accented characters for correct ordering). */
    public static String sortKey(String text) {
        return sortKey(text, null);
    }

    public static String sortKey(String text, String lang) {
        return Native.sortKey(req(text), lang);
    }

    /** Library-catalog deduplication key (search key plus confusable folding). */
    public static String catalogKey(String text) {
        return catalogKey(text, null, false);
    }

    public static String catalogKey(String text, String lang) {
        return catalogKey(text, lang, false);
    }

    public static String catalogKey(String text, String lang, boolean strictIso9) {
        return Native.catalogKey(req(text), lang, strictIso9);
    }

    // ── Grapheme clusters ──────────────────────────────────────────────────────

    /** Number of grapheme clusters (user-perceived characters) in {@code text}. */
    public static long graphemeLen(String text) {
        return Native.graphemeLen(req(text));
    }

    /** Truncate to at most {@code maxGraphemes} grapheme clusters. */
    public static String graphemeTruncate(String text, int maxGraphemes) {
        return Native.graphemeTruncate(req(text), maxGraphemes);
    }

    /** Split {@code text} into its grapheme clusters, in order. */
    public static List<String> graphemeSplit(String text) {
        return List.of(Native.graphemeSplit(req(text)));
    }

    /** Display width of a single grapheme cluster (narrow ambiguous). */
    public static long graphemeWidth(String cluster) {
        return graphemeWidth(cluster, false);
    }

    public static long graphemeWidth(String cluster, boolean ambiguousWide) {
        return Native.graphemeWidth(Objects.requireNonNull(cluster, "cluster"), ambiguousWide);
    }

    /** Total terminal display width of {@code text} (narrow ambiguous). */
    public static long terminalWidth(String text) {
        return terminalWidth(text, false);
    }

    public static long terminalWidth(String text, boolean ambiguousWide) {
        return Native.terminalWidth(req(text), ambiguousWide);
    }

    // ── Hostname / script analysis ─────────────────────────────────────────────

    /**
     * Whether the hostname looks like a mixed-script / confusable / bidi-reorder IDN
     * spoof. A {@code false} asserts nothing was <em>found</em>, not that the host is safe.
     */
    public static boolean isSuspiciousHostname(String host) {
        return Native.isSuspiciousHostname(Objects.requireNonNull(host, "host"));
    }

    /** Whether {@code text} mixes characters from more than one script. */
    public static boolean isMixedScript(String text) {
        return Native.isMixedScript(req(text));
    }

    /** Whether {@code text} mixes strong LTR and strong RTL characters ("BiDi Swap" precondition). */
    public static boolean hasBidiConflict(String text) {
        return Native.hasBidiConflict(req(text));
    }

    /** The Unicode scripts present in {@code text}, in first-appearance order (UCD identifiers). */
    public static List<String> detectScripts(String text) {
        return List.of(Native.detectScripts(req(text)));
    }

    // ── Metadata listings ──────────────────────────────────────────────────────

    /** Every Unicode script name known to the transliteration tables. */
    public static List<String> listScripts() {
        return List.of(Native.listScripts());
    }

    /** Every language code that has a context-aware transliteration profile. */
    public static List<String> listContextLangs() {
        return List.of(Native.listContextLangs());
    }

    // ── Reusable handles & anomalies ────────────────────────────────────────────

    /**
     * Build a reusable {@link Pipeline} for a named policy profile. Throws
     * {@link DisarmInvalidArgumentException} on an unknown profile. The returned
     * pipeline holds a native resource — close it (try-with-resources).
     */
    public static Pipeline getPipeline(String profile) {
        Objects.requireNonNull(profile, "profile");
        return new Pipeline(Native.pipelineNew(profile));
    }

    /** Whether {@code text} trips any anomaly against a word list (per-call set build). */
    public static boolean hasAnomalies(String text, List<String> words) {
        req(text);
        Objects.requireNonNull(words, "words");
        return Native.hasAnomaliesWords(text, words.toArray(new String[0]));
    }

    /** Whether {@code text} trips any anomaly against a prebuilt {@link Lexicon}. */
    public static boolean hasAnomalies(String text, Lexicon lexicon) {
        req(text);
        Objects.requireNonNull(lexicon, "lexicon");
        return Native.hasAnomalies(text, lexicon.handle());
    }
}
