package dev.disarm;

import dev.disarm.internal.Native;
import java.util.List;
import java.util.Objects;

/**
 * Idiomatic Java entry point for disarm — Unicode confusable / text-security
 * building blocks backed by a native Rust core.
 *
 * <p>The Rust mechanism is transparent: add the dependency and call the static
 * methods; the native library loads itself on first use (see
 * {@code dev.disarm.internal.NativeLoader}). Enums stand in for the core's string
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

    /** Fold cross-script confusables toward {@code target}, with the numeric digit policy. */
    public static String normalizeConfusables(String text, TargetScript target) {
        return normalizeConfusables(text, target, DigitPolicy.NUMERIC);
    }

    /**
     * Fold cross-script confusables toward {@code target}, choosing how non-Latin digits
     * fold.
     *
     * <p>{@link DigitPolicy#NUMERIC} is right for prose; {@link DigitPolicy#TR39} is what
     * an identifier skeleton wants. The two differ on 45 rows and agree everywhere
     * else. {@link DigitPolicy#TR39} applies to {@link TargetScript#LATIN} only; with any
     * other target it is a no-op.
     */
    public static String normalizeConfusables(
            String text, TargetScript target, DigitPolicy digitPolicy) {
        req(text);
        Objects.requireNonNull(target, "target");
        Objects.requireNonNull(digitPolicy, "digitPolicy");
        return Native.normalizeConfusables(text, target.token(), digitPolicy.token());
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

    /**
     * Whether {@code text} is a stable identity key under case folding — whether
     * {@link #foldCase} and {@code String.toLowerCase()} agree on it.
     *
     * <p>{@code false} means some other string folds to the same value, so a table keyed on
     * this one can collide: {@code "groß.txt"} and {@code "gross.txt"} are the pair node-tar
     * collided on (CVE-2026-23950). It states a fact about the string, not suspicion.
     */
    public static boolean isCaseFoldStable(String text) {
        return Native.isCaseFoldStable(req(text));
    }

    /**
     * Which of {@code values} are the same name under {@code key}.
     *
     * <p>Every other disarm detector is a single-string predicate, and a collision is not a
     * property of a single string — {@code "groß.txt"} is an ordinary German filename, and
     * {@code "аdmin"} is only a problem next to {@code "admin"}. This is the set-shaped
     * question node-tar's {@code PathReservations} guard failed to ask (CVE-2026-23950).
     *
     * <p>{@code key} is one of {@code "fold_case"}, {@code "search_key"},
     * {@code "catalog_key"}, {@code "canonicalize"}, {@code "canonicalize_strict"},
     * {@code "normalize_confusables"}. There is no default: a stronger key finds more
     * collisions, including ones nobody attacked, so the choice is the policy.
     *
     * @param values the set to check; order is preserved in the report
     * @param key    which reducer builds the keys
     * @param lang   language hint for {@code search_key} / {@code catalog_key}, or null
     */
    public static List<KeyCollision> findKeyCollisions(List<String> values, String key, String lang) {
        Objects.requireNonNull(values, "values");
        Objects.requireNonNull(key, "key");
        return Native.findKeyCollisions(values.toArray(new String[0]), key, lang);
    }

    /** {@link #findKeyCollisions(List, String, String)} with no language hint. */
    public static List<KeyCollision> findKeyCollisions(List<String> values, String key) {
        return findKeyCollisions(values, key, null);
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

    /**
     * Turn arbitrary text into a filesystem-safe filename with default options.
     *
     * <p>A safe <em>filename</em>, not a safe URL path segment. {@code %} is legal in a
     * filename, so one the caller typed is kept — {@code sanitizeFilename("..%2Fetc")}
     * returns {@code "%2Fetc"} — and a consumer that percent-decodes the result must
     * validate <em>after</em> decoding. What this will not do is manufacture one:
     * {@code %} never appears in the output unless it appeared in the input (#721).
     */
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

    /**
     * Canonicalize text for security-sensitive comparison. Not an output sanitizer —
     * encode at the sink.
     *
     * <p>Two steps introduce ASCII, not one (#719): the leading NFKC, and the confusable
     * fold, which reaches characters NFKC leaves alone. {@code U+2236 RATIO} becomes
     * {@code :}, {@code U+2044 FRACTION SLASH} becomes {@code /}, {@code U+2216 SET
     * MINUS} becomes {@code \}. A string that carried no delimiter can leave here
     * carrying one. {@code inspectAnomalies} reports it as {@code confusable} <em>when the
     * word also carries an ASCII letter</em>, which is the gate that keeps ordinary
     * non-Latin text from firing; a delimiter-only string is not reported.
     */
    public static String canonicalize(String text) {
        return Native.canonicalize(req(text));
    }

    /**
     * Canonicalize, but throw rather than silently normalize a structural difference away.
     *
     * <p>The half of the pair that lets a caller <em>reject</em> input instead of
     * comparing a value the sender never wrote — the useful behaviour when the comparison
     * decides access rather than ranks a search result.
     *
     * @throws DisarmException if the text cannot be canonicalized unambiguously
     */
    public static String canonicalizeStrict(String text) {
        return Native.canonicalizeStrict(req(text));
    }

    /**
     * Strip the non-interchange and invisible classes while keeping the script.
     *
     * <p>Unlike {@link #canonicalize} it folds no confusables, so non-Latin text keeps its
     * script. It cannot be rebuilt from the universal {@code strip*} methods, and the
     * difference runs both ways: this preserves the private-use area (icon fonts) and
     * keeps the VS15/VS16 presentation selectors after a base, which the naive chain
     * deletes, and it collapses TAB/LF to a space, which the primitives leave alone.
     */
    public static List<UnmappedConfusable> findUnmappedConfusables(String text, TargetScript target) {
        req(text);
        Objects.requireNonNull(target, "target");
        return Native.findUnmappedConfusables(text, target.token());
    }

    /** {@link #findUnmappedConfusables(String, TargetScript)} against the Latin table. */
    public static List<UnmappedConfusable> findUnmappedConfusables(String text) {
        return findUnmappedConfusables(text, TargetScript.LATIN);
    }

    /** Characters with no transliteration under the default scheme, in order. */
    public static List<Untranslatable> findUntranslatable(String text) {
        return findUntranslatable(text, TransliterateOptions.builder().build());
    }

    /** Characters with no transliteration under the given options, in order. */
    public static List<Untranslatable> findUntranslatable(String text, TransliterateOptions options) {
        req(text);
        Objects.requireNonNull(options, "options");
        return Native.findUntranslatable(text, options.scheme(), options.lang());
    }
}
