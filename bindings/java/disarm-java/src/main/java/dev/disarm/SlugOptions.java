package dev.disarm;

import java.util.List;

/**
 * Options for {@link Disarm#slugify(String, SlugOptions)}. Immutable; build via
 * {@link #builder()}. Defaults mirror the Node/Ruby bindings.
 */
public final class SlugOptions {

    private final String separator;
    private final boolean lowercase;
    private final int maxLength;
    private final boolean wordBoundary;
    private final boolean saveOrder;
    private final String[] stopwords;
    private final boolean allowUnicode;
    private final String lang;
    private final boolean entities;
    private final boolean decimal;
    private final boolean hexadecimal;
    private final String safeChars;

    private SlugOptions(Builder b) {
        this.separator = b.separator;
        this.lowercase = b.lowercase;
        this.maxLength = b.maxLength;
        this.wordBoundary = b.wordBoundary;
        this.saveOrder = b.saveOrder;
        this.stopwords = b.stopwords.toArray(new String[0]);
        this.allowUnicode = b.allowUnicode;
        this.lang = b.lang;
        this.entities = b.entities;
        this.decimal = b.decimal;
        this.hexadecimal = b.hexadecimal;
        this.safeChars = b.safeChars;
    }

    String separator() {
        return separator;
    }

    boolean lowercase() {
        return lowercase;
    }

    int maxLength() {
        return maxLength;
    }

    boolean wordBoundary() {
        return wordBoundary;
    }

    boolean saveOrder() {
        return saveOrder;
    }

    String[] stopwords() {
        return stopwords;
    }

    boolean allowUnicode() {
        return allowUnicode;
    }

    String lang() {
        return lang;
    }

    boolean entities() {
        return entities;
    }

    boolean decimal() {
        return decimal;
    }

    boolean hexadecimal() {
        return hexadecimal;
    }

    String safeChars() {
        return safeChars;
    }

    public static Builder builder() {
        return new Builder();
    }

    /** Fluent builder for {@link SlugOptions}. */
    public static final class Builder {
        private String separator = "-";
        private boolean lowercase = true;
        private int maxLength = 0; // 0 = no limit
        private boolean wordBoundary = false;
        private boolean saveOrder = false;
        private List<String> stopwords = List.of();
        private boolean allowUnicode = false;
        private String lang = null;
        private boolean entities = true;
        private boolean decimal = true;
        private boolean hexadecimal = true;
        private String safeChars = "";

        private Builder() {}

        public Builder separator(String separator) {
            this.separator = separator;
            return this;
        }

        public Builder lowercase(boolean lowercase) {
            this.lowercase = lowercase;
            return this;
        }

        /** Maximum slug length in characters; {@code 0} means no limit. */
        public Builder maxLength(int maxLength) {
            this.maxLength = maxLength;
            return this;
        }

        public Builder wordBoundary(boolean wordBoundary) {
            this.wordBoundary = wordBoundary;
            return this;
        }

        public Builder saveOrder(boolean saveOrder) {
            this.saveOrder = saveOrder;
            return this;
        }

        public Builder stopwords(List<String> stopwords) {
            this.stopwords = List.copyOf(stopwords);
            return this;
        }

        public Builder allowUnicode(boolean allowUnicode) {
            this.allowUnicode = allowUnicode;
            return this;
        }

        /** Transliteration language profile, or {@code null} for none. */
        public Builder lang(String lang) {
            this.lang = lang;
            return this;
        }

        public Builder entities(boolean entities) {
            this.entities = entities;
            return this;
        }

        public Builder decimal(boolean decimal) {
            this.decimal = decimal;
            return this;
        }

        public Builder hexadecimal(boolean hexadecimal) {
            this.hexadecimal = hexadecimal;
            return this;
        }

        public Builder safeChars(String safeChars) {
            this.safeChars = safeChars;
            return this;
        }

        public SlugOptions build() {
            return new SlugOptions(this);
        }
    }
}
