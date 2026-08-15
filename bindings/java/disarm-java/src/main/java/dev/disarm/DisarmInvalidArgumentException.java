package dev.disarm;

/**
 * Raised when an argument is invalid — e.g. an unknown transliteration scheme or
 * language token. Corresponds to the core's {@code ErrorKind::InvalidArgument}.
 *
 * <p>The raw JNI layer throws this subtype directly (JNI can {@code ThrowNew} an
 * arbitrary class), so callers can catch it distinctly from other
 * {@link DisarmException}s.
 */
public final class DisarmInvalidArgumentException extends DisarmException {

    private static final long serialVersionUID = 1L;

    public DisarmInvalidArgumentException(String message) {
        super(message);
    }
}
