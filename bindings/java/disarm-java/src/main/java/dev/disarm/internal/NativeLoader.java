package dev.disarm.internal;

import dev.disarm.DisarmException;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.Locale;

/**
 * Loads the {@code disarm} native library, transparently hiding the Rust
 * mechanism from callers (the "hide-the-Rust" goal).
 *
 * <p>Resolution order:
 * <ol>
 *   <li><b>Dev override</b> — the {@code disarm.native.lib} system property or
 *       {@code DISARM_NATIVE_LIB} env var, an absolute path to a freshly built
 *       shared object. Lets a spike / local build point at
 *       {@code rust/target/release/libdisarm_jni.dylib} with no packaging step.</li>
 *   <li><b>Bundled resource</b> — {@code /dev/disarm/native/<os>-<arch>/<lib>}
 *       inside the JAR (the {@code sqlite-jdbc}/{@code jansi} fat-JAR model),
 *       extracted to a temp file and {@link System#load(String)}ed.</li>
 * </ol>
 *
 * <p>Platform detection is factored into pure, package-private helpers so every
 * OS/arch branch is unit-testable on any host.
 */
final class NativeLoader {

    private static boolean loaded = false;

    private NativeLoader() {}

    static synchronized void load() {
        if (loaded) {
            return;
        }
        System.load(resolveLibraryPath());
        loaded = true;
    }

    /**
     * Resolve the absolute path of the native library to load: the dev override if
     * set, otherwise the platform resource extracted to a temp file. Split out from
     * {@link #load()} so both branches are testable without the (unrepeatable)
     * {@link System#load} side effect.
     */
    static String resolveLibraryPath() {
        String override = overridePath();
        if (override != null) {
            return override;
        }
        return extractBundledLibrary(resourcePath(osArch(), libFileName(osToken())))
                .toAbsolutePath()
                .toString();
    }

    /** The dev-override library path from the property/env, or {@code null} if unset. */
    static String overridePath() {
        String p = System.getProperty("disarm.native.lib");
        if (p == null || p.isEmpty()) {
            p = System.getenv("DISARM_NATIVE_LIB");
        }
        return (p == null || p.isEmpty()) ? null : p;
    }

    /** Extract the classpath resource to a temp file and return its path. */
    static Path extractBundledLibrary(String resource) {
        try (InputStream in = NativeLoader.class.getResourceAsStream(resource)) {
            if (in == null) {
                throw new DisarmException(
                        "disarm native library not found on the classpath at "
                                + resource
                                + " — set the system property 'disarm.native.lib' (or env "
                                + "DISARM_NATIVE_LIB) to a built shared object, or use a JAR that "
                                + "bundles the native library for this platform.");
            }
            Path tmp = Files.createTempFile("libdisarm_jni", suffixOf(resource));
            tmp.toFile().deleteOnExit();
            Files.copy(in, tmp, StandardCopyOption.REPLACE_EXISTING);
            return tmp;
        } catch (IOException e) {
            throw new DisarmException("failed to extract the disarm native library: " + e, e);
        }
    }

    /** Classpath resource path for the given {@code <os>-<arch>} tag and lib filename. */
    static String resourcePath(String osArch, String libFileName) {
        return "/dev/disarm/native/" + osArch + "/" + libFileName;
    }

    /** {@code <os>-<arch>} tag for the running platform, e.g. {@code darwin-aarch64}. */
    static String osArch() {
        return osToken() + "-" + archToken();
    }

    private static String osToken() {
        return osToken(System.getProperty("os.name", ""));
    }

    private static String archToken() {
        return archToken(System.getProperty("os.arch", ""));
    }

    /** Normalize an {@code os.name} value to {@code darwin} / {@code windows} / {@code linux}. */
    static String osToken(String osName) {
        String os = osName.toLowerCase(Locale.ROOT);
        if (os.contains("mac") || os.contains("darwin")) {
            return "darwin";
        }
        if (os.contains("win")) {
            return "windows";
        }
        if (os.contains("nux") || os.contains("nix")) {
            return "linux";
        }
        throw new DisarmException("unsupported OS for disarm native library: " + osName);
    }

    /** Normalize an {@code os.arch} value to {@code aarch64} / {@code x86_64}. */
    static String archToken(String arch) {
        String a = arch.toLowerCase(Locale.ROOT);
        if (a.equals("aarch64") || a.equals("arm64")) {
            return "aarch64";
        }
        if (a.equals("x86_64") || a.equals("amd64")) {
            return "x86_64";
        }
        throw new DisarmException("unsupported CPU architecture for disarm native library: " + arch);
    }

    /** Platform library filename, e.g. {@code libdisarm_jni.dylib} / {@code disarm_jni.dll}. */
    static String libFileName(String osToken) {
        return switch (osToken) {
            case "windows" -> "disarm_jni.dll";
            case "darwin" -> "libdisarm_jni.dylib";
            default -> "libdisarm_jni.so";
        };
    }

    /** The filename suffix (incl. dot) of a resource path, for the temp-file extension. */
    private static String suffixOf(String resource) {
        int dot = resource.lastIndexOf('.');
        return dot < 0 ? "" : resource.substring(dot);
    }
}
