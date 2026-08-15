package dev.disarm;

/**
 * Base type for all errors raised by disarm.
 *
 * <p>Unchecked (extends {@link RuntimeException}) so idiomatic call sites are not
 * forced into {@code try/catch} for what are almost always programming errors
 * (bad scheme/language tokens). The raw JNI layer throws this class — or its
 * {@link DisarmInvalidArgumentException} subtype — directly from Rust.
 */
public class DisarmException extends RuntimeException {

    private static final long serialVersionUID = 1L;

    public DisarmException(String message) {
        super(message);
    }

    public DisarmException(String message, Throwable cause) {
        super(message, cause);
    }
}
