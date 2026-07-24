package com.disarm.internal;

/**
 * Raw JNI entry points — the thin native shim (Layer A/B boundary).
 *
 * <p>This is an <b>internal</b> class: the idiomatic, supported surface is
 * {@link com.disarm.Disarm} (and, later, the Kotlin module). Method names here map
 * 1:1 to {@code Java_com_disarm_internal_Native_*} symbols in the Rust cdylib and
 * take positional, string-token arguments — no defaults, no options objects.
 *
 * <p>The static initializer triggers {@link NativeLoader}, so merely referencing
 * this class loads the native library.
 */
public final class Native {

    static {
        NativeLoader.load();
    }

    private Native() {}

    /** Unicode → ASCII with the default scheme. */
    public static native String transliterate(String text);

    /**
     * Transliterate with a scheme token and an optional language profile.
     *
     * @param text   input
     * @param scheme {@code "default"} | {@code "strict_iso9"} | {@code "gost7034"}
     * @param lang   language profile, or {@code null} for none
     */
    public static native String transliterateOpts(String text, String scheme, String lang);
}
