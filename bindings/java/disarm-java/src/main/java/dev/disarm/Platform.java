package dev.disarm;

/** Target platform for filename sanitization. Maps to the core's string tokens. */
public enum Platform {
    UNIVERSAL("universal"),
    WINDOWS("windows"),
    POSIX("posix");

    private final String token;

    Platform(String token) {
        this.token = token;
    }

    String token() {
        return token;
    }
}
