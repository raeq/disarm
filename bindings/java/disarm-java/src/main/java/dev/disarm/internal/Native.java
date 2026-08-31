package dev.disarm.internal;

import dev.disarm.AnomalyReport;
import dev.disarm.AutoLangInspection;
import dev.disarm.HostnameAnalysis;
import dev.disarm.LangMeta;
import dev.disarm.ScriptMeta;
import dev.disarm.Untranslatable;
import java.util.List;

/**
 * Raw JNI entry points — the thin native shim (Layer A/B boundary).
 *
 * <p>This is an <b>internal</b> class: the idiomatic, supported surface is
 * {@link dev.disarm.Disarm} (and, later, the Kotlin module). Method names here map
 * 1:1 to {@code Java_dev_disarm_internal_Native_*} symbols in the Rust cdylib and
 * take positional, string-token arguments — no defaults, no options objects.
 * Nullable reference args (e.g. {@code lang}) accept {@code null}; size args are
 * {@code long} so a negative value arrives intact and is rejected as a
 * {@link dev.disarm.DisarmInvalidArgumentException} rather than wrapping.
 *
 * <p>The static initializer triggers {@link NativeLoader}, so merely referencing
 * this class loads the native library.
 */
public final class Native {

    static {
        NativeLoader.load();
    }

    private Native() {}

    // ── Transliteration ────────────────────────────────────────────────────────
    public static native String transliterate(String text);

    public static native String transliterateOpts(String text, String scheme, String lang);

    public static native String reverseTransliterate(String text, String lang);

    // ── Confusables ────────────────────────────────────────────────────────────
    public static native String normalizeConfusables(
            String text, String target, String digitPolicy);

    public static native boolean isConfusable(String text, String target);

    // ── Canonicalization primitives ────────────────────────────────────────────
    public static native String stripAccents(String text);

    public static native String foldCase(String text);

    public static native boolean isCaseFoldStable(String text);

    public static native java.util.List<dev.disarm.KeyCollision> findKeyCollisions(
            String[] values, String key, String lang);

    public static native String demojize(String text, boolean stripModifiers);

    // ── Normalization ──────────────────────────────────────────────────────────
    public static native String normalize(String text, String form);

    public static native boolean isNormalized(String text, String form);

    // ── Text cleaning ──────────────────────────────────────────────────────────
    public static native String collapseWhitespace(String text);

    public static native String stripControlChars(String text);

    public static native String stripZeroWidthChars(String text);

    public static native String stripBidi(String text);

    public static native String stripTags(String text);

    public static native String stripVariationSelectors(String text);

    public static native String stripNoncharacters(String text);

    public static native String stripPua(String text);

    public static native String stripZalgo(String text, long maxMarks);

    public static native boolean isZalgo(String text, long threshold);

    // ── Deobfuscation & security presets ───────────────────────────────────────
    public static native String stripObfuscation(String text);

    public static native String canonicalize(String text);

    public static native String canonicalizeStrict(String text);

    public static native String stripFormat(String text);

    public static native String searchKey(String text, String lang);

    public static native String sortKey(String text, String lang);

    public static native String catalogKey(String text, String lang, boolean strictIso9);

    public static native String sanitizeFilename(
            String text,
            String separator,
            long maxLength,
            String platform,
            String lang,
            boolean preserveExtension);

    public static native String slugify(
            String text,
            String separator,
            boolean lowercase,
            long maxLength,
            boolean wordBoundary,
            boolean saveOrder,
            String[] stopwords,
            boolean allowUnicode,
            String lang,
            boolean entities,
            boolean decimal,
            boolean hexadecimal,
            String safeChars);

    // ── Grapheme clusters ──────────────────────────────────────────────────────
    public static native long graphemeLen(String text);

    public static native String graphemeTruncate(String text, long maxGraphemes);

    public static native long graphemeWidth(String cluster, boolean ambiguousWide);

    public static native long terminalWidth(String text, boolean ambiguousWide);

    public static native String[] graphemeSplit(String text);

    // ── Hostname / script analysis ─────────────────────────────────────────────
    public static native boolean isSuspiciousHostname(String host);

    public static native HostnameAnalysis analyzeHostname(String host, boolean contractions);

    public static native boolean isMixedScript(String text);

    public static native boolean hasBidiConflict(String text);

    public static native String[] detectScripts(String text);

    public static native String mlNormalize(
            String text, String lang, String emojiStyle, boolean foldCase);

    public static native String[] unmappedConfusables(String target);

    public static native java.util.List<dev.disarm.UnmappedConfusable> findUnmappedConfusables(
            String text, String target);

    // ── Metadata listings ──────────────────────────────────────────────────────
    public static native String confusablesVersion();

    public static native String unicodeVersion();

    public static native int keySchemaVersion();

    public static native String[] listScripts();

    public static native String[] listContextLangs();

    // ── Reusable handles (opaque jlong pointers) ───────────────────────────────
    public static native long pipelineNew(String profile);

    public static native String pipelineProcess(long handle, String text);

    public static native void pipelineFree(long handle);

    public static native long lexiconNew(String[] words);

    public static native void lexiconFree(long handle);

    public static native boolean hasAnomalies(String text, long lexicon);

    public static native boolean hasAnomaliesWords(String text, String[] words);

    // ── Structured-report returns ──────────────────────────────────────────────
    public static native LangMeta langInfo(String code);

    public static native ScriptMeta scriptInfo(String name);

    public static native AutoLangInspection inspectAutoLang(String text);

    public static native List<Untranslatable> findUntranslatable(
            String text, String scheme, String lang);

    public static native AnomalyReport inspectAnomalies(String text, long lexicon);

    public static native AnomalyReport inspectAnomaliesWords(String text, String[] words);
}
