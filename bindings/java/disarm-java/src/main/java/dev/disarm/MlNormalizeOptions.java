package dev.disarm;

/**
 * Options for {@link Disarm#mlNormalize(String, MlNormalizeOptions)}.
 *
 * <p>Immutable; build via {@link #builder()}. Mirrors the options-object idiom the Node
 * ({@code MlNormalizeOptions}) and Ruby (keyword args) bindings expose, and the shape
 * {@link TransliterateOptions} already established here.
 */
public final class MlNormalizeOptions {

    private final String lang;
    private final String emojiStyle;
    private final boolean foldCase;

    private MlNormalizeOptions(String lang, String emojiStyle, boolean foldCase) {
        this.lang = lang;
        this.emojiStyle = emojiStyle;
        this.foldCase = foldCase;
    }

    /** Language profile token, or {@code null} for none. */
    String lang() {
        return lang;
    }

    /** {@code "cldr"} or {@code "none"}. */
    String emojiStyle() {
        return emojiStyle;
    }

    boolean foldCase() {
        return foldCase;
    }

    /** Defaults: no language, CLDR emoji expansion, case folding on. */
    public static MlNormalizeOptions defaults() {
        return builder().build();
    }

    public static Builder builder() {
        return new Builder();
    }

    /** Fluent builder for {@link MlNormalizeOptions}. */
    public static final class Builder {
        private String lang = null;
        private String emojiStyle = "cldr";
        private boolean foldCase = true;

        private Builder() {}

        /** Set the transliteration language profile, e.g. {@code "de"}, {@code "ja"}. */
        public Builder lang(String lang) {
            this.lang = lang;
            return this;
        }

        /**
         * Emoji handling: {@code "cldr"} (default) expands emoji to their CLDR short
         * names; {@code "none"} leaves them untouched. Any other value throws
         * {@link DisarmInvalidArgumentException} at call time.
         */
        public Builder emojiStyle(String emojiStyle) {
            this.emojiStyle = emojiStyle == null ? "cldr" : emojiStyle;
            return this;
        }

        /**
         * Apply Unicode case folding (default {@code true}).
         *
         * <p>Pass {@code false} in front of a <b>cased</b> model. Folding is destructive,
         * cannot be undone downstream, and an uncased evaluation harness cannot measure
         * what it cost. It restores case, not diacritics — {@code strip_accents} still
         * runs, so {@code José} becomes {@code Jose}.
         */
        public Builder foldCase(boolean foldCase) {
            this.foldCase = foldCase;
            return this;
        }

        public MlNormalizeOptions build() {
            return new MlNormalizeOptions(lang, emojiStyle, foldCase);
        }
    }
}
