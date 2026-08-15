package dev.disarm;

/**
 * Options for {@link Disarm#transliterate(String, TransliterateOptions)}.
 *
 * <p>Immutable; build via {@link #builder()}. Mirrors the options-object idiom the
 * Node ({@code TransliterateOptions}) and Ruby (keyword args) bindings expose.
 */
public final class TransliterateOptions {

    /** Transliteration scheme. Maps to the core's string tokens. */
    public enum Scheme {
        DEFAULT("default"),
        STRICT_ISO9("strict_iso9"),
        GOST7034("gost7034");

        private final String token;

        Scheme(String token) {
            this.token = token;
        }

        String token() {
            return token;
        }
    }

    private final Scheme scheme;
    private final String lang;

    private TransliterateOptions(Scheme scheme, String lang) {
        this.scheme = scheme;
        this.lang = lang;
    }

    String scheme() {
        return scheme.token();
    }

    /** Language profile token, or {@code null} for none. */
    String lang() {
        return lang;
    }

    public static Builder builder() {
        return new Builder();
    }

    /** Fluent builder for {@link TransliterateOptions}. */
    public static final class Builder {
        private Scheme scheme = Scheme.DEFAULT;
        private String lang = null;

        private Builder() {}

        public Builder scheme(Scheme scheme) {
            this.scheme = scheme == null ? Scheme.DEFAULT : scheme;
            return this;
        }

        /** Set the language profile, e.g. {@code "ru"}, {@code "uk"}, {@code "el"}. */
        public Builder lang(String lang) {
            this.lang = lang;
            return this;
        }

        public TransliterateOptions build() {
            return new TransliterateOptions(scheme, lang);
        }
    }
}
