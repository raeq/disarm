package com.disarm.internal;

import com.disarm.DisarmException;
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
 *       {@code rust/target/release/libdisarm.dylib} with no packaging step.</li>
 *   <li><b>Bundled resource</b> — {@code /com/disarm/native/<os>-<arch>/<lib>}
 *       inside the JAR (the {@code sqlite-jdbc}/{@code jansi} fat-JAR model),
 *       extracted to a temp file and {@link System#load(String)}ed.</li>
 * </ol>
 *
 * <p>Idempotent: {@link #load()} runs the resolution once; callers just trigger
 * the {@code Native} class initializer.
 */
final class NativeLoader {

    private static boolean loaded = false;

    private NativeLoader() {}

    static synchronized void load() {
        if (loaded) {
            return;
        }

        String override = System.getProperty("disarm.native.lib");
        if (override == null || override.isEmpty()) {
            override = System.getenv("DISARM_NATIVE_LIB");
        }
        if (override != null && !override.isEmpty()) {
            System.load(override);
            loaded = true;
            return;
        }

        String resource = resourcePath();
        try (InputStream in = NativeLoader.class.getResourceAsStream(resource)) {
            if (in == null) {
                throw new DisarmException(
                        "disarm native library not found on the classpath at "
                                + resource
                                + " — set the system property 'disarm.native.lib' (or env "
                                + "DISARM_NATIVE_LIB) to a built shared object, or use a JAR that "
                                + "bundles the native library for this platform.");
            }
            Path tmp = Files.createTempFile("libdisarm", libSuffix());
            tmp.toFile().deleteOnExit();
            Files.copy(in, tmp, StandardCopyOption.REPLACE_EXISTING);
            System.load(tmp.toAbsolutePath().toString());
            loaded = true;
        } catch (IOException e) {
            throw new DisarmException("failed to extract the disarm native library: " + e, e);
        }
    }

    /** Classpath resource path of the bundled library for the running platform. */
    private static String resourcePath() {
        return "/com/disarm/native/" + osArch() + "/" + libName();
    }

    /** {@code <os>-<arch>} tag, e.g. {@code darwin-aarch64}, {@code linux-x86_64}. */
    static String osArch() {
        return osToken() + "-" + archToken();
    }

    private static String osToken() {
        String os = System.getProperty("os.name", "").toLowerCase(Locale.ROOT);
        if (os.contains("mac") || os.contains("darwin")) {
            return "darwin";
        }
        if (os.contains("win")) {
            return "windows";
        }
        if (os.contains("nux") || os.contains("nix")) {
            return "linux";
        }
        throw new DisarmException("unsupported OS for disarm native library: " + os);
    }

    private static String archToken() {
        String arch = System.getProperty("os.arch", "").toLowerCase(Locale.ROOT);
        if (arch.equals("aarch64") || arch.equals("arm64")) {
            return "aarch64";
        }
        if (arch.equals("x86_64") || arch.equals("amd64")) {
            return "x86_64";
        }
        throw new DisarmException("unsupported CPU architecture for disarm native library: " + arch);
    }

    /** Platform library filename, e.g. {@code libdisarm_jni.dylib} / {@code disarm_jni.dll}. */
    private static String libName() {
        String os = osToken();
        if (os.equals("windows")) {
            return "disarm_jni.dll";
        }
        return "libdisarm_jni" + libSuffix();
    }

    private static String libSuffix() {
        return switch (osToken()) {
            case "darwin" -> ".dylib";
            case "windows" -> ".dll";
            default -> ".so";
        };
    }
}
