package dev.disarm;

/**
 * Target script for confusable folding. Maps to the core's string tokens.
 *
 * <p>{@link #ARABIC} and {@link #HEBREW} fold toward those scripts (#792); the core and
 * every other binding accepted them before this enum could name them.
 */
public enum TargetScript {
    LATIN("latin"),
    CYRILLIC("cyrillic"),
    ARABIC("arabic"),
    HEBREW("hebrew");

    private final String token;

    TargetScript(String token) {
        this.token = token;
    }

    String token() {
        return token;
    }
}
