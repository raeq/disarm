package com.disarm;

import com.disarm.internal.Native;
import java.util.Objects;

/**
 * Idiomatic Java entry point for disarm — Unicode confusable / text-security
 * building blocks backed by a native Rust core.
 *
 * <p>The Rust mechanism is transparent: add the dependency and call the static
 * methods; the native library loads itself on first use (see
 * {@code com.disarm.internal.NativeLoader}).
 *
 * <pre>{@code
 * String ascii = Disarm.transliterate("Ｈéllo");            // "Hello"
 * String ru    = Disarm.transliterate("Москва",
 *                    TransliterateOptions.builder().lang("ru").build());
 * }</pre>
 */
public final class Disarm {

    private Disarm() {}

    /** Unicode → ASCII with the default scheme. */
    public static String transliterate(String text) {
        Objects.requireNonNull(text, "text");
        return Native.transliterate(text);
    }

    /** Unicode → ASCII with an explicit scheme and/or language profile. */
    public static String transliterate(String text, TransliterateOptions options) {
        Objects.requireNonNull(text, "text");
        Objects.requireNonNull(options, "options");
        return Native.transliterateOpts(text, options.scheme(), options.lang());
    }
}
