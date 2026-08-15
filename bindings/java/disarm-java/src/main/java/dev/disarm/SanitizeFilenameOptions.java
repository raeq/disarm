package dev.disarm;

/**
 * Options for {@link Disarm#sanitizeFilename(String, SanitizeFilenameOptions)}.
 * Immutable; build via {@link #builder()}. Defaults mirror the Node/Ruby bindings.
 */
public final class SanitizeFilenameOptions {

    private final String separator;
    private final int maxLength;
    private final Platform platform;
    private final String lang;
    private final boolean preserveExtension;

    private SanitizeFilenameOptions(Builder b) {
        this.separator = b.separator;
        this.maxLength = b.maxLength;
        this.platform = b.platform;
        this.lang = b.lang;
        this.preserveExtension = b.preserveExtension;
    }

    String separator() {
        return separator;
    }

    int maxLength() {
        return maxLength;
    }

    Platform platform() {
        return platform;
    }

    String lang() {
        return lang;
    }

    boolean preserveExtension() {
        return preserveExtension;
    }

    public static Builder builder() {
        return new Builder();
    }

    /** Fluent builder for {@link SanitizeFilenameOptions}. */
    public static final class Builder {
        private String separator = "_";
        private int maxLength = 255;
        private Platform platform = Platform.UNIVERSAL;
        private String lang = null;
        private boolean preserveExtension = true;

        private Builder() {}

        public Builder separator(String separator) {
            this.separator = separator;
            return this;
        }

        public Builder maxLength(int maxLength) {
            this.maxLength = maxLength;
            return this;
        }

        public Builder platform(Platform platform) {
            this.platform = platform == null ? Platform.UNIVERSAL : platform;
            return this;
        }

        /** Transliteration language profile, or {@code null} for none. */
        public Builder lang(String lang) {
            this.lang = lang;
            return this;
        }

        public Builder preserveExtension(boolean preserveExtension) {
            this.preserveExtension = preserveExtension;
            return this;
        }

        public SanitizeFilenameOptions build() {
            return new SanitizeFilenameOptions(this);
        }
    }
}
