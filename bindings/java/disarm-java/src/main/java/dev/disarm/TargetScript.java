package dev.disarm;

/** Target script for confusable folding. Maps to the core's string tokens. */
public enum TargetScript {
    LATIN("latin"),
    CYRILLIC("cyrillic");

    private final String token;

    TargetScript(String token) {
        this.token = token;
    }

    String token() {
        return token;
    }
}
